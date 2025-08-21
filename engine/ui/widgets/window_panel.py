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
        keep_centered: bool = False,
        center_x: bool = True,
        center_y: bool = True,
        resizable: bool = True,
        min_width: int = 180,
        min_height: int = 120,
        resize_border: int = 6, # Pixel thickness of the interactive edge zone
        dims_backdrop: bool = True,
    ):
        self.id = id
        self.rect = rect.copy()
        self.title = title
        self.theme = theme
        self.style = style or WindowStyle()
        self.content_draw = content_draw
        
        self.draggable = draggable
        self.keep_centered = keep_centered
        self.center_x = center_x
        self.center_y = center_y
        
        self.resizable = resizable
        self.min_width = max(1, min_width)
        self.min_height = max(1, min_height)
        self.resize_border = max(2, resize_border)
        self.visible = True
        
        self.dims_backdrop = dims_backdrop
        
        # Resize state
        self._resizing = False
        self._resize_edges = (False, False, False, False)  # (left, top, right, bottom)
        self._resize_start_mouse = (0, 0)
        self._resize_start_rect = self.rect.copy()
        
        # Optional: track cursor to avoid thrashing set_cursor calls
        self._cursor_shape = None
        
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
        
        # --- Hover cursor when not dragging/resizing ---
        if e.type == pygame.MOUSEMOTION and self.resizable and not self._dragging and not self._resizing:
            edges = self._edge_hit_test(e.pos)        
            self._set_system_cursor(self._edge_cursor(edges))

        if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
            self.visible = False
            return True

        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            # 1) Close button takes priority
            if self._close_rect.collidepoint(e.pos):
                self.visible = False
                return True

            # 2) Edge/corner resize (priority over drag)
            if self.resizable:
                edges = self._edge_hit_test(e.pos)
                if any(edges):
                    self._resizing = True
                    self._resize_edges = edges
                    self._resize_start_mouse = e.pos
                    self._resize_start_rect = self.rect.copy()
                    return True

            # 3) Title-bar drag
            if self._title_rect().collidepoint(e.pos):
                if self.draggable and not self.keep_centered:
                    self._dragging = True
                    mx, my = e.pos
                    self._drag_dx = mx - self.rect.x
                    self._drag_dy = my - self.rect.y
                return True  # always consume title clicks

            # 4) (optional) Clicks inside the window body should not fall through
            if self.rect.collidepoint(e.pos):
                return True

        elif e.type == pygame.MOUSEBUTTONUP and e.button == 1:
            if self._dragging:
                self._dragging = False
                return True
            if self._resizing:
                self._resizing = False
                self._set_system_cursor(None)            
                return True


        elif e.type == pygame.MOUSEMOTION: 
            if self._dragging:
                mx, my = e.pos
                self.rect.x = mx - self._drag_dx
                self.rect.y = my - self._drag_dy
                return True
            if self._resizing:
                self._apply_resize(e.pos, pygame.display.get_surface().get_size())
                return True

        return False

    # ----- draw -----
    def draw(self, surface: pygame.Surface) -> None:
        if self.keep_centered:
            sw, sh = surface.get_size()
            self._recenter(sw, sh)
            
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
            surface, st.title_bg_rgba, trect, border_radius=st.radius, border_top_left_radius=st.radius, border_top_right_radius=st.radius, border_bottom_left_radius=0, border_bottom_right_radius=0,
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
            
    def set_keep_centered(self, keep: bool, *, center_x: Optional[bool] = None, center_y: Optional[bool] = None) -> None:
        self.keep_centered = keep
        if center_x is not None:
            self.center_x = center_x
        if center_y is not None:
            self.center_y = center_y
        if keep:
            self._dragging = False

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
        
    def _recenter(self, sw: int, sh: int) -> None:
        # Center only on the requested axes
        if self.center_x:
            self.rect.x = (sw - self.rect.w) // 2
        if self.center_y:
            self.rect.y = (sh - self.rect.h) // 2

    def _edge_hit_test(self, pos: tuple[int, int]) -> tuple[bool, bool, bool, bool]:
        """Return which edges are active (L,T,R,B) for resizing at mouse pos."""
        x, y = pos
        r = self.rect
        b = self.resize_border
        on_left   = r.left <= x <= r.left + b
        on_right  = r.right - b <= x <= r.right
        on_top    = r.top <= y <= r.top + b
        on_bottom = r.bottom - b <= y <= r.bottom
        return (on_left, on_top, on_right, on_bottom)

    def _edge_cursor(self, edges: tuple[bool, bool, bool, bool]):
        """Map edges to a system cursor name if available."""
        l, t, r, b = edges
        # corners
        if (l and t) or (r and b):
            return "SIZENWSE"
        if (r and t) or (l and b):
            return "SIZENESW"
        # sides
        if l or r:
            return "SIZEWE"
        if t or b:
            return "SIZENS"
        return None

    def _set_system_cursor(self, shape: Optional[str]) -> None:
        """Best-effort system cursor switch; no-op if unsupported."""
        if shape == self._cursor_shape:
            return
        try:
            import pygame
            if shape is None:
                pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_ARROW)
            else:
                pygame.mouse.set_cursor(getattr(pygame, f"SYSTEM_CURSOR_{shape}"))
            self._cursor_shape = shape
        except Exception:
            # Ignore on platforms/backends without system cursors
            self._cursor_shape = None

    def _apply_resize(self, mouse: tuple[int, int], screen_size: tuple[int, int]) -> None:
        """Resize rect based on active edges and mouse delta, enforce min size + keep on-screen."""
        mx, my = mouse
        sw, sh = screen_size
        l, t, r, b = self._resize_edges
        start = self._resize_start_rect
        sx, sy = self._resize_start_mouse
        dx, dy = mx - sx, my - sy

        new_left   = start.left
        new_top    = start.top
        new_right  = start.right
        new_bottom = start.bottom

        if l:
            new_left = min(start.right - self.min_width, start.left + dx)
        if r:
            new_right = max(start.left + self.min_width, start.right + dx)
        if t:
            new_top = min(start.bottom - self.min_height, start.top + dy)
        if b:
            new_bottom = max(start.top + self.min_height, start.bottom + dy)

        # Clamp to screen bounds (optional but nice)
        new_left   = max(0, new_left)
        new_top    = max(0, new_top)
        new_right  = min(sw, new_right)
        new_bottom = min(sh, new_bottom)

        # Write back
        self.rect.update(new_left, new_top, new_right - new_left, new_bottom - new_top)

