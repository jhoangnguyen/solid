from __future__ import annotations
from typing import Optional, Tuple
import pygame

_BG_MODES = ("cover", "contain", "stretch", "center", "tile")

class ImageBrush:
    """
    Draw an image into any pygame.Rect with mode like CSS:
        - cover / contain (keep aspect)
        - stretch (ignore aspect)
        - center (no scale)
        - tile (repeat to fill)
    
    Supports rounded corners, padding/inset, and on optional tint overlay.
    """
    def __init__(self) -> None:
        self._orig: Optional[pygame.Surface] = None
        self._mode: str = "cover"
        self.enabled: bool = True
        self.tint_rgba: Optional[Tuple[int, int, int, int]] = None
        self.radius: int = 0 # Rounded corners
        self.border_color: Optional[Tuple[int, int, int, int]] = None
        self.border_width: int = 1
        self.inset: Tuple[int, int, int, int] = (0, 0, 0, 0) # t, r, b, l
        
        # Simple internal cache keyed by (w, h, mode)
        self._cache_size: Tuple[int, int] = (0, 0)
        self._cache_mode: str = ""
        self._cache_surf: Optional[pygame.Surface] = None
        
    # ----- Config -----
    def set_image(self, path: Optional[str]) -> None:
        if not path:
            self._orig = None
            self._cache_surf = None
            return
        self._orig = pygame.image.load(path).convert_alpha()
        self._cache_surf = None
        
    def set_mode(self, mode: str) -> None:
        if mode not in _BG_MODES:
            raise ValueError(f"mode must be one of {_BG_MODES}")
        if mode != self._mode:
            self._mode = mode
            self._cache_surf = None
            
    # ----- Drawing -----
    def draw(self, surface: pygame.Surface, rect: pygame.Rect) -> None:
        if not self.enabled or self._orig is None or rect.w <= 0 or rect.h <= 0:
            return
        
        # Apply inset (inner content rect)
        it, ir, ib, il = self.inset
        inner = pygame.Rect(rect.x + il, rect.y + it,
                            max(0, rect.w - (il + ir)), 
                            max(0, rect.h - (it + ib)))
        if inner.w <= 0 or inner.h <= 0:
            return
        
        # Prepare a target surface exactly the size of the inner rect
        # we'll clip the image to rounded corners here
        target = pygame.Surface((inner.w, inner.h), pygame.SRCALPHA)
        
        # Build the image content on `content`
        content = self._build_content((inner.w, inner.h)).copy()
        
        # Mask for rounded corner (if any)
        if self.radius > 0:
            mask = pygame.Surface((inner.w, inner.h), pygame.SRCALPHA)
            pygame.draw.rect(mask, (255, 255, 255, 255), mask.get_rect(), border_radius=self.radius)
            # Multiply alpha so corners become transparent
            # content = content.copy()
            content.blit(mask, (0,0), special_flags=pygame.BLEND_RGBA_MULT)
        
        # Optional tint overlay (applies after masking)
        if self.tint_rgba:
            tint = pygame.Surface((inner.w, inner.h), pygame.SRCALPHA)
            tint.fill(self.tint_rgba)
            content.blit(tint, (0, 0))
        
        # Blit to destination
        surface.blit(content, inner.topleft)
        
        # Optional border
        if self.border_color and self.border_width > 0:
            pygame.draw.rect(surface, self.border_color, inner, width= self.border_width, border_radius=self.radius)
            
    # ---------- internals ----------
    def _build_content(self, size: Tuple[int,int]) -> pygame.Surface:
        """Return an image the size of `size`, composed per mode."""
        assert self._orig is not None
        w, h = size

        # tile mode doesn't benefit from cache by size; build each time
        if self._mode == "tile":
            tile = self._orig
            tw, th = tile.get_size()
            out = pygame.Surface((w, h), pygame.SRCALPHA)
            y = 0
            while y < h:
                x = 0
                while x < w:
                    out.blit(tile, (x, y))
                    x += tw
                y += th
            return out

        # cover/contain/stretch/center can cache by size+mode
        if self._cache_surf is not None and self._cache_size == (w, h) and self._cache_mode == self._mode:
            return self._cache_surf

        iw, ih = self._orig.get_size()

        if self._mode == "stretch":
            scaled = pygame.transform.smoothscale(self._orig, (w, h))
            out = scaled
        elif self._mode == "center":
            out = pygame.Surface((w, h), pygame.SRCALPHA)
            x = (w - iw) // 2
            y = (h - ih) // 2
            out.blit(self._orig, (x, y))
        else:
            # cover / contain (keep aspect)
            s_cover = max(w / iw, h / ih)
            s_contain = min(w / iw, h / ih)
            s = s_cover if self._mode == "cover" else s_contain
            tw, th = max(1, int(iw * s)), max(1, int(ih * s))
            scaled = pygame.transform.smoothscale(self._orig, (tw, th))
            out = pygame.Surface((w, h), pygame.SRCALPHA)
            x = (w - tw) // 2
            y = (h - th) // 2
            out.blit(scaled, (x, y))

        # update cache
        self._cache_surf = out
        self._cache_size = (w, h)
        self._cache_mode = self._mode
        return out