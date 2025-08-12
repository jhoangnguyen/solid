from dataclasses import dataclass, replace, field
import pygame

@dataclass
class ScrollbarStyle:
    width: int = 6
    margin: int = 8
    radius: int = 3
    min_thumb_size: int = 24
    show_when_no_overflow: bool = True
    track_color: tuple[int, int, int, int] = (255, 255, 255, 32)
    thumb_color: tuple[int, int, int, int] = (255, 255, 255, 192)
    offset_x: int = 15
    def derive(self, **overrides): return replace(self, **overrides)

@dataclass
class WaitIndicatorStyle:
    enabled: bool = True
    char: str = "\u25BC"
    color: tuple[int, int, int] = (237, 237, 237)
    period: float = 1.2
    alpha_min: int = 40
    alpha_max: int = 255
    offset_x: int = 6
    offset_y: int = 2
    scale: float = 1.0
    font_path: str | None = None


@dataclass
class Theme:
    font_path: str | None = None
    font_size: int = 22
    text_rgb: tuple[int, int, int] = (237, 237, 237)
    box_bg: tuple[int, int, int] = (20, 22, 27)
    box_border: tuple[int, int, int] = (60, 64, 72)
    border_radius: int = 16
    padding: tuple[int, int, int, int] = (24, 28, 24, 28)
    line_spacing: int = 6
    scrollbar: ScrollbarStyle = field(default_factory=ScrollbarStyle)
    entry_gap: int = 5
    wait_indicator: WaitIndicatorStyle = field(default_factory=WaitIndicatorStyle)
    
    def derive(self, **overrides) -> "Theme":
        """ Create a variant theme (e.g., per screen) without mutating the base. """
        return replace(self, **overrides)
    
def compute_centered_rect(surface: pygame.Surface, frac_w=0.7, frac_h=0.45) -> pygame.Rect:
    sw, sh = surface.get_size()
    w, h = int(sw * frac_w), int(sh * frac_h)
    return pygame.Rect((sw - w) // 2, (sh - h) // 2, w, h)

class StyleContext:
    """ Simple stack so screens can push a theme variant and pop on exit."""
    def __init__(self, base: Theme | None = None):
        self._stack: list[Theme] = [base or Theme()]
        
    @property
    def current(self) -> Theme:
        return self._stack[-1]
    
    def push(self, theme: Theme) -> None:
        self._stack.append(theme)
        
    def pop(self) -> None:
        if len(self._stack) > 1:
            self._stack.pop()
        