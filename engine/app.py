import pygame
from dataclasses import dataclass
from engine.ui.style import Theme, StyleContext, compute_centered_rect, WaitIndicatorStyle
from engine.ui.widgets.text_box import TextBox, RevealParams
from engine.ui.anim import Animator, Tween
from engine.settings import load_settings, AppCfg
from engine.narrative.loader import load_story_file
from engine.narrative.presenter import NodePresenter

class GameApp:
    def __init__(self, cfg: AppCfg):
        self.cfg = cfg
        pygame.init()
        pygame.display.set_caption(cfg.window.title)
        self.screen = pygame.display.set_mode((cfg.window.width, cfg.window.height), pygame.RESIZABLE)
        self.clock = pygame.time.Clock()
        self.running = True

        self.anim = Animator()
        theme = Theme()
        theme.wait_indicator = WaitIndicatorStyle(
            char="\u25BC",
            font_path="game/assets/fonts/NotoSansSymbols2-Regular.ttf",
            color=(255, 255, 255),
            period=1.0,
            offset_x=6, offset_y=1, scale=0.5
        )
        self.theme = theme

        # textbox
        tb_rect = compute_centered_rect(self.screen, cfg.textbox.width_frac, cfg.textbox.height_frac)
        self.textbox = TextBox(tb_rect, self.theme, reveal=RevealParams(
            per_line_delay=cfg.reveal.per_line_delay,
            intro_duration=cfg.reveal.intro_duration,
            intro_offset_px=cfg.reveal.intro_offset_px,
            stick_to_bottom_threshold_px=cfg.reveal.stick_to_bottom_threshold_px,
        ))
        
        # --- load YAML ---
        story_path = "game/content/prologue.yaml"
        self.story = load_story_file(story_path)
        self.current_node_id = self.story.start
        
        self.presenter = NodePresenter(self.textbox, self.story)
        self.presenter.show_node(self.story.nodes[self.current_node_id])
        
        self.hud_font = pygame.font.Font(None, 24)
    
    # def handle_input(self):
    #     for e in pygame.event.get():
    #         if e.type == pygame.QUIT: 
    #             self.running = False
    #         elif e.type == pygame.KEYDOWN:
    #             if e.key == pygame.K_ESCAPE: 
    #                 self.running = False
    #             elif e.key in (pygame.K_SPACE, pygame.K_RETURN):
    #                 self.textbox.on_player_press()
    #             elif e.key == pygame.K_PAGEUP:
    #                 self.textbox.scroll(-self.textbox.viewport_height * self.cfg.input.page_scroll_frac)
    #             elif e.key == pygame.K_PAGEDOWN:
    #                 self.textbox.scroll(+self.textbox.viewport_height * self.cfg.input.page_scroll_frac)
    #             elif e.key == pygame.K_HOME: self.textbox.scroll_to_top()
    #             elif e.key == pygame.K_END: self.textbox.scroll_to_bottom()
    #         elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
    #             self.textbox.on_player_press()
    #         elif e.type == pygame.MOUSEWHEEL:
    #             self.textbox.scroll(-e.y * self.cfg.input.scroll_wheel_pixels)
    #         elif e.type == pygame.VIDEORESIZE:
    #             self.screen = pygame.display.set_mode((e.w, e.h), pygame.RESIZABLE)
    #             self.textbox.on_resize(compute_centered_rect(self.screen, self.cfg.textbox.width_frac, self.cfg.textbox.height_frac))
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
        # pass
    
    def draw(self):
        self.screen.fill(self.cfg.window.bg_rgb)
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