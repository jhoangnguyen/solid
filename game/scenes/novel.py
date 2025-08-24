# game/scenes/novel.py
from __future__ import annotations
from typing import Optional, Dict, Tuple, Callable
import pygame

from engine.scene import Scene, SceneManager

# Settings + theming
from engine.settings import (
    load_ui_defaults,
    build_theme_from_defaults,
    textbox_fracs_from_defaults,
    reveal_overrides_from_defaults,
    presenter_overrides_from_defaults,
)

# Core UI
from engine.ui.fonts import FontCache
from engine.ui.style import Theme, compute_centered_rect
from engine.ui.widgets.text_box import TextBox
from engine.ui.text_model import RevealParams
from engine.ui.background_manager import BackgroundManager
from engine.ui.widgets.top_icons import TopIcons, IconButton
from engine.ui.widgets.bottom_bar import BottomBar, BottomBarButton
from engine.ui.widgets.window_panel import WindowManager, ModalWindow

# Narrative
from engine.narrative.loader import load_story_file
from engine.narrative.presenter import NodePresenter

# Optional: centralized click routing to avoid text advances on UI hits
try:
    from engine.input_router import InputRouter
except Exception:
    InputRouter = None  # type: ignore


class NovelScene(Scene):
    """
    Visual Novel play scene.
    - Builds Theme/Fonts/TextBox from your UI defaults
    - Loads story and shows the starting node
    - Wires TopIcons, BottomBar, Modal windows
    - Routes input so only TextBox/empty-space clicks advance dialogue
    """

    def __init__(self, mgr: SceneManager):
        self.mgr = mgr
        self.screen = mgr.screen

        # ---- UI defaults, theme, fonts ------------------------------------
        self.defaults = load_ui_defaults("game/config/defaults.yaml")
        self.theme: Theme = build_theme_from_defaults(self.defaults)
        self.fonts = FontCache()

        # Textbox rect (fractions come from defaults, fallback supported)
        wfrac, hfrac = textbox_fracs_from_defaults(self.defaults, (0.40, 0.80))
        self._tb_fracs: Tuple[float, float] = (wfrac, hfrac)
        tb_rect = compute_centered_rect(self.screen, wfrac, hfrac)

        # Reveal params (typing/animation)
        rv = reveal_overrides_from_defaults(self.defaults)
        self.textbox = TextBox(tb_rect, self.theme, self.fonts, reveal=RevealParams(**rv))

        # Background manager + assign TextBox slot
        self.bg = BackgroundManager()
        if hasattr(self.textbox, "view"):
            self.textbox.view.set_background_slot(self.bg, "textbox")

        # Icons / Bottom bar / Windows
        self.top_icons = TopIcons(self.theme, count=3)
        self.top_icons.set_icons(
            [
                IconButton("map", image_path="game/assets/ui/map.png"),
                IconButton("bag", image_path="game/assets/ui/backpack.jpg"),
                IconButton("menu", image_path="game/assets/ui/menu.png"),
            ]
        )

        self.bottom_bar = BottomBar(self.theme, width_frac=0.92, height_frac=0.18, margin_px=10)
        self.bottom_bar.set_slots(
            {
                "left_1": BottomBarButton("left_1", "Objectives"),
                "left_4": BottomBarButton("left_4", "Calendar"),
                "right_1": BottomBarButton("right_1", "MAP"),
                "right_2": BottomBarButton("right_2", "Inventory"),
                "right_3": BottomBarButton("right_3", "Settings"),
            }
        )

        self.windows = WindowManager(theme=self.theme)
        self.icon_routes: Dict[str, tuple[str, Callable[[], ModalWindow]]] = {
            "bag": ("inventory", self._build_inventory_window),
            "map": ("map", self._build_map_window),
            "menu": ("settings", self._build_settings_window),
        }

        # Click router (optional; falls back to local logic if unavailable)
        self.router = InputRouter(
            windows=self.windows,
            textbox=self.textbox,
            top_icons=self.top_icons,
            bottom_bar=self.bottom_bar,
        ) if InputRouter else None

        # Story/presenter
        story_path = "game/content/prologue.yaml"
        self.story = load_story_file(story_path)
        pr = presenter_overrides_from_defaults(self.defaults)
        self.presenter = NodePresenter(
            self.textbox,
            self.story,
            bg_manager=self.bg,
            clear_after_nodes=pr.get("clear_after_nodes"),
            insert_node_separator=pr.get("insert_node_separator", False),
            separator_text=pr.get("separator_text", "—"),
        )

        # Simple clock for per-scene timing if you need it
        self.clock = pygame.time.Clock()

    # --- Scene lifecycle ----------------------------------------------------
    def on_enter(self, prev: Optional[Scene]) -> None:
        # Set an initial background (from defaults, or a fallback image)
        try:
            win_bg = (self.defaults.get("backgrounds", {}) or {}).get("window", {}) or {}
            if win_bg:
                self.bg.set(win_bg, transition="cut")
            else:
                self.bg.set(
                    {
                        "image_path": "game/assets/backgrounds/stock_fireplace.jpg",
                        "mode": "cover",
                        "tint_rgba": (0, 0, 0, 64),
                    },
                    transition="cut",
                )
        except Exception:
            self.bg.set(
                {
                    "image_path": "game/assets/backgrounds/stock_fireplace.jpg",
                    "mode": "cover",
                    "tint_rgba": (0, 0, 0, 64),
                },
                transition="cut",
            )

        # Start at the story's starting node
        if hasattr(self.story, "start") and self.story.start in self.story.nodes:
            self.presenter.show_node(self.story.nodes[self.story.start])

    def on_exit(self, nxt: Optional[Scene]) -> None:
        pass

    def on_pause(self) -> None:
        pass

    def on_resume(self) -> None:
        # Re-apply scaling on resume in case window changed while paused
        self._apply_text_scaling()

    # --- Loop ---------------------------------------------------------------
    def handle_event(self, e: pygame.event.Event) -> bool:
        # Windows first (drag/close/etc.)
        if self.windows.handle_event(e):
            return True

        # --- Keyboard
        if e.type == pygame.KEYDOWN:
            if e.key == pygame.K_ESCAPE:
                # Close a window if open; otherwise request app quit
                if self.windows.any_open():
                    self.windows.close_top()
                else:
                    self.mgr.request_quit = True
                return True

            if self._handle_scroll_key(e.key):
                return True

            if self.textbox.choice_active():
                if self._is_advance_key(e.key):
                    idx = self.textbox.choice_get_selected_index()
                    if idx is not None and idx >= 0:
                        self.presenter.submit_choice_index(idx)
                    return True
                elif e.key == pygame.K_UP:
                    self.textbox.choice_move_cursor(-1)
                    return True
                elif e.key == pygame.K_DOWN:
                    self.textbox.choice_move_cursor(+1)
                    return True
            else:
                if self._is_advance_key(e.key):
                    self.textbox.on_player_press()
                    return True
            return False

        # --- Hover
        if e.type == pygame.MOUSEMOTION:
            if hasattr(self.top_icons, "on_mouse_move"):
                self.top_icons.on_mouse_move(e.pos)
            if self.textbox.choice_active():
                self.textbox.choice_hover_at(e.pos)
            if hasattr(self.bottom_bar, "on_mouse_move"):
                self.bottom_bar.on_mouse_move(e.pos)
            return False  # do not consume hover

        # --- Mouse down (left)
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            # Bottom bar can consume clicks before anything else
            if hasattr(self.bottom_bar, "handle_event") and self.bottom_bar.handle_event(e):
                return True

            # Icons: never advance text
            if self.top_icons.hit_test(e.pos):
                sid = self.top_icons.get_clicked(e.pos)
                if sid:
                    route = self.icon_routes.get(sid)
                    if route:
                        win_id, builder = route
                        self.windows.toggle(win_id, builder=builder)
                return True

            # Choices: only clicking a choice selects; outside is ignored
            if self.textbox.choice_active():
                if self.textbox.rect.collidepoint(e.pos):
                    idx = self.textbox.choice_click(e.pos)
                    if idx is not None:
                        self.presenter.submit_choice_index(idx)
                return True

            # Normal: textbox or empty space to advance (not UI/windows)
            if self._progress_allowed(e.pos):
                self.textbox.on_player_press()
                return True
            return False

        # --- Mouse up (left)
        if e.type == pygame.MOUSEBUTTONUP and e.button == 1:
            if hasattr(self.top_icons, "on_mouse_up"):
                self.top_icons.on_mouse_up()
            if hasattr(self.bottom_bar, "on_mouse_up"):
                self.bottom_bar.on_mouse_up()
            return False

        # --- Scroll wheel
        if e.type == pygame.MOUSEWHEEL:
            self.textbox.scroll(-e.y * 40)  # default step; adjust if you keep this in cfg
            return True

        # --- Resize
        if e.type == pygame.VIDEORESIZE:
            # App already recreated the window; update our screen ref & layout
            self.screen = self.mgr.screen
            wfrac, hfrac = self._tb_fracs
            self.textbox.on_resize(compute_centered_rect(self.screen, wfrac, hfrac))
            self._apply_text_scaling()
            if hasattr(self.bottom_bar, "on_resize"):
                self.bottom_bar.on_resize(self.screen.get_rect())
            if hasattr(self.top_icons, "on_resize"):
                self.top_icons.on_resize(self.screen.get_rect())
            if hasattr(self.windows, "on_resize"):
                self.windows.on_resize(self.screen.get_rect())
            return True

        return False

    def update(self, dt: float) -> None:
        if hasattr(self.presenter, "update"):
            self.presenter.update(dt)
        if hasattr(self.textbox, "update"):
            self.textbox.update(dt)
        if hasattr(self.bg, "update"):
            self.bg.update(dt)

    def draw(self, surface: pygame.Surface) -> None:
        # Background first
        self.bg.draw(surface, surface.get_rect())

        # VN layer
        self.textbox.draw(surface)

        # Optional bars/icons
        # if hasattr(self.bottom_bar, "draw"):
        #     self.bottom_bar.draw(surface)
        if hasattr(self.top_icons, "draw"):
            self.top_icons.draw(surface)

        # Modal windows on top (handles optional dimming internally)
        self.windows.draw(surface)

    # --- helpers ------------------------------------------------------------
    def _is_advance_key(self, key: int) -> bool:
        return key in (pygame.K_SPACE, pygame.K_RETURN, pygame.K_KP_ENTER)

    def _handle_scroll_key(self, key: int) -> bool:
        if key == pygame.K_PAGEUP:
            self.textbox.page_up()
            return True
        if key == pygame.K_PAGEDOWN:
            self.textbox.page_down()
            return True
        if key == pygame.K_HOME:
            self.textbox.scroll_to_top()
            return True
        if key == pygame.K_END:
            self.textbox.scroll_to_bottom()
            return True
        return False

    def _progress_allowed(self, pos: Tuple[int, int]) -> bool:
        # Prefer centralized router if available
        if self.router:
            try:
                return bool(self.router.click_progress_allowed(pos))
            except Exception:
                pass
        # Fallback: block if clicking UI/windows
        if getattr(self.bottom_bar, "hit_test", None) and self.bottom_bar.hit_test(pos):
            return False
        if self.top_icons.hit_test(pos):
            return False
        if self.windows.hit_test(pos):
            return False
        # Otherwise it's textbox or empty space
        return True

    def _apply_text_scaling(self) -> None:
        """Scale the theme font size relative to window height and rebuild layouts."""
        try:
            sh = self.screen.get_height()
            base = max(1, 720)  # assume design at 720h if you don't track a base
            scaled = int(round(self.theme.font_size * (sh / base)))
            cap = max(self.theme.font_size, min(int(self.theme.font_size * 1.75), scaled))
            if cap != self.theme.font_size:
                self.theme.font_size = cap
                # Push new theme to TextBox view + refresh caches/layouts
                self.textbox.view.set_theme(self.theme)
                self.textbox.fonts.clear()
                self.textbox.view.invalidate_layout()
        except Exception as ex:
            print(f"[novel/font-scale] error: {ex}")

    # --- Window builders (simple templates) --------------------------------
    def _build_inventory_window(self) -> ModalWindow:
        sw, sh = self.screen.get_size()
        w, h = max(320, sw // 2), max(240, sh // 2)
        x, y = (sw - w) // 2, (sh - h) // 2
        return ModalWindow(
            "inventory",
            pygame.Rect(x, y, w, h),
            title="Inventory",
            theme=self.theme,
            content_draw=self._draw_inventory_content,
            dims_backdrop=False,
        )

    def _draw_inventory_content(self, surface: pygame.Surface, rect: pygame.Rect) -> None:
        pygame.draw.rect(surface, (255, 255, 255, 20), rect, border_radius=8)
        pygame.draw.rect(surface, (255, 255, 255), rect, width=1, border_radius=8)
        font = pygame.font.Font(getattr(self.theme, "font_path", None), max(12, self.theme.font_size))
        sub = font.render("Inventory (WIP)", True, (220, 220, 220))
        surface.blit(sub, (rect.x + 8, rect.y + 6))

    def _build_map_window(self) -> ModalWindow:
        sw, sh = self.screen.get_size()
        w, h = max(360, int(sw * 0.55)), max(260, int(sh * 0.5))
        x, y = (sw - w) // 2, (sh - h) // 2
        return ModalWindow(
            "map",
            pygame.Rect(x, y, w, h),
            title="Map",
            theme=self.theme,
            content_draw=self._draw_map_content,
            dims_backdrop=False,
        )

    def _draw_map_content(self, surface: pygame.Surface, rect: pygame.Rect) -> None:
        pygame.draw.rect(surface, (255, 255, 255, 20), rect, border_radius=8)
        pygame.draw.rect(surface, (255, 255, 255), rect, width=1, border_radius=8)
        font = pygame.font.Font(getattr(self.theme, "font_path", None), max(12, self.theme.font_size))
        sub = font.render("Map (WIP)", True, (220, 220, 220))
        surface.blit(sub, (rect.x + 8, rect.y + 6))

    def _build_settings_window(self) -> ModalWindow:
        sw, sh = self.screen.get_size()
        w, h = max(360, int(sw * 0.45)), max(240, int(sh * 0.4))
        x, y = (sw - w) // 2, (sh - h) // 2
        return ModalWindow(
            "settings",
            pygame.Rect(x, y, w, h),
            title="Settings",
            theme=self.theme,
            content_draw=self._draw_settings_content,
            draggable=False,
            keep_centered=True,
            center_x=True,
            center_y=True,
        )

    def _draw_settings_content(self, surface: pygame.Surface, rect: pygame.Rect) -> None:
        pygame.draw.rect(surface, (255, 255, 255, 20), rect, border_radius=8)
        pygame.draw.rect(surface, (255, 255, 255), rect, width=1, border_radius=8)
        font = pygame.font.Font(getattr(self.theme, "font_path", None), max(12, self.theme.font_size))
        sub = font.render("Settings (WIP)", True, (220, 220, 220))
        surface.blit(sub, (rect.x + 8, rect.y + 6))
