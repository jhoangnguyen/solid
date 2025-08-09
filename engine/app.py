import pygame
from dataclasses import dataclass
from engine.ui.style import Theme, StyleContext, compute_centered_rect
from engine.ui.widgets.textbox import TextBox
from engine.ui.anim import Animator, Tween

"""
Game Config that will be auto-instantiated with @dataclass.
NOTE: Currently hardcoding the window size, game title, background color, and the fps.
"""
@dataclass
class GameConfig:
    width: int = 1200 
    height: int = 720
    title: str = "HORIZON"
    bg_rgb: tuple[int, int, int] = (14, 15, 18)
    fps: int = 60
    
    
class GameApp:
    def __init__(self, cfg: GameConfig):
        self.cfg = cfg
        pygame.init()
        pygame.display.set_caption(cfg.title)
        self.screen = pygame.display.set_mode((cfg.width, cfg.height), pygame.RESIZABLE)
        self.clock = pygame.timeClock = pygame.time.Clock()
        self.running = True

        # styles + animator
        self.styles = StyleContext(Theme())
        self.anim = Animator()

        # textbox
        tb_rect = compute_centered_rect(self.screen, 0.7, 0.45)
        self.textbox = TextBox(tb_rect, self.styles.current)
        self.textbox.set_text("Hello! This box can fade and re-theme.\n\nScroll me.")

        # fade-in on start
        self.textbox.opacity = 0.0
        self.anim.add(Tween(self.textbox, "opacity", 0.0, 1.0, 0.35))

        # prepare an alternate theme (pretend another screen)
        self.alt_theme = self.styles.current.derive(
            box_bg=(32, 12, 38), box_border=(120, 60, 130), text_rgb=(245, 230, 255)
        )
        
        
    def handle_input(self):
            for e in pygame.event.get():
                if e.type == pygame.QUIT: self.running = False
                elif e.type == pygame.KEYDOWN:
                    if e.key == pygame.K_ESCAPE: self.running = False
                    elif e.key == pygame.K_t:
                        # toggle theme with a quick fade to mask the recolor
                        self.anim.add(Tween(self.textbox, "opacity", self.textbox.opacity, 0.0, 0.15,
                                            on_done=lambda: self.textbox.set_theme(self.alt_theme)))
                        self.anim.add(Tween(self.textbox, "opacity", 0.0, 1.0, 0.15))
                    elif e.key == pygame.K_F1:
                        # demo slide-in: animate padding top for a “drop” effect
                        top, r, b, l = self.styles.current.padding
                        new_theme = self.styles.current.derive(padding=(top+40, r, b, l))
                        self.textbox.set_theme(new_theme)
                        self.anim.add(Tween(self.textbox, "opacity", 0.6, 1.0, 0.2))
                elif e.type == pygame.MOUSEWHEEL:
                    self.textbox.scroll(-e.y * 40)
                elif e.type == pygame.VIDEORESIZE:
                    self.screen = pygame.display.set_mode((e.w, e.h), pygame.RESIZABLE)
                    self.textbox.on_resize(compute_centered_rect(self.screen, 0.7, 0.45))
                
    def update(self, dt: float):
        # Function to run on delta time to update game state. Will be blank for now.
        self.anim.update(dt)
    
    def draw(self):
        self.screen.fill(self.cfg.bg_rgb)
        self.textbox.draw(self.screen)
        pygame.display.flip()
        
    def run(self):
        while self.running:
            dt = self.clock.tick(self.cfg.fps) / 1000.0
            self.handle_input()
            self.update(dt)
            self.draw()
        pygame.quit()