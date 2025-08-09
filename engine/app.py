import pygame
from dataclasses import dataclass
from engine.ui.style import Theme, StyleContext, compute_centered_rect
from engine.ui.widgets.textbox import TextBox
from engine.ui.anim import Animator, Tween
from engine.settings import load_settings, AppCfg

"""
Game Config that will be auto-instantiated with @dataclass.
NOTE: Currently hardcoding the window size, game title, background color, and the fps.
"""
# @dataclass
# class GameConfig:
#     width: int = 1200 
#     height: int = 720
#     title: str = "HORIZON"
#     bg_rgb: tuple[int, int, int] = (14, 15, 18)
#     fps: int = 60
    
    
class GameApp:
    def __init__(self, cfg: AppCfg):
        self.cfg = cfg
        pygame.init()
        pygame.display.set_caption(cfg.window.title)
        self.screen = pygame.display.set_mode((cfg.window.width, cfg.window.height), pygame.RESIZABLE)
        self.clock = pygame.time.Clock()
        self.running = True

        # styles + animator
        # self.styles = StyleContext(Theme())
        self.anim = Animator()
        self.theme = Theme()

        # textbox
        tb_rect = compute_centered_rect(self.screen, cfg.textbox.width_frac, cfg.textbox.height_frac)
        self.textbox = TextBox(tb_rect, self.theme)
        self.textbox.set_text(
            "Centered scrolling textbox.\n"
            "Mouse wheel / PgUp / PgDn / Home / End.\n\n"
            "Resize window to reflow.\n" + ("Lorem ipsum " * 500)
        )
        self.hud_font = pygame.font.Font(None, 24)
        
    def handle_input(self):
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                self.running = False
            elif e.type == pygame.KEYDOWN:
                if e.key == pygame.K_ESCAPE:
                    self.running = False
                elif e.key == pygame.K_PAGEUP:
                    page = self.textbox.viewport_height * self.cfg.input.page_scroll_frac
                    self.textbox.scroll(-page)
                elif e.key == pygame.K_PAGEDOWN:
                    page = self.textbox.viewport_height * self.cfg.input.page_scroll_frac
                    self.textbox.scroll(+page)
                elif e.key == pygame.K_HOME:
                    self.textbox.scroll_to_top()
                elif e.key == pygame.K_END:
                    self.textbox.scroll_to_bottom()
            elif e.type == pygame.MOUSEWHEEL:
                self.textbox.scroll(-e.y * self.cfg.input.scroll_wheel_pixels)
            elif e.type == pygame.VIDEORESIZE:
                self.screen = pygame.display.set_mode((e.w, e.h), pygame.RESIZABLE)
                new_rect = compute_centered_rect(
                    self.screen, self.cfg.textbox.width_frac, self.cfg.textbox.height_frac
                )
                self.textbox.on_resize(new_rect)
                
    def update(self, dt: float):
        # Function to run on delta time to update game state. Will be blank for now.
        # self.anim.update(dt)
        pass
    
    def draw(self):
        # self.screen.fill(self.cfg.bg_rgb)
        # self.textbox.draw(self.screen)
        # pygame.display.flip()
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