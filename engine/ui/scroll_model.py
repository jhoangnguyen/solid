from dataclasses import dataclass

@dataclass
class ScrollModel:
    content_h: int = 0
    viewport_h: int = 0
    offset: float = 0.0
    
    def max(self) -> float: return max(0.0, float(self.content_h - self.viewport_h))
    def clamp(self): self.offset = max(0.0, min(self.max(), self.offset))
    def scroll(self, dy: float): self.offset += dy; self.clamp()
    def to_top(self): self.offset = 0.0
    def to_bottom(self): self.offset = self.max()
    def near_bottom(self, px: int) -> bool: return (self.max() - self.offset) <= max(0, px)