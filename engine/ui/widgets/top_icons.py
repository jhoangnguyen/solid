from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Optional, Iterable
import pygame
from engine.ui.style import Theme

@dataclass
class IconButton:
    id: str
    image_path: Optional[str] = None   # path OR
    surface: Optional[pygame.Surface] = None  # preloaded Surface (wins if provided)
    tooltip: str = ""                  # (not drawn yet, kept for future)
    
class TopIcons:
    """
    Fixed strip of N icons aligned to the top-right corner.
    - Hover highlight + simple pressed tint
    - Hit-test + get_clicked() for collision routing
    - Images can be supplied as file paths or Surfaces; scaled to fit
    """
    def __init__(self, theme: Theme, count: int = 3):
        self.theme = theme
        self._icons: Dict[str, IconButton] = {}   # id -> IconButton
        self._order: list[str] = []               # visual order left->right
        self._hit_rects: Dict[str, pygame.Rect] = {}
        self._hover_id: Optional[str] = None
        self._down_id: Optional[str] = None
        self._count = int(count)
        
        size_frac: float | None = None          # 0..1 of screen height
        margin_frac: float | None = None        # 0..1 of screen height
        gap_frac: float | None = None           # 0..1 of screen height
        ring_px_frac: float | None = None       # 0..1 of screen height
        corner_radius_frac: float | None = None # 0..1 of *icon size*

    # -------- public API ----------
    def set_icons(self, icons: Iterable[IconButton]) -> None:
        self._icons.clear()
        self._order.clear()
        for ic in icons:
            self._icons[ic.id] = ic
            self._order.append(ic.id)
        # allow fewer than count; we’ll draw as many as provided
        self._order = self._order[: self._count]

    def set_icon(self, ic: IconButton) -> None:
        if ic.id not in self._order:
            self._order.append(ic.id)
            self._order = self._order[: self._count]
        self._icons[ic.id] = ic

    def on_mouse_move(self, pos: tuple[int,int]) -> None:
        # update hover id
        self._hover_id = None
        for sid, r in self._hit_rects.items():
            if r.collidepoint(pos):
                self._hover_id = sid
                break

    def hit_test(self, pos: tuple[int,int]) -> bool:
        # any rect matches?
        for r in self._hit_rects.values():
            if r.collidepoint(pos):
                return True
        return False

    def get_clicked(self, pos: tuple[int,int]) -> Optional[str]:
        # single-click behavior on mousedown
        for sid, r in self._hit_rects.items():
            if r.collidepoint(pos):
                self._down_id = sid
                return sid
        return None

    def on_mouse_up(self) -> None:
        self._down_id = None

    # -------- drawing ----------
    def draw(self, surface: pygame.Surface) -> None:
        ti = getattr(self.theme, "top_icons", None)
        sw, sh = surface.get_size()

        def clamp(v, lo, hi): return max(lo, min(hi, v))

        # Prefer fractions (of screen height), else pixels
        if ti and ti.size_frac is not None:
            size = int(clamp(ti.size_frac, 0.04, 0.25) * sh)
        else:
            size = int(ti.size_px if ti else 48)

        if ti and ti.margin_frac is not None:
            margin = int(clamp(ti.margin_frac, 0.0, 0.2) * sh)
        else:
            margin = int(ti.margin_px if ti else 12)

        if ti and ti.gap_frac is not None:
            gap = int(clamp(ti.gap_frac, 0.0, 0.15) * sh)
        else:
            gap = int(ti.gap_px if ti else 10)

        ring_rgba = ti.ring_rgba if ti else (255, 255, 255, 180)
        if ti and ti.ring_px_frac is not None:
            ring_px = max(1, int(clamp(ti.ring_px_frac, 0.0, 0.05) * sh))
        else:
            ring_px = int(ti.ring_px if ti else 2)

        # Corner radius: fraction of icon size (looks nicer)
        if ti and ti.corner_radius_frac is not None:
            radius = max(0, int(clamp(ti.corner_radius_frac, 0.0, 0.5) * size))
        else:
            radius = int(ti.corner_radius if ti else 8)

        hover_rgba = ti.hover_tint_rgba if ti else (255, 255, 255, 40)
        down_rgba  = ti.down_tint_rgba  if ti else (255, 255, 255, 80)

        # layout left->right but anchored to top-right
        n = len(self._order)
        total_w = n * size + max(0, n - 1) * gap
        x0 = sw - margin - total_w
        y  = margin

        self._hit_rects.clear()
        for i, sid in enumerate(self._order):
            rect = pygame.Rect(x0 + i * (size + gap), y, size, size)
            self._hit_rects[sid] = rect
            ic = self._icons.get(sid)
            img = self._resolve_image(ic)

            if img:
                fitted = self._fit_surface(img, size, size)
                ix = rect.x + (rect.w - fitted.get_width()) // 2
                iy = rect.y + (rect.h - fitted.get_height()) // 2
                surface.blit(fitted, (ix, iy))
            else:
                ph = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
                pygame.draw.rect(ph, (255,255,255,32), ph.get_rect(), border_radius=radius)
                surface.blit(ph, rect.topleft)

            ov = pygame.Surface(rect.size, pygame.SRCALPHA)
            if sid == self._down_id and down_rgba[3] > 0:
                pygame.draw.rect(ov, down_rgba, ov.get_rect(), border_radius=radius)
            elif sid == self._hover_id and hover_rgba[3] > 0:
                pygame.draw.rect(ov, hover_rgba, ov.get_rect(), border_radius=radius)
            if ring_px > 0 and ring_rgba[3] > 0 and (sid == self._hover_id or sid == self._down_id):
                pygame.draw.rect(ov, ring_rgba, ov.get_rect(), width=ring_px, border_radius=radius)
            surface.blit(ov, rect.topleft)

    # -------- helpers ----------
    def _resolve_image(self, ic: Optional[IconButton]) -> Optional[pygame.Surface]:
        if not ic:
            return None
        if ic.surface is not None:
            return ic.surface
        if ic.image_path:
            try:
                return pygame.image.load(ic.image_path).convert_alpha()
            except Exception:
                return None
        return None

    def _fit_surface(self, surf: pygame.Surface, max_w: int, max_h: int) -> pygame.Surface:
        sw, sh = surf.get_size()
        if sw <= 0 or sh <= 0:
            return surf
        # contain w/ small padding
        pad = max(1, int(min(max_w, max_h) * 0.1))
        avail_w, avail_h = max_w - pad*2, max_h - pad*2
        scale = min(avail_w / sw, avail_h / sh, 1.0)
        tw, th = max(1, int(sw * scale)), max(1, int(sh * scale))
        return pygame.transform.smoothscale(surf, (tw, th))