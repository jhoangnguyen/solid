from __future__ import annotations
from typing import Optional, Protocol, List
import pygame


class Scene(Protocol):
    """Lightweight scene protocol with no inheritance burden."""
    # Lifecycle
    def on_enter(self, prev: Optional["Scene"]) -> None: ...
    def on_exit(self,  nxt: Optional["Scene"]) -> None: ...
    def on_pause(self) -> None: ...
    def on_resume(self) -> None: ...

    # Loop
    def update(self, dt: float) -> None: ...
    def draw(self, surface: pygame.Surface) -> None: ...
    def handle_event(self, e: pygame.event.Event) -> bool: ...


class SceneManager:
    """
    Simple stack:
      - push(scene) adds and enters the scene (pauses old top)
      - pop() exits the top and resumes the new top
      - replace(scene) = pop + push
      - update() updates only the top scene
      - draw() draws the whole stack (bottom->top) so overlays are possible
      - handle_event() routes events to top; return True if consumed
    """
    def __init__(self, screen: pygame.Surface) -> None:
        self._stack: List[Scene] = []
        self.screen = screen
        self.request_quit = False

    # ----- stack ops --------------------------------------------------------
    def push(self, scene: Scene) -> None:
        prev = self._stack[-1] if self._stack else None
        if prev:
            prev.on_pause()
        self._stack.append(scene)
        scene.on_enter(prev)

    def pop(self) -> Optional[Scene]:
        if not self._stack:
            return None
        top = self._stack.pop()
        nxt = self._stack[-1] if self._stack else None
        top.on_exit(nxt)
        if nxt:
            nxt.on_resume()
        return top

    def replace(self, scene: Scene) -> None:
        self.pop()
        self.push(scene)

    def clear(self) -> None:
        while self._stack:
            self.pop()

    # ----- loop -------------------------------------------------------------
    def active(self) -> Optional[Scene]:
        return self._stack[-1] if self._stack else None

    def handle_event(self, e: pygame.event.Event) -> bool:
        top = self.active()
        if top:
            return bool(top.handle_event(e))
        return False

    def update(self, dt: float) -> None:
        top = self.active()
        if top:
            top.update(dt)

    def draw(self) -> None:
        # draw full stack bottom -> top (supports overlay scenes)
        for s in self._stack:
            s.draw(self.screen)
