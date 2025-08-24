from __future__ import annotations

import pygame
from typing import Optional

from engine.settings import AppCfg  # type: ignore[import]
from engine.resources import after_display_init
from engine.scene import SceneManager  # your stack from engine/scene.py

from game.scenes.title import TitleScene
from game.scenes.novel import NovelScene


class GameApp:
    """
    Minimal app shell that delegates input/update/draw to the active scene
    via SceneManager. It keeps global concerns (window init, vsync/fps, resize).
    """

    def __init__(self, cfg: AppCfg):
        self.cfg = cfg
        pygame.init()
        pygame.display.set_caption(cfg.window.title)

        # Window/display
        self._flags = pygame.RESIZABLE | pygame.DOUBLEBUF
        self.screen = pygame.display.set_mode(
            (int(cfg.window.width), int(cfg.window.height)),
            flags=self._flags,
        )
        after_display_init()  # make sure cached surfaces are display-ready

        # Core loop
        self.clock = pygame.time.Clock()
        self.running = True

        # Scene stack
        self.scenes = SceneManager(self.screen)

        # Boot on Title; switch to Novel from inside TitleScene (any key/click)
        self.scenes.push(TitleScene(self.scenes))
        # self.scenes.push(NovelScene(self.scenes))

    # ------------------------------------------------------------------ #
    # Main loop
    # ------------------------------------------------------------------ #
    def run(self) -> None:
        while self.running and not getattr(self.scenes, "request_quit", False):
            dt = self.clock.tick(self.cfg.fps) / 1000.0

            # ---- event pump -------------------------------------------------
            for e in pygame.event.get():
                # App-level quit
                if e.type == pygame.QUIT:
                    self.running = False
                    break

                # App-level resize: update display first, then forward event
                if e.type == pygame.VIDEORESIZE:
                    self._resize_to(e.w, e.h)
                    # Let the active scene also handle re-layout, etc.
                    _ = self.scenes.handle_event(e)
                    continue

                # Forward to active scene; consume if handled
                consumed = self.scenes.handle_event(e)
                if consumed:
                    continue

                # Global hotkeys
                if e.type == pygame.KEYDOWN:
                    if e.key == pygame.K_F11:
                        self._toggle_fullscreen()
                        continue
                    if (e.key == pygame.K_q) and (pygame.key.get_mods() & pygame.KMOD_CTRL):
                        self.running = False
                        continue

            # ---- update/draw -----------------------------------------------
            self.scenes.update(dt)
            self.scenes.draw()
            pygame.display.flip()

        pygame.quit()

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _resize_to(self, w: int, h: int) -> None:
        """Recreate the window surface and update the SceneManager's screen."""
        w = max(1, int(w))
        h = max(1, int(h))
        self.screen = pygame.display.set_mode((w, h), flags=self._flags)
        # keep SceneManager in sync
        self.scenes.screen = self.screen

    def _toggle_fullscreen(self) -> None:
        """Simple fullscreen toggle with F11."""
        # pygame-ce supports toggle_fullscreen(); fall back to manual toggle
        try:
            pygame.display.toggle_fullscreen()
        except Exception:
            # Manual toggle using flags
            current_flags = pygame.display.get_surface().get_flags()
            is_full = bool(current_flags & pygame.FULLSCREEN)
            if is_full:
                self._flags = pygame.RESIZABLE | pygame.SCALED | pygame.DOUBLEBUF
                self.screen = pygame.display.set_mode(
                    self.screen.get_size(), flags=self._flags
                )
            else:
                self._flags = pygame.FULLSCREEN | pygame.SCALED | pygame.DOUBLEBUF
                self.screen = pygame.display.set_mode((0, 0), flags=self._flags)
            self.scenes.screen = self.screen
