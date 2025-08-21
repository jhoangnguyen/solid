from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Optional
from engine.ui.style import Theme
import pygame


@dataclass
class BottomBarButton:
    id: str
    label: str = ""


def _rgb(c, fallback=(255, 255, 255)) -> tuple[int, int, int]:
    if isinstance(c, (list, tuple)) and len(c) >= 3:
        return int(c[0]), int(c[1]), int(c[2])
    return fallback


def _rgba(c, fallback=(10, 10, 10, 170)) -> tuple[int, int, int, int]:
    if isinstance(c, (list, tuple)) and len(c) >= 4:
        return int(c[0]), int(c[1]), int(c[2]), int(c[3])
    if isinstance(c, (list, tuple)) and len(c) == 3:
        return int(c[0]), int(c[1]), int(c[2]), 255
    r, g, b, a = fallback
    return int(r), int(g), int(b), int(a)

class BottomBar:
    """
    Bottom HUD bar:
      - Left 75%: 2 rows × 3 columns (six long buttons)
      - Right 25%: 3 vertically stacked chunky buttons (equal height)

    Slots you can set with BottomBar.set_slots({...}):
      left_1, left_2, left_3,
      left_4, left_5, left_6,
      right_1, right_2, right_3
    """

    def __init__(
        self,
        theme,
        width_frac: float = 0.92,     # keep width as a fraction
        height_frac: float = 0.18,    # used only if theme.bottom_bar.height is absent
        margin_px: int = 10,
    ):
        self.theme : Theme = theme
        self.width_frac = float(width_frac)
        self.height_frac = float(height_frac)
        self.margin_px = int(margin_px)

        self.slots: Dict[str, BottomBarButton] = {}
        self._hit_rects: Dict[str, pygame.Rect] = {}
        self._font: Optional[pygame.font.Font] = None
        self._bar_rect_rect: Optional[pygame.Rect] = None

    # ---------- public ----------
    def set_slots(self, mapping: Dict[str, BottomBarButton]) -> None:
        self.slots.update(mapping)

    def hit_test(self, pos: tuple[int, int]) -> bool:
        """True if pos lies inside the bar area last laid out by draw()."""
        br = self._bar_rect_rect
        return isinstance(br, pygame.Rect) and br.collidepoint(pos)

    def get_clicked(self, pos: tuple[int, int]) -> Optional[str]:
        for sid, r in self._hit_rects.items():
            if r.collidepoint(pos):
                return sid
        return None

    def on_resize(self, screen_rect: pygame.Rect) -> None:
        """Call this from VIDEORESIZE if you cache anything screen-related."""
        self._screen_rect = screen_rect

    def draw(self, surface: pygame.Surface) -> None:
        # ---- read theme-driven metrics ----
        bb = getattr(self.theme, "bottom_bar", None)

        # Bar metrics
        bar_height_px = int(bb.height if bb else 72)
        bar_radius    = int(bb.radius if bb else 12)
        pad_t, pad_r, pad_b, pad_l = (bb.padding if bb else (10, 16, 10, 16))
        gap           = int(bb.gap if bb else 12)
        bar_bg_rgba   = (bb.bg_rgba if bb else (10, 10, 10, 170))
        bar_border_rgba = (bb.border_rgba if bb else (255, 255, 255, 60))

        # ---- layout the bar rect first (we need bar.h for fractions) ----
        bar = self._bar_rect(surface, bar_height_px)
        self._bar_rect_rect = bar
        if bar.w <= 0 or bar.h <= 0:
            return

        # Button metrics (fractions override pixels)
        btns = bb.button if bb else None
        # base pixel fallbacks
        base_btn_h      = int(btns.h if btns else 44)
        base_pad_x      = int(btns.pad_x if btns else 14)
        btn_text_size   = int(btns.text_size if btns else 18)
        btn_radius      = int(btns.radius if btns else 10)
        btn_text_rgb    = (btns.text_rgb if btns else (235, 235, 235))
        btn_fill_rgba   = (btns.fill_rgba if btns else (30, 30, 35, 220))
        btn_hover_rgba  = (btns.hover_rgba if btns else (50, 50, 60, 240))
        btn_down_rgba   = (btns.down_rgba if btns else (70, 70, 80, 255))
        btn_border_rgba = (btns.border_rgba if btns else (255, 255, 255, 60))
        btn_border_px   = int(btns.border_px if btns else 1)

        # optional fraction fields
        h_frac          = float(btns.h_frac) if btns and btns.h_frac is not None else None
        pad_x_frac      = float(btns.pad_x_frac) if btns and btns.pad_x_frac is not None else None
        text_size_frac  = float(btns.text_size_frac) if btns and btns.text_size_frac is not None else None
        radius_frac     = float(btns.radius_frac) if btns and btns.radius_frac is not None else None
        border_px_frac  = float(btns.border_px_frac) if btns and btns.border_px_frac is not None else None

        # Clamp fractions to sane ranges
        def _clamp(v, lo, hi):
            return max(lo, min(hi, v))

        if text_size_frac is not None:
            btn_text_size = max(8, int(_clamp(text_size_frac, 0.05, 1.0) * bar.h))
        if radius_frac is not None:
            btn_radius = max(2, int(_clamp(radius_frac, 0.0, 0.5) * bar.h))
        if border_px_frac is not None:
            btn_border_px = max(1, int(_clamp(border_px_frac, 0.0, 0.1) * bar.h))

        # Font (resolve each frame in case theme changed)
        font_path = getattr(self.theme, "font_path", None)
        self._font = pygame.font.Font(font_path, btn_text_size)

        # --- background + border using an alpha-capable overlay ---
        overlay = pygame.Surface(bar.size, pygame.SRCALPHA)
        pygame.draw.rect(overlay, bar_bg_rgba, overlay.get_rect(), border_radius=bar_radius)
        if bar_border_rgba[3] > 0 and btn_border_px >= 1:
            pygame.draw.rect(overlay, bar_border_rgba, overlay.get_rect(), width=1, border_radius=bar_radius)
        surface.blit(overlay, bar.topleft)

        # --- inner content area ---
        inner = pygame.Rect(
            bar.x + pad_l,
            bar.y + pad_t,
            bar.w - (pad_l + pad_r),
            bar.h - (pad_t + pad_b),
        )
        if inner.w <= 0 or inner.h <= 0:
            return

        # Split 75% / 25%
        left_w = int(inner.w * 0.75)
        right_w = inner.w - left_w
        left_area = pygame.Rect(inner.x, inner.y, left_w, inner.h)
        right_area = pygame.Rect(inner.x + left_w, inner.y, right_w, inner.h)

        # ---- LEFT: 2 rows × 3 equal columns ----
        left_row_h = (left_area.h - gap) // 2
        left_col_w = (left_area.w - 2 * gap) // 3
        left_rows_y = (left_area.y, left_area.y + left_row_h + gap)
        left_cols_x = (
            left_area.x,
            left_area.x + left_col_w + gap,
            left_area.x + (left_col_w + gap) * 2,
        )

        # Build left cells, then shrink to button rects using frac OR pixels
        left_cells = [pygame.Rect(cx, ry, left_col_w, left_row_h)
                    for ry in left_rows_y for cx in left_cols_x]

        left_btn_rects = []
        for cell in left_cells:
            # pad_x may be frac of cell width
            px = int(_clamp(pad_x_frac, 0.0, 0.5) * cell.w) if pad_x_frac is not None else base_pad_x
            # height may be frac of cell height
            h  = int(_clamp(h_frac, 0.0, 1.0) * cell.h) if h_frac is not None else min(base_btn_h, cell.h)
            w  = max(0, cell.w - 2 * px)
            x  = cell.x + px
            y  = cell.y + (cell.h - h) // 2
            left_btn_rects.append(pygame.Rect(x, y, w, h))

        # ---- RIGHT: 3 vertical chunky buttons (full height, frac pad_x) ----
        gap_x = gap
        right_col_w = max(40, (right_area.w - 2 * gap_x) // 3)
        x0 = right_area.x + gap_x
        x1 = x0 + right_col_w + gap_x
        x2 = x1 + right_col_w + gap_x
        w_last = right_area.right - x2

        right_cells = [
            pygame.Rect(x0, right_area.y, right_col_w, right_area.h),
            pygame.Rect(x1, right_area.y, right_col_w, right_area.h),
            pygame.Rect(x2, right_area.y, w_last,        right_area.h),
        ]
        right_btn_rects = []
        for cell in right_cells:
            px = int(_clamp(pad_x_frac, 0.0, 0.5) * cell.w) if pad_x_frac is not None else base_pad_x
            w  = max(0, cell.w - 2 * px)
            x  = cell.x + px
            right_btn_rects.append(pygame.Rect(x, cell.y, w, cell.h))

        # Map ids -> rects
        layout = {
            "left_1": left_btn_rects[0], "left_2": left_btn_rects[1], "left_3": left_btn_rects[2],
            "left_4": left_btn_rects[3], "left_5": left_btn_rects[4], "left_6": left_btn_rects[5],
            "right_1": right_btn_rects[0], "right_2": right_btn_rects[1], "right_3": right_btn_rects[2],
        }

        # Draw + hit rects
        self._hit_rects.clear()
        for sid, rect in layout.items():
            self._draw_button(surface, rect, self.slots.get(sid),
                            fill_rgba=btn_fill_rgba,
                            border_rgba=btn_border_rgba,
                            border_px=btn_border_px,
                            radius=btn_radius,
                            text_rgb=btn_text_rgb)
            self._hit_rects[sid] = rect

    # ---------- internals ----------
    def _bar_rect(self, surface: pygame.Surface, height_px_from_theme: int) -> pygame.Rect:
        sw, sh = surface.get_size()
        w = int(max(0.0, min(1.0, self.width_frac)) * sw)

        # Prefer theme pixel height; fall back to fraction if <=0
        h_theme = int(height_px_from_theme or 0)
        if h_theme > 0:
            h = min(h_theme, sh)  # clamp
        else:
            h = int(max(0.0, min(1.0, self.height_frac)) * sh)

        x = (sw - w) // 2
        y = sh - h - self.margin_px
        return pygame.Rect(x, y, w, h)

    def _draw_button(
        self,
        surface: pygame.Surface,
        rect: pygame.Rect,
        btn: Optional[BottomBarButton],
        *,
        fill_rgba: tuple[int,int,int,int],
        border_rgba: tuple[int,int,int,int],
        border_px: int,
        radius: int,
        text_rgb: tuple[int,int,int],
    ) -> None:
        # Alpha overlay for fill + border so RGBA is respected
        ov = pygame.Surface(rect.size, pygame.SRCALPHA)
        pygame.draw.rect(ov, fill_rgba, ov.get_rect(), border_radius=radius)
        if border_px >= 1 and border_rgba[3] > 0:
            pygame.draw.rect(ov, border_rgba, ov.get_rect(), width=border_px, border_radius=radius)
        surface.blit(ov, rect.topleft)

        # Label
        if btn and btn.label and self._font:
            surf = self._font.render(btn.label, True, text_rgb)
            tx = rect.x + (rect.w - surf.get_width()) // 2
            ty = rect.y + (rect.h - surf.get_height()) // 2
            surface.blit(surf, (tx, ty))
