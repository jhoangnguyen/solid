from __future__ import annotations
from typing import Optional
import pygame
from engine.scene import Scene, SceneManager
from game.scenes.novel import NovelScene
from engine.settings import load_ui_defaults, build_theme_from_defaults
from engine.ui.fonts import FontCache


class TitleScene(Scene):
    def __init__(self, mgr: SceneManager, font: pygame.font.Font | None = None):
        self.mgr = mgr
        defaults = load_ui_defaults("game/config/defaults.yaml")
        self.theme = build_theme_from_defaults(defaults=defaults)
        self.fonts = FontCache()
        self.font = font or self.fonts.get(self.theme.font_path, 72)
        self.small = self.fonts.get(self.theme.font_path, 28)
        self.blink = 0.0

    # --- lifecycle ---
    def on_enter(self, prev: Optional[Scene]) -> None:
        pass

    def on_exit(self, nxt: Optional[Scene]) -> None:
        pass

    def on_pause(self) -> None:
        pass

    def on_resume(self) -> None:
        pass

    # --- loop ---
    def handle_event(self, e: pygame.event.Event) -> bool:
        if e.type == pygame.KEYDOWN:
            # Any key to start
            self.mgr.replace(NovelScene(self.mgr))
            return True
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            self.mgr.replace(NovelScene(self.mgr))
            return True
        return False

    def update(self, dt: float) -> None:
        self.blink = (self.blink + dt) % 1.2

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill((18, 20, 24))
        w, h = surface.get_size()
        title = self.font.render("HORIZON", True, (235, 235, 240))
        tip = self.small.render("Press any key to start", True, (180, 182, 190))

        surface.blit(title, title.get_rect(center=(w//2, h//2 - 40)))
        # soft blink
        if self.blink < 0.8:
            surface.blit(tip, tip.get_rect(center=(w//2, h//2 + 40)))
