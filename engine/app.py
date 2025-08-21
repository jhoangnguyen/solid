import pygame
from dataclasses import dataclass
from engine.ui.fonts import FontCache
from engine.ui.style import Theme, StyleContext, compute_centered_rect, WaitIndicatorStyle
from engine.ui.widgets.text_box import TextBox, RevealParams
from engine.ui.anim import Animator, Tween
from engine.settings import load_settings, AppCfg, load_ui_defaults, build_theme_from_defaults, textbox_fracs_from_defaults, reveal_overrides_from_defaults, presenter_overrides_from_defaults
from engine.narrative.loader import load_story_file
from engine.narrative.presenter import NodePresenter
from engine.ui.background_manager import BackgroundManager
from engine.ui.widgets.bottom_bar import BottomBar, BottomBarButton
from engine.ui.widgets.top_icons import TopIcons, IconButton
from engine.ui.widgets.window_panel import WindowManager, ModalWindow
from engine.resources import after_display_init

class GameApp:
    def __init__(self, cfg: AppCfg):
        # Set config
        self.cfg = cfg
        
        # Initialize PyGame
        pygame.init()
        
        # Set window size and title
        pygame.display.set_caption(cfg.window.title)
        self.screen = pygame.display.set_mode((cfg.window.width, cfg.window.height), flags=pygame.RESIZABLE | pygame.SCALED | pygame.DOUBLEBUF)
        after_display_init()
        
        # Load default settings
        self.defaults = load_ui_defaults("game/config/defaults.yaml")
        self.theme : Theme = build_theme_from_defaults(self.defaults)
        self.fonts = FontCache()
        print("player_choice:", getattr(self.theme, "player_choice", {}))
        
        self._min_font_px = int(self.theme.font_size)          # floor (your current size)
        self._font_base_h = int(self.screen.get_height())      # reference height for scaling
        self._max_font_px = 30

        
        # --- Textbox ---
        wfrac, hfrac = textbox_fracs_from_defaults(self.defaults, (cfg.textbox.width_frac, cfg.textbox.height_frac))
        self._tb_fracs = (wfrac, hfrac)
        tb_rect = compute_centered_rect(self.screen, wfrac, hfrac)
        rv = reveal_overrides_from_defaults(self.defaults)
        self.textbox = TextBox(tb_rect, self.theme, self.fonts, reveal=RevealParams(**rv))
        
        self._apply_text_scaling()                              # Apply text scaling after text box init
        
        self.clock = pygame.time.Clock()
        self.running = True

        self.anim = Animator()
        
        # --- Load YAML ---
        story_path = "game/content/prologue.yaml"
        self.story = load_story_file(story_path)
        self.current_node_id = self.story.start
        
        # --- Background Manager ---
        self.bg = BackgroundManager()                         # create the manager
        
        self.textbox.view.set_background_slot(self.bg, "textbox")
        
        # Seed initial background from defaults.yaml if present; otherwise fall back to the old fireplace.
        try:
            win_bg = (self.defaults.get("backgrounds", {}) or {}).get("window", {}) or {}
            if win_bg:
            # accept dict spec straight from YAML
                self.bg.set(win_bg, transition="cut")
            else:
                self.bg.set({
                    "image_path": "game/assets/backgrounds/stock_fireplace.jpg",
                    "mode": "cover",
                "tint_rgba": (0, 0, 0, 64),
                }, transition="cut")
        except Exception:
            # Safe fallback if defaults.yaml isn’t available
            self.bg.set({
            "image_path": "game/assets/backgrounds/stock_fireplace.jpg",
            "mode": "cover",
            "tint_rgba": (0, 0, 0, 64),
            }, transition="cut")

        # --- Node Presenter --- 
        # Loads each node in .yaml files along with the background
        pr = presenter_overrides_from_defaults(self.defaults)
        self.presenter = NodePresenter(
            self.textbox, 
            self.story, 
            bg_manager=self.bg,
            clear_after_nodes=pr.get("clear_after_nodes"),            # Keep N nodes, clear on the N + 1th
            insert_node_separator=pr["insert_node_separator"],     # Blank line between nodes
            separator_text=pr["separator_text"],               # Customize if desired, e.g. "-"
            )
        self.presenter.show_node(self.story.nodes[self.current_node_id])
        
        self.hud_font = pygame.font.Font(None, 24)

        
        self.bottom_bar = BottomBar(self.theme, width_frac=0.92, height_frac=0.18, margin_px=10)
        self.bottom_bar.set_slots({
            # left six (top row: 1–3, bottom row: 4–6)
            "left_1": BottomBarButton("left_1", "Objectives"),
            "left_4": BottomBarButton("left_4", "Calendar"),
            # Fill the rest later:
            # "left_2": BottomBarButton("left_2", "Party"),
            # "left_3": BottomBarButton("left_3", "Quests"),
            # "left_5": BottomBarButton("left_5", "Skills"),
            # "left_6": BottomBarButton("left_6", "Codex"),

            # right stack (top→bottom)
            "right_1": BottomBarButton("right_1", "MAP"),
            "right_2": BottomBarButton("right_2", "Inventory"),
            "right_3": BottomBarButton("right_3", "Settings"),
        })
        
        # --- Top-right icons (3) ---
        self.top_icons = TopIcons(self.theme, count=3)
        self.top_icons.set_icons([
            IconButton("map",  image_path="game/assets/ui/map.png"),
            IconButton("bag",  image_path="game/assets/ui/backpack.jpg"),
            IconButton("menu", image_path="game/assets/ui/menu.png"),
        ])
        
        # Map icon id -> (window_id, builder)
        self.icon_routes = {
            "bag":  ("inventory", self._build_inventory_window),
            "map":  ("map",       self._build_map_window),
            "menu": ("settings",  self._build_settings_window),
        }
        
        # --- Initialiize In-Game Windows ---
        self.windows = WindowManager(self.theme)

    def handle_input(self):
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                self.running = False
                
            # --- windows get first dibs ---
            if self.windows.handle_event(e):
                # If a window handled this, don't fall through to game UI.
                continue

            elif e.type == pygame.KEYDOWN:
                if e.key == pygame.K_ESCAPE:
                    self.running = False
                    continue

                # Scroll keys work the same with or without an active choice
                if self._handle_scroll_key(e.key):
                    continue

                if self.textbox.choice_active():
                    # In choice mode: Enter/Space selects; others fall through
                    if self._is_advance_key(e.key):
                        idx = self.textbox.choice_get_selected_index()
                        if idx is not None and idx >= 0:
                            self.presenter.submit_choice_index(idx)
                    elif e.key == pygame.K_UP:
                        self.textbox.choice_move_cursor(-1)
                    elif e.key == pygame.K_DOWN:
                        self.textbox.choice_move_cursor(+1)
                else:
                    # Normal VN advance
                    if self._is_advance_key(e.key):
                        self.textbox.on_player_press()

            elif e.type == pygame.MOUSEMOTION:
                self.top_icons.on_mouse_move(e.pos)
                # Optional: hover support for choices and bar
                if self.textbox.choice_active():
                    self.textbox.choice_hover_at(e.pos)
                # If your BottomBar has hover, call it here (no-op if absent):
                if hasattr(self.bottom_bar, "on_mouse_move"):
                    self.bottom_bar.on_mouse_move(e.pos)
                    
            elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                # 1) Icons never advance text
                if self.top_icons.hit_test(e.pos):
                    sid = self.top_icons.get_clicked(e.pos)
                    if sid:
                        route = self.icon_routes.get(sid)
                        if route:
                            win_id, builder = route
                            self.windows.toggle(win_id, builder=builder)
                        else:
                            print(f"[icons] no route for '{sid}'")
                    continue  # stop here; icon clicks don't advance text

                # 2) If click lands on any open window, do not progress text
                if self.windows.any_open() and self.windows.hit_test(e.pos):
                    # Let windows drag/close logic run (already called at loop top),
                    # but don't fall through to text progression.
                    continue

                in_tb = self.textbox.rect.collidepoint(e.pos)

                # 3) Choices: only clicking an actual choice selects; nothing else advances
                if self.textbox.choice_active():
                    if in_tb:
                        idx = self.textbox.choice_click(e.pos)
                        if idx is not None:
                            print(f"[collision-test] textbox: CLICKED choice index {idx}")
                            self.presenter.submit_choice_index(idx)
                    # Clicks outside the textbox are ignored while choices are up
                    continue

                # 4) No choices: advance only when clicking textbox OR empty space
                if in_tb:
                    print("[collision-test] textbox: click (advance)")
                    self.textbox.on_player_press()
                else:
                    print("[collision-test] empty space: click (advance)")
                    self.textbox.on_player_press()
                continue
            
            elif e.type == pygame.MOUSEBUTTONUP and e.button == 1:
                self.top_icons.on_mouse_up()

            elif e.type == pygame.MOUSEWHEEL:
                self.textbox.scroll(-e.y * self.cfg.input.scroll_wheel_pixels)

            elif e.type == pygame.VIDEORESIZE:
                self.screen = pygame.display.set_mode((e.w, e.h), pygame.RESIZABLE)
                # Reuse the resolved fractions you stored earlier
                wfrac, hfrac = self._tb_fracs
                self.textbox.on_resize(compute_centered_rect(self.screen, wfrac, hfrac))
                # Now scale the font (and rebuild layout/caches)
                self._apply_text_scaling()
                # Refresh icons if necessary
                # if hasattr(self, "top_icons") and hasattr(self.top_icons, "on_resize"):
                #     self.top_icons.on_resize()
                if hasattr(self.bottom_bar, "on_resize"):
                    self.bottom_bar.on_resize(self.screen.get_rect())
                
    def update(self, dt: float):
        # Function to run on delta time to update game state. 
        self.presenter.update(dt)
        self.textbox.update(dt)
        self.bg.update(dt)
        # pass
    
    def draw(self):
        self.bg.draw(self.screen, self.screen.get_rect())
        self.textbox.draw(self.screen)
        self.top_icons.draw(self.screen)
        self.windows.draw(self.screen)
        self.screen.set_clip(None)

        fps = int(self.clock.get_fps())

        hud = self.hud_font.render(f"{fps} FPS", True, (180, 180, 180))
        # self.bottom_bar.draw(self.screen)
        self.screen.blit(hud, (8, 6))
        pygame.display.flip()
        
    def run(self):
        while self.running:
            dt = self.clock.tick(self.cfg.fps) / 1000.0
            self.handle_input()
            self.update(dt)
            self.draw()
        pygame.quit()
        
    def _is_advance_key(self, key: int) -> bool:
        return key in (pygame.K_SPACE, pygame.K_RETURN)

    def _handle_scroll_key(self, key: int) -> bool:
        """Return True if handled; performs the scroll."""
        vh = self.textbox.viewport_height
        pf = self.cfg.input.page_scroll_frac
        if key == pygame.K_PAGEUP:
            self.textbox.scroll(-vh * pf)
            return True
        if key == pygame.K_PAGEDOWN:
            self.textbox.scroll(+vh * pf)
            return True
        if key == pygame.K_HOME:
            self.textbox.scroll_to_top()
            return True
        if key == pygame.K_END:
            self.textbox.scroll_to_bottom()
            return True
        return False

    def _handle_bottom_bar_click(self, pos: tuple[int,int]) -> bool:
        """
        Returns True if the bottom bar consumed the click.
        Prints what happened for a simple 'collisions' test.
        """
        # First: is the pointer inside the bar region at all?
        if hasattr(self.bottom_bar, "hit_test") and self.bottom_bar.hit_test(pos):
            # Inside the bar; do not forward to textbox.
            sid = None
            if hasattr(self.bottom_bar, "get_clicked"):
                sid = self.bottom_bar.get_clicked(pos)

            if sid:
                print(f"[collision-test] bottom_bar: CLICKED button '{sid}'")
                # TODO: your real action by id goes here, e.g. open inventory/map/etc.
            else:
                print("[collision-test] bottom_bar: click in empty bar area")
            return True

        # If BottomBar has no hit_test(), be conservative and treat as not-consumed
        return False
            
    def _apply_text_scaling(self) -> None:
        """Scale theme.font_size with window height, but never below the initial size."""
        try:
            sh = pygame.display.get_window_size()[1] if hasattr(pygame.display, "get_window_size") else self.screen.get_height()
            k = max(0.0, sh / max(1, self._font_base_h))
            scaled = int(round(self._min_font_px * k))

            caps = []
            # absolute px cap
            mx = getattr(self.theme, "max_font_px", None)
            if mx: caps.append(int(mx))
            # relative to baseline
            mult = getattr(self.theme, "font_max_mult", None)
            if mult: caps.append(int(self._min_font_px * float(mult)))
            # fraction of textbox viewport height
            frac = getattr(self.theme, "font_max_frac_of_tb", None)
            if frac:
                tb_h = getattr(self.textbox, "viewport_height", None) or sh
                caps.append(int(float(frac) * tb_h))

            cap_px = min(caps) if caps else int(self._min_font_px * 1.75)
            new_px = max(self._min_font_px, min(cap_px, scaled))

            if new_px != self.theme.font_size:
                old = self.theme.font_size
                self.theme.font_size = new_px
                self.textbox.view.set_theme(self.theme)  # rebuild TextLayout font
                self.textbox.fonts.clear()
                self.textbox.view.invalidate_layout()
                print(f"[font-scale] {old} -> {new_px} (caps={caps or 'default'})")
        except Exception as ex:
            print(f"[font-scale] error: {ex}")

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
        )

    def _draw_inventory_content(self, surface: pygame.Surface, rect: pygame.Rect) -> None:
        # Placeholder “grid” so you have something to tweak later.
        # Draw a subtle panel background (optional).
        pygame.draw.rect(surface, (255, 255, 255, 20), rect, border_radius=8)
        pygame.draw.rect(surface, (255, 255, 255), rect, width=1, border_radius=8)

        # Title-ish text inside content
        font = pygame.font.Font(getattr(self.theme, "font_path", None), max(12, self.theme.font_size))
        sub = font.render("Inventory (WIP template)", True, (220, 220, 220))
        surface.blit(sub, (rect.x + 8, rect.y + 6))

        # Simple 5x4 slots grid
        rows, cols = 4, 5
        gap = 8
        slot_w = (rect.w - gap * (cols + 1)) // cols
        slot_h = (rect.h - 40 - gap * (rows + 1)) // rows  # leave a little header space
        y = rect.y + 32
        for r in range(rows):
            x = rect.x + gap
            for c in range(cols):
                cell = pygame.Rect(x, y, slot_w, slot_h)
                pygame.draw.rect(surface, (255, 255, 255, 40), cell, border_radius=6)
                pygame.draw.rect(surface, (255, 255, 255), cell, width=1, border_radius=6)
                x += slot_w + gap
            y += slot_h + gap


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
        )

    def _draw_map_content(self, surface: pygame.Surface, rect: pygame.Rect) -> None:
        pygame.draw.rect(surface, (255, 255, 255, 20), rect, border_radius=8)
        pygame.draw.rect(surface, (255, 255, 255), rect, width=1, border_radius=8)
        font = pygame.font.Font(getattr(self.theme, "font_path", None), max(12, self.theme.font_size))
        sub = font.render("Map (WIP template)", True, (220, 220, 220))
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
            draggable=False, # Locked in place
        )

    def _draw_settings_content(self, surface: pygame.Surface, rect: pygame.Rect) -> None:
        pygame.draw.rect(surface, (255, 255, 255, 20), rect, border_radius=8)
        pygame.draw.rect(surface, (255, 255, 255), rect, width=1, border_radius=8)
        font = pygame.font.Font(getattr(self.theme, "font_path", None), max(12, self.theme.font_size))
        sub = font.render("Settings (WIP template)", True, (220, 220, 220))
        surface.blit(sub, (rect.x + 8, rect.y + 6))
