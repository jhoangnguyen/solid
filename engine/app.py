import pygame
from dataclasses import dataclass

"""
Game Config that will be auto-instantiated with @dataclass.
NOTE: Currently hardcoding the window size, game title, background color, and the fps.
"""
@dataclass
class GameConfig:
    width: int = 1200 
    height: int = 720
    title: str = "Solid"
    bg_rgb: tuple[int, int, int] = (14, 15, 18)
    fps: int = 60
    
    
class GameApp:
    def __init__(self, cfg: GameConfig):
        self.cfg = cfg
        pygame.init()
        pygame.display.set_caption(cfg.title)
        self.screen = pygame.display.set_mode((cfg.width, cfg.height), pygame.RESIZABLE)
        self.clock = pygame.time.Clock()
        self.running = True
        
        self.font = pygame.font.Font(None, 28) # We'll use the default font from Pygame for now
        
        
    def handle_input(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                self.running = False
                
    def update(self, dt: float):
        # Function to run on delta time to update game state. Will be blank for now.
        pass
    
    def draw(self):
        self.screen.fill(self.cfg.bg_rgb)
        msg = self.font.render("Milestone 0 - Boot & Loop", True, (220, 220, 220))
        rect = msg.get_rect(center=self.screen.get_rect().center)
        self.screen.blit(msg, rect)
        pygame.display.flip()
        
    def run(self):
        while self.running:
            dt = self.clock.tick(self.cfg.fps) / 1000.0
            self.handle_input()
            self.update(dt)
            self.draw()
        pygame.quit()