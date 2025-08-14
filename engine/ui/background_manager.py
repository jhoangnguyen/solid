from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Tuple, Any
import pygame
from engine.ui.brushes.image_brush import ImageBrush

@dataclass(frozen=True)
class BackgroundSpec:
    image_path: Optional[str] = None
    mode: str = "cover"                 # cover | contain | stretch | center | tile
    tint_rgba: Optional[Tuple[int, int, int, int]] = None
    
    @staticmethod
    def from_any(v: Any) -> "BackgroundSpec":
        if v is None:
            return BackgroundSpec(None)
        if isinstance(v, str):
            return BackgroundSpec(image_path=v)
        if isinstance(v, dict):
            return BackgroundSpec(
                image_path=v.get("image_path") or v.get("path") or v.get("file"),
                mode=v.get("mode", "cover"),
                tint_rgba=tuple(v["tint_rgba"] if v.get("tint_rgba") is not None else None)
            )
        raise TypeError(f"Unsupported bg spec: {type(v)}")
    
class BackgroundManager:
    """ Owns the window background, supports seamless crossfades. """
    def __init__(self) -> None:
        self._current = ImageBrush()
        self._next: Optional[ImageBrush] = None
        self._fade_t = 0.0
        self._fade_dur = 0.0
        self._active = False
        self._last_key: Optional[tuple] = None # (path, mode, tint)
        
    def _apply_spec(self, brush: ImageBrush, spec: BackgroundSpec) -> None:
        brush.set_image(spec.image_path)
        brush.set_mode(spec.mode)
        brush.tint_rgba = spec.tint_rgba
        
    def set(self, spec_any: Any, *, transition: str = "crossfade", duration: float = 0.35) -> None:
        """ Set background from YAML spec. If none, do nothing. """
        if spec_any is None:
            return
        spec = BackgroundSpec.from_any(spec_any)
        key = (spec.image_path, spec.mode, spec.tint_rgba)
        
        # No change -> Ignore
        if self._last_key == key:
            return
        self._last_key = key
        
        # First time or no image -> Hard cut
        if not getattr(self._current, "_orig", None) or transition == "cut":
            self._apply_spec(self._current, spec)
            self._next = None
            self._active = False
            self._fade_t = 0.0
            self._fade_dur = 0.0
            return
        
        # Prepare crossfade
        nxt = ImageBrush()
        self._apply_spec(nxt, spec)
        self._next = nxt
        self._fade_t = 0.0
        self._fade_dur = max(0.01, float(duration))
        self._active = True
        
    def update(self, dt: float) -> None:
        if not self._active or not self._next:
            return
        self._fade_t = min(self._fade_dur, self._fade_t + max(0.0, dt))
        if self._fade_t >= self._fade_dur:
            # Finalize
            self._current, self._next = self._next, None
            self._active = None
            
    def draw(self, surface: pygame.Surface, rect: pygame.Rect) -> None:
        # Draw the current background directly
        self._current.draw(surface, rect)
        
        # If fading, draw the next on a temp surface with alpha
        if self._active and self._next:
            alpha = int(255 * (self._fade_t / self._fade_dur) if self._fade_dur > 0 else 255)
            temp = pygame.Surface(rect.size, pygame.SRCALPHA)
            self._next.draw(temp, temp.get_rect())
            temp.set_alpha(alpha)
            surface.blit(temp, rect.topleft)
            
            