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


class GameApp:
    def __init__(self, cfg: AppCfg):
        # Set config
        self.cfg = cfg
        
        # Initialize PyGame
        pygame.init()
        
        # Set window size and title
        pygame.display.set_caption(cfg.window.title)
        self.screen = pygame.display.set_mode((cfg.window.width, cfg.window.height), flags=pygame.RESIZABLE | pygame.SCALED | pygame.DOUBLEBUF)
        
        # Load default settings
        self.defaults = load_ui_defaults("game/config/defaults.yaml")
        self.theme : Theme = build_theme_from_defaults(self.defaults)
        print("player_choice:", getattr(self.theme, "player_choice", {}))
        
        self.fonts = FontCache()

        
        # --- Textbox ---
        wfrac, hfrac = textbox_fracs_from_defaults(self.defaults, (cfg.textbox.width_frac, cfg.textbox.height_frac))
        self._tb_fracs = (wfrac, hfrac)
        tb_rect = compute_centered_rect(self.screen, wfrac, hfrac)
        rv = reveal_overrides_from_defaults(self.defaults)
        self.textbox = TextBox(tb_rect, self.theme, reveal=RevealParams(**rv))
        
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
            # defaults = load_ui_defaults("game/config/defaults.yaml")
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
            "left_4": BottomBarButton("left_4", "Inventory"),
            # Fill the rest later:
            # "left_2": BottomBarButton("left_2", "Party"),
            # "left_3": BottomBarButton("left_3", "Quests"),
            # "left_5": BottomBarButton("left_5", "Skills"),
            # "left_6": BottomBarButton("left_6", "Codex"),

            # right stack (top→bottom)
            "right_2": BottomBarButton("right_2", "MAP"),
        })

                
    # def handle_input(self):
    #     for e in pygame.event.get():
    #         if e.type == pygame.QUIT:
    #             self.running = False
    #         elif e.type == pygame.KEYDOWN:
    #             if e.key == pygame.K_ESCAPE:
    #                 self.running = False
    #             elif self.textbox.choice_active():
    #                 if e.key == pygame.K_UP:
    #                     self.textbox.choice_move_cursor(-1)
    #                 elif e.key == pygame.K_DOWN:
    #                     self.textbox.choice_move_cursor(+1)
    #                 elif e.key in (pygame.K_RETURN, pygame.K_SPACE):
    #                     idx = self.textbox.choice_get_selected_index()
    #                     if idx is not None and idx >= 0:
    #                         self.presenter.submit_choice_index(idx)
    #                 elif e.key == pygame.K_PAGEUP:
    #                     self.textbox.scroll(-self.textbox.viewport_height * self.cfg.input.page_scroll_frac)
    #                 elif e.key == pygame.K_PAGEDOWN:
    #                     self.textbox.scroll(+self.textbox.viewport_height * self.cfg.input.page_scroll_frac)
    #                 elif e.key == pygame.K_HOME:
    #                     self.textbox.scroll_to_top()
    #                 elif e.key == pygame.K_END:
    #                     self.textbox.scroll_to_bottom()
    #             else:
    #                 # no active choice panel -> normal VN advance controls
    #                 if e.key in (pygame.K_SPACE, pygame.K_RETURN):
    #                     self.textbox.on_player_press()
    #                 elif e.key == pygame.K_PAGEUP:
    #                     self.textbox.scroll(-self.textbox.viewport_height * self.cfg.input.page_scroll_frac)
    #                 elif e.key == pygame.K_PAGEDOWN:
    #                     self.textbox.scroll(+self.textbox.viewport_height * self.cfg.input.page_scroll_frac)
    #                 elif e.key == pygame.K_HOME:
    #                     self.textbox.scroll_to_top()
    #                 elif e.key == pygame.K_END:
    #                     self.textbox.scroll_to_bottom()

    #         elif e.type == pygame.MOUSEMOTION:
    #             if self.textbox.choice_active():
    #                 self.textbox.choice_hover_at(e.pos)

    #         elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
    #             if self.textbox.choice_active():
    #                 idx = self.textbox.choice_click(e.pos)
    #                 if idx is not None:
    #                     self.presenter.submit_choice_index(idx)
    #             else:
    #                 self.textbox.on_player_press()

    #         elif e.type == pygame.MOUSEWHEEL:
    #             self.textbox.scroll(-e.y * self.cfg.input.scroll_wheel_pixels)
    #         elif e.type == pygame.VIDEORESIZE:
    #             self.screen = pygame.display.set_mode((e.w, e.h), pygame.RESIZABLE)
    #             wfrac, hfrac = self._tb_fracs
    #             self.textbox.on_resize(compute_centered_rect(self.screen, self.cfg.textbox.width_frac, self.cfg.textbox.height_frac))
                
    def handle_input(self):
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                self.running = False

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
                # Optional: hover support for choices and bar
                if self.textbox.choice_active():
                    self.textbox.choice_hover_at(e.pos)
                # If your BottomBar has hover, call it here (no-op if absent):
                if hasattr(self.bottom_bar, "on_mouse_move"):
                    self.bottom_bar.on_mouse_move(e.pos)

            elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                # 1) Give the bottom bar first crack — if consumed, stop here.
                if self._handle_bottom_bar_click(e.pos):
                    # Prevent simultaneous textbox click
                    continue

                # 2) Otherwise, route to textbox / choices
                if self.textbox.choice_active():
                    idx = self.textbox.choice_click(e.pos)
                    if idx is not None:
                        print(f"[collision-test] textbox: CLICKED choice index {idx}")
                        self.presenter.submit_choice_index(idx)
                    else:
                        print("[collision-test] textbox: click (no choice)")
                else:
                    print("[collision-test] textbox: click (advance)")
                    self.textbox.on_player_press()

            elif e.type == pygame.MOUSEWHEEL:
                self.textbox.scroll(-e.y * self.cfg.input.scroll_wheel_pixels)

            elif e.type == pygame.VIDEORESIZE:
                self.screen = pygame.display.set_mode((e.w, e.h), pygame.RESIZABLE)
                # Reuse the resolved fractions you stored earlier
                wfrac, hfrac = self._tb_fracs
                self.textbox.on_resize(compute_centered_rect(self.screen, wfrac, hfrac))
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
        self.screen.set_clip(None)

        fps = int(self.clock.get_fps())

        hud = self.hud_font.render(f"{fps} FPS", True, (180, 180, 180))
        self.bottom_bar.draw(self.screen)
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
