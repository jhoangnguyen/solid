from __future__ import annotations
from dataclasses import dataclass, field
from typing import List

@dataclass
class ChoiceController:
    lines: List[str] = field(default_factory=list)
    sel: int = -1
    hover: int = -1
    anim_t: float = 0.0
    anim_dur: float = 0.18
    anchor_bottom: bool = False # Keep scrolled to bottom while animation plays
    
    # Lifecycle
    def show(self, lines: List[str], anchor_bottom: bool) -> None:
        self.lines = list(lines or [])
        self.sel = 0 if self.lines else -1
        self.hover = -1
        self.anim_t = 0.0
        self.anchor_bottom = bool(anchor_bottom)
        
    def hide(self) -> None:
        self.lines.clear()
        self.sel = -1
        self.hover = -1
        self.anim_t = 0.0
        self.anchor_bottom = False
        
    def active(self) -> bool:
        return bool(self.lines)
    
    # Input
    def move(self, delta: int) -> None:
        if not self.lines: return
        n = len(self.lines)
        self.sel = (self.sel + delta) % n
        
    def set_hover_index(self, idx: int | None) -> None:
        self.hover = -1 if idx is None else int(idx)
        if idx is not None:
            self.sel = int(idx) # Hover also selects for underline
            
    # Animation
    def tick(self, dt: float) -> None:
        if self.anim_t < self.anim_dur:
            self.anim_t = min(self.anim_dur, self.anim_t + max(0.0, dt))