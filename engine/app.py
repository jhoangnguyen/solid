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
            "Resize window to reflow.\n" + ("Lorem ipsum " * 120)
        )
        # self.textbox.set_text("Hello! This box can fade and re-theme.\n\nScroll me.")
        # self.textbox.append_text("HORIZON")
        
        # fade-in on start
        # self.textbox.opacity = 0.0
        # self.anim.add(Tween(self.textbox, "opacity", 0.0, 1.0, 0.35))

        # prepare an alternate theme (pretend another screen)
        # self.alt_theme = self.styles.current.derive(
        #     box_bg=(32, 12, 38), box_border=(120, 60, 130), text_rgb=(245, 230, 255)
        # )
        
        self.hud_font = pygame.font.Font(None, 24)
        
    def handle_input(self):
        # for e in pygame.event.get():
        #     if e.type == pygame.QUIT: self.running = False
        #     elif e.type == pygame.KEYDOWN:
        #         if e.key == pygame.K_ESCAPE: self.running = False
        #         elif e.key == pygame.K_t:
        #             # toggle theme with a quick fade to mask the recolor
        #             self.anim.add(Tween(self.textbox, "opacity", self.textbox.opacity, 0.0, 0.15,
        #                                 on_done=lambda: self.textbox.set_theme(self.alt_theme)))
        #             self.anim.add(Tween(self.textbox, "opacity", 0.0, 1.0, 0.15))
        #         elif e.key == pygame.K_F1:
        #             # demo slide-in: animate padding top for a “drop” effect
        #             top, r, b, l = self.styles.current.padding
        #             new_theme = self.styles.current.derive(padding=(top+40, r, b, l))
        #             self.textbox.set_theme(new_theme)
        #             self.anim.add(Tween(self.textbox, "opacity", 0.6, 1.0, 0.2))
        #     elif e.type == pygame.MOUSEWHEEL:
        #         self.textbox.scroll(-e.y * 40)
        #     elif e.type == pygame.VIDEORESIZE:
        #         self.screen = pygame.display.set_mode((e.w, e.h), pygame.RESIZABLE)
        #         self.textbox.on_resize(compute_centered_rect(self.screen, 0.4, 0.8))
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