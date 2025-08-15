import pygame
from dataclasses import dataclass
from engine.ui.style import Theme, StyleContext, compute_centered_rect, WaitIndicatorStyle
from engine.ui.widgets.text_box import TextBox, RevealParams
from engine.ui.anim import Animator, Tween
from engine.settings import load_settings, AppCfg, load_ui_defaults, build_theme_from_defaults, textbox_fracs_from_defaults, reveal_overrides_from_defaults
from engine.narrative.loader import load_story_file
from engine.narrative.presenter import NodePresenter
from engine.ui.brushes.image_brush import ImageBrush
from engine.ui.background_manager import BackgroundManager

class GameApp:
    def __init__(self, cfg: AppCfg):
        # Set config
        self.cfg = cfg
        
        # Initialize PyGame
        pygame.init()
        
        # Set window size and title
        pygame.display.set_caption(cfg.window.title)
        self.screen = pygame.display.set_mode((cfg.window.width, cfg.window.height), pygame.RESIZABLE)
        
        # Load default settings
        defaults = load_ui_defaults("game/config/defaults.yaml")
        self.theme = build_theme_from_defaults(defaults)
        
        # --- Textbox ---
        wfrac, hfrac = textbox_fracs_from_defaults(defaults, (cfg.textbox.width_frac, cfg.textbox.height_frac))
        tb_rect = compute_centered_rect(self.screen, wfrac, hfrac)
        rv = reveal_overrides_from_defaults(defaults)
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
            defaults = load_ui_defaults("game/config/defaults.yaml")
            win_bg = (defaults.get("backgrounds", {}) or {}).get("window", {}) or {}
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
        self.presenter = NodePresenter(self.textbox, self.story, bg_manager=self.bg)
        self.presenter.show_node(self.story.nodes[self.current_node_id])
        
        self.hud_font = pygame.font.Font(None, 24)
        
    def handle_input(self):
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                self.running = False
            elif e.type == pygame.KEYDOWN:
                if e.key == pygame.K_ESCAPE:
                    self.running = False
                elif self.textbox.choice_active():
                    if e.key == pygame.K_UP:
                        self.textbox.choice_move_cursor(-1)
                    elif e.key == pygame.K_DOWN:
                        self.textbox.choice_move_cursor(+1)
                    elif e.key in (pygame.K_RETURN, pygame.K_SPACE):
                        idx = self.textbox.choice_get_selected_index()
                        if idx is not None and idx >= 0:
                            self.presenter.submit_choice_index(idx)
                    elif e.key == pygame.K_PAGEUP:
                        self.textbox.scroll(-self.textbox.viewport_height * self.cfg.input.page_scroll_frac)
                    elif e.key == pygame.K_PAGEDOWN:
                        self.textbox.scroll(+self.textbox.viewport_height * self.cfg.input.page_scroll_frac)
                    elif e.key == pygame.K_HOME:
                        self.textbox.scroll_to_top()
                    elif e.key == pygame.K_END:
                        self.textbox.scroll_to_bottom()
                else:
                    # no active choice panel -> normal VN advance controls
                    if e.key in (pygame.K_SPACE, pygame.K_RETURN):
                        self.textbox.on_player_press()
                    elif e.key == pygame.K_PAGEUP:
                        self.textbox.scroll(-self.textbox.viewport_height * self.cfg.input.page_scroll_frac)
                    elif e.key == pygame.K_PAGEDOWN:
                        self.textbox.scroll(+self.textbox.viewport_height * self.cfg.input.page_scroll_frac)
                    elif e.key == pygame.K_HOME:
                        self.textbox.scroll_to_top()
                    elif e.key == pygame.K_END:
                        self.textbox.scroll_to_bottom()

            elif e.type == pygame.MOUSEMOTION:
                if self.textbox.choice_active():
                    self.textbox.choice_hover_at(e.pos)

            elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                if self.textbox.choice_active():
                    idx = self.textbox.choice_click(e.pos)
                    if idx is not None:
                        self.presenter.submit_choice_index(idx)
                else:
                    self.textbox.on_player_press()

            elif e.type == pygame.MOUSEWHEEL:
                self.textbox.scroll(-e.y * self.cfg.input.scroll_wheel_pixels)
            elif e.type == pygame.VIDEORESIZE:
                self.screen = pygame.display.set_mode((e.w, e.h), pygame.RESIZABLE)
                self.textbox.on_resize(compute_centered_rect(self.screen, self.cfg.textbox.width_frac, self.cfg.textbox.height_frac))
                
    def update(self, dt: float):
        # Function to run on delta time to update game state. 
        self.presenter.update(dt)
        self.textbox.update(dt)
        self.bg.update(dt)
        # pass
    
    def draw(self):
        self.bg.draw(self.screen, self.screen.get_rect())
        self.textbox.draw(self.screen)
        fps = int(self.clock.get_fps())
        hud = self.hud_font.render(f"{fps} FPS", True, (180, 180, 180))
        self.screen.blit(hud, (8, 6))
        pygame.display.flip()
        
    def run(self):
        while self.running:
            dt = self.clock.tick(self.cfg.fps) / 1000.0
            self.handle_input()
            self.update(dt)
            self.draw()
        pygame.quit()