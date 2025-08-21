from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Tuple, Any, Dict
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
            tint = v.get("tint_rgba", None)
            return BackgroundSpec(
                image_path=v.get("image_path") or v.get("path") or v.get("file"),
                mode=v.get("mode", "cover"),
                tint_rgba=(tuple(tint) if tint is not None else None)
            )
        raise TypeError(f"Unsupported bg spec: {type(v)}")
    
class _Channel:
    def __init__(self) -> None:
        self.current = ImageBrush()
        self.next: Optional[ImageBrush] = None
        self.fade_t = 0.0
        self.fade_dur = 0.0
        self.active = False
        self.last_key: Optional[tuple] = None # (path, mode, tint)        
    
class BackgroundManager:
    """ Owns the window background, supports seamless crossfades. """
    def __init__(self) -> None:
        self._slots: Dict[str, _Channel] = {}
        
    def _slot(self, name: str) -> _Channel:
        if name not in self._slots:
            self._slots[name] = _Channel()
        return self._slots[name]
        
    def _apply_spec(self, brush: ImageBrush, spec: BackgroundSpec) -> None:
        brush.set_image(spec.image_path)
        brush.set_mode(spec.mode)
        brush.tint_rgba = spec.tint_rgba
        
    def set(self, spec_any: Any, *, slot: str = "window", transition: str = "crossfade", duration: float = 0.35) -> None:
        """ Set background from YAML spec. If none, do nothing. """
        if spec_any is None:
            return
        spec = BackgroundSpec.from_any(spec_any)
        ch = self._slot(slot)
        key = (spec.image_path, spec.mode, spec.tint_rgba)
        
        # No change -> Ignore
        if ch.last_key == key:
            return
        ch.last_key = key
        
        # First time or no image -> Hard cut
        if not getattr(ch.current, "_orig", None) or transition == "cut":
            self._apply_spec(ch.current, spec)
            ch.next = None
            ch.active = False
            ch.fade_t = 0.0
            ch.fade_dur = 0.0
            return
        
        # Prepare crossfade
        nxt = ImageBrush()
        self._apply_spec(nxt, spec)
        ch.next = nxt
        ch.fade_t = 0.0
        ch.fade_dur = max(0.01, float(duration))
        ch.active = True
        
    def clear(self, slot: str) -> None:
        """ Remove image in a slot (nothing will draw). """
        if slot in self._slots:
            self._slots.pop(slot, None)
            
    def slot_has_image(self, slot: str) -> bool:
        ch = self._slot(slot)
        cur = getattr(ch.current, "_orig", None) is not None
        nxt = ch.active and ch.next and getattr(ch.next, "_orig", None) is not None
        return bool(cur or nxt)
        
    def update(self, dt: float) -> None:
        for ch in self._slots.values():
            if not ch.active or not ch.next:
                continue
            ch.fade_t = min(ch.fade_dur, ch.fade_t + max(0.0, dt))
            if ch.fade_t >= ch.fade_dur:
                ch.current, ch.next = ch.next , None
                ch.active = False
            
    def draw(self, surface: pygame.Surface, rect: pygame.Rect) -> None:
        # Draw the current background directly
        self.draw_slot("window", surface, rect)
        
    def draw_slot(self, slot: str, surface: pygame.Surface, rect: pygame.Rect) -> None:
        ch = self._slot(slot)
        ch.current.draw(surface, rect)
        if ch.active and ch.next:
            alpha = int(255 * (ch.fade_t / ch.fade_dur)) if ch.fade_dur > 0 else 255
            temp = pygame.Surface(rect.size, pygame.SRCALPHA)
            ch.next.draw(temp, temp.get_rect())
            temp.set_alpha(alpha)
            surface.blit(temp, rect.topleft) 
            