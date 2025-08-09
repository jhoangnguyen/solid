from dataclasses import dataclass
from typing import Callable, Any, List

def ease_linear(t: float) -> float: return t
def ease_out_cubic(t: float) -> float: t = max(0.0, min(1.0, t)); return 1 - (1 - t) ** 3

@dataclass
class Tween:
    obj: Any
    attr: str
    start: float
    end: float
    duration: float
    ease: Callable[[float], float] = ease_out_cubic
    t: float = 0.0
    on_done: Callable[[], None] | None = None
    
    def update(self, dt: float) -> bool:
        self.t += dt
        u = 1.0 if self.duration <= 0 else max(0.0, min(1.0, self.t / self.duration))
        v = self.start + (self.end - self.start) * self.ease(u)
        setattr(self.obj, self.attr, v)
        finished = (u >= 1.0)
        if finished and self.on_done:
            self.on_done()
        return finished
    
class Animator:
    def __init__(self):
        self._tweens: list[Tween] = []
        
    def add(self, tween: Tween) -> None:
        self._tweens.append(tween)
        
    def update(self, dt: float) -> None:
        self._tweens[:] = [tw for tw in self._tweens if not tw.update(dt)]
        
        
