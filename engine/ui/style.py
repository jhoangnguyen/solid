from dataclasses import dataclass, replace, field
from typing import Optional
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
class BottomBarButtonStyle:
    h: int = 44
    pad_x: int = 14
    radius: int = 10
    text_size: int = 18
    text_rgb: tuple[int, int, int] = (235, 235, 235)
    fill_rgba: tuple[int, int, int, int] = (30, 30, 35, 220)
    hover_rgba: tuple[int, int, int, int] = (50, 50, 60, 240)
    down_rgba: tuple[int, int, int, int]  = (70, 70, 80, 255)
    border_rgba: tuple[int, int, int, int] = (255, 255, 255, 60)
    border_px: int = 1
    h_frac: float | None = None          # 0..1 of the LEFT cell height
    pad_x_frac: float | None = None      # 0..0.5 of the button cell width
    text_size_frac: float | None = None  # 0..1 of the BAR height
    radius_frac: float | None = None     # 0..0.5 of the BAR height
    border_px_frac: float | None = None  # 0..0.1 of the BAR height

    
@dataclass
class BottomBarStyle:
    height: int = 72               # pixels (preferred)
    radius: int = 12
    padding: tuple[int, int, int, int] = (10, 16, 10, 16)  # t, r, b, l
    gap: int = 12
    bg_rgba: tuple[int, int, int, int] = (10, 10, 10, 170)
    border_rgba: tuple[int, int, int, int] = (255, 255, 255, 60)
    button: BottomBarButtonStyle = field(default_factory=BottomBarButtonStyle)
    
@dataclass
class TopIconsStyle:
    size_px: int = 48          # square icon box size
    margin_px: int = 12        # distance from screen top/right edges
    gap_px: int = 10           # space between icons
    ring_rgba: tuple[int,int,int,int] = (255, 255, 255, 180)  # hover outline
    ring_px: int = 2
    hover_tint_rgba: tuple[int,int,int,int] = (255, 255, 255, 40)
    down_tint_rgba:  tuple[int,int,int,int] = (255, 255, 255, 80)
    corner_radius: int = 8     # round the icon’s hitbox square (purely visual)
    
@dataclass
class Theme:
    font_path: str | None = None
    font_size: int = 22
    text_rgb: tuple[int, int, int] = (237, 237, 237)
    box_bg: tuple[int, int, int] = (20, 22, 27)
    box_border: tuple[int, int, int] = (60, 64, 72)
    border_radius: int = 16
    padding: tuple[int, int, int, int] = (24, 28, 24, 28)
    line_spacing: int = 8
    scrollbar: ScrollbarStyle = field(default_factory=ScrollbarStyle)
    entry_gap: int = 8
    wait_indicator: WaitIndicatorStyle = field(default_factory=WaitIndicatorStyle)
    choice_blur_scale: float = 0.25      # 0.20–0.35 = stronger blur
    choice_blur_passes: int = 1        # 1–2
    choice_tint_rgba: Optional[tuple[int, int, int, int]] = (0, 0, 0, 96)  # darken a bit over the blur for readability
    bottom_bar: BottomBarStyle = field(default_factory=BottomBarStyle)
    top_icons: TopIconsStyle = field(default_factory=TopIconsStyle)
    
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
        