class WindowManager:
    """
    Holds and draws multiple windows, forwards events, dims background when any are open.
    """
    def __init__(self, theme=None):
        self.theme = theme
        self._order: List[str] = []              # z-order (front = end)
        self._wins: Dict[str, ModalWindow] = {}
        # Backdrop controls
        self.dim_background: bool = True
        self.background_rgba: tuple[int, int, int, int] = (0, 0, 0, 100)
        self._dim_surface: Optional[pygame.Surface] = None
        self._dim_size: tuple[int, int] = (0, 0)
        
    def set_backdrop(self, enabled: bool, rgba: Optional[tuple[int, int, int, int]] = None) -> None:
        """ Enable/disable global darkening; optionally change RGBA. """
        self.dim_background = enabled
        if rgba is not None:
            self.background_rgba = rgba
        self._dim_surface = None # Rebuild on next draw
        
    def set_dims_backdrop(self, id: str, dims: bool) -> None:
        """ Per-window override. """
        w = self._wins.get(id)
        if w:
            w.dims_backdrop = dims

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
        
        if not self.any_open():
            return
        # Optional dimmer behind windows
        if self._should_dim_background():
            self._draw_backdrop(surface=surface)

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
    
    def set_keep_centered(self, id: str, keep: bool, *, center_x: Optional[bool] = None, center_y: Optional[bool] = None) -> None:
        w = self._wins.get(id)
        if not w:
            return
        w.set_keep_centered(keep, center_x=center_x, center_y=center_y)
        
    def _should_dim_background(self) -> bool:
        if not self.dim_background:
            return False
        # Dim only if at least one visible window requests dimming
        return any(w.visible and getattr(w, "dims_backdrop", True) for w in self._wins.values())
    
    def _draw_backdrop(self, surface: pygame.Surface) -> None:
        size = surface.get_size()
        if self._dim_surface is None or self._dim_size != size:
            self._dim_surface = pygame.Surface(size, pygame.SRCALPHA)
            self._dim_size = size
        self._dim_surface.fill(self.background_rgba)
        surface.blit(self._dim_surface, (0, 0))