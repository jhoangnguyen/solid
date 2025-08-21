from __future__ import annotations
from dataclasses import dataclass
from typing import Callable, Optional, Dict, List
import pygame


@dataclass
class WindowStyle:
    radius: int = 12
    bg_rgba: tuple[int, int, int, int] = (22, 24, 28, 235)
    border_rgb: tuple[int, int, int] = (255, 255, 255)
    border_px: int = 1
    shadow: bool = True
    shadow_alpha: int = 120
    shadow_pad: int = 8

    title_h: int = 34
    title_bg_rgba: tuple[int, int, int, int] = (30, 34, 40, 255)
    title_rgb: tuple[int, int, int] = (235, 235, 235)
    title_pad_x: int = 12
    title_pad_y: int = 6

    close_w: int = 24
    close_h: int = 20
    close_pad_right: int = 8


class ModalWindow:
    """
    Minimal draggable window:
      - Rounded panel + title bar + close [X]
      - Drag by title bar
      - ESC or clicking [X] closes the window
      - Optional content_draw(surface, content_rect) callback
    """
    def __init__(
        self,
        id: str,
        rect: pygame.Rect,
        title: str = "Window",
        *,
        theme=None,
        content_draw: Optional[Callable[[pygame.Surface, pygame.Rect], None]] = None,
        style: Optional[WindowStyle] = None,
        draggable: bool = True,
    ):
        self.id = id
        self.rect = rect.copy()
        self.title = title
        self.theme = theme
        self.style = style or WindowStyle()
        self.content_draw = content_draw
        self.draggable = draggable

        self.visible = True
        self._dragging = False
        self._drag_dx = 0
        self._drag_dy = 0
        self._close_rect = pygame.Rect(0, 0, self.style.close_w, self.style.close_h)

        # Font: prefer theme font if present
        size = max(12, int(getattr(getattr(theme, "font_size", None), "__int__", lambda: 18)()))
        path = getattr(theme, "font_path", None) if theme else None
        self._font = pygame.font.Font(path, size)

    # ----- input -----
    def handle_event(self, e: pygame.event.Event) -> bool:
        if not self.visible:
            return False

        if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
            self.visible = False
            return True

        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            if self._close_rect.collidepoint(e.pos):
                self.visible = False
                return True
            if self._title_rect().collidepoint(e.pos):
                if self.draggable:
                    self._dragging = True
                    mx, my = e.pos
                    self._drag_dx = mx - self.rect.x
                    self._drag_dy = my - self.rect.y
                    return True

        if e.type == pygame.MOUSEBUTTONUP and e.button == 1:
            if self._dragging:
                self._dragging = False
                return True

        if e.type == pygame.MOUSEMOTION and self._dragging:
            mx, my = e.pos
            self.rect.x = mx - self._drag_dx
            self.rect.y = my - self._drag_dy
            return True

        return False

    # ----- draw -----
    def draw(self, surface: pygame.Surface) -> None:
        if not self.visible:
            return
        st = self.style
        r = self.rect

        # Drop shadow
        if st.shadow:
            sh = pygame.Surface((r.w + st.shadow_pad * 2, r.h + st.shadow_pad * 2), pygame.SRCALPHA)
            pygame.draw.rect(
                sh, (0, 0, 0, st.shadow_alpha), sh.get_rect(), border_radius=st.radius + 2
            )
            surface.blit(sh, (r.x - st.shadow_pad, r.y - st.shadow_pad))

        # Body
        pygame.draw.rect(surface, st.bg_rgba, r, border_radius=st.radius)
        pygame.draw.rect(surface, st.border_rgb, r, width=st.border_px, border_radius=st.radius)

        # Title bar
        trect = self._title_rect()
        pygame.draw.rect(
            surface, st.title_bg_rgba, trect, border_radius=st.radius, border_top_left_radius=st.radius, border_top_right_radius=st.radius
        )

        # Title text
        title_surf = self._font.render(self.title, True, st.title_rgb)
        tx = trect.x + st.title_pad_x
        ty = trect.y + (trect.h - title_surf.get_height()) // 2
        surface.blit(title_surf, (tx, ty))

        # Close button
        self._close_rect = pygame.Rect(
            trect.right - st.close_pad_right - st.close_w,
            trect.y + (trect.h - st.close_h) // 2,
            st.close_w, st.close_h
        )
        self._draw_close(surface, self._close_rect)

        # Content
        content = pygame.Rect(
            r.x + st.title_pad_x,
            trect.bottom + st.title_pad_y,
            r.w - 2 * st.title_pad_x,
            r.h - st.title_h - 2 * st.title_pad_y,
        )
        if self.content_draw:
            self.content_draw(surface, content)

    # ----- helpers -----
    def _title_rect(self) -> pygame.Rect:
        return pygame.Rect(self.rect.x, self.rect.y, self.rect.w, self.style.title_h)

    def _draw_close(self, surface: pygame.Surface, rect: pygame.Rect) -> None:
        pygame.draw.rect(surface, (255, 255, 255), rect, width=1, border_radius=6)
        # Draw an 'X'
        pad = 5
        x1, y1 = rect.x + pad, rect.y + pad
        x2, y2 = rect.right - pad, rect.bottom - pad
        pygame.draw.line(surface, (255, 255, 255), (x1, y1), (x2, y2), 2)
        pygame.draw.line(surface, (255, 255, 255), (x1, y2), (x2, y1), 2)


class WindowManager:
    """
    Holds and draws multiple windows, forwards events, dims background when any are open.
    """
    def __init__(self, theme=None):
        self.theme = theme
        self._order: List[str] = []              # z-order (front = end)
        self._wins: Dict[str, ModalWindow] = {}

    def any_open(self) -> bool:
        return any(w.visible for w in self._wins.values())

    def get(self, id: str) -> Optional[ModalWindow]:
        return self._wins.get(id)
    
    def set_locked(self, id: str, locked: bool) -> None:
        w = self._wins.get(id)
        if w:
            w.draggable = not locked

    def add(self, win: ModalWindow) -> None:
        self._wins[win.id] = win
        if win.id in self._order:
            self._order.remove(win.id)
        self._order.append(win.id)

    def toggle(self, id: str, builder: Callable[[], ModalWindow]) -> None:
        w = self._wins.get(id)
        if w is None:
            w = builder()
            self.add(w)
        else:
            w.visible = not w.visible
            if w.visible:
                # bring to front
                if id in self._order:
                    self._order.remove(id)
                self._order.append(id)

    def close_top(self) -> None:
        for wid in reversed(self._order):
            w = self._wins.get(wid)
            if w and w.visible:
                w.visible = False
                return

    def handle_event(self, e: pygame.event.Event) -> bool:
        # ESC handled here too (closes topmost)
        if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE and self.any_open():
            self.close_top()
            return True
        # Top-most first
        for wid in reversed(self._order):
            w = self._wins.get(wid)
            if w and w.visible and w.handle_event(e):
                return True
        return False

    def draw(self, surface: pygame.Surface) -> None:
        if not self.any_open():
            return
        # Dimmer behind windows
        dim = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 100))
        surface.blit(dim, (0, 0))

        # Back-to-front
        for wid in self._order:
            w = self._wins.get(wid)
            if w and w.visible:
                w.draw(surface)

    def hit_test(self, pos: tuple[int, int]) -> bool:
        """True if the point is inside any visible window."""
        for wid in reversed(self._order):  # top-first if you ever need it
            w = self._wins.get(wid)
            if w and w.visible and w.rect.collidepoint(pos):
                return True
        return False