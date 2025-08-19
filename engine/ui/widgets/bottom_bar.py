from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Optional
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
        width_frac: float = 0.92,
        height_frac: float = 0.18,
        margin_px: int = 10,
    ):
        self.theme = theme
        self.width_frac = float(width_frac)
        self.height_frac = float(height_frac)
        self.margin_px = int(margin_px)

        self.slots: Dict[str, BottomBarButton] = {}
        self._hit_rects: Dict[str, pygame.Rect] = {}
        self._font: Optional[pygame.font.Font] = None

    # ---------- public ----------
    def set_slots(self, mapping: Dict[str, BottomBarButton]) -> None:
        self.slots.update(mapping)

    def get_clicked(self, pos: tuple[int, int]) -> Optional[str]:
        for sid, r in self._hit_rects.items():
            if r.collidepoint(pos):
                return sid
        return None

    def draw(self, surface: pygame.Surface) -> None:
        bar = self._bar_rect(surface)
        if bar.w <= 0 or bar.h <= 0:
            return

        # font (resolve each frame in case theme changed)
        size = max(12, int(getattr(self.theme, "font_size", 22) * 0.9))
        self._font = pygame.font.Font(getattr(self.theme, "font_path", None), size)

        radius = max(6, int(getattr(self.theme, "border_radius", 12)))

        # --- background (translucent overlay) ---
        bg_rgba = _rgba(getattr(self.theme, "box_bg", (10, 10, 10, 170)))
        bg_overlay = pygame.Surface(bar.size, pygame.SRCALPHA)
        pygame.draw.rect(bg_overlay, bg_rgba, bg_overlay.get_rect(), border_radius=radius)
        surface.blit(bg_overlay, bar.topleft)

        # --- outer border (draw OPAQUE directly on the screen) ---
        border_rgb = _rgb(getattr(self.theme, "box_border", (255, 255, 255)))
        pygame.draw.rect(surface, border_rgb, bar, width=1, border_radius=radius)

        # --- inner content area ---
        pad_x, pad_y = 12, 10
        inner = bar.inflate(-2 * pad_x, -2 * pad_y)
        if inner.w <= 0 or inner.h <= 0:
            return

        gap_x, gap_y = 12, 8

        # Split 75% / 25%
        left_w = int(inner.w * 0.75)
        right_w = inner.w - left_w
        left_area = pygame.Rect(inner.x, inner.y, left_w, inner.h)
        right_area = pygame.Rect(inner.x + left_w, inner.y, right_w, inner.h)

        # ---- LEFT: 2 rows × 3 equal columns ----
        # Row height:
        left_row_h = (left_area.h - gap_y) // 2
        # Column width:
        left_col_w = (left_area.w - 2 * gap_x) // 3

        left_rows_y = (left_area.y, left_area.y + left_row_h + gap_y)
        left_cols_x = (
            left_area.x,
            left_area.x + left_col_w + gap_x,
            left_area.x + (left_col_w + gap_x) * 2,
        )

        # Build left slot rects (absolute coords)
        r_left = []
        for row_y in left_rows_y:
            for col_x in left_cols_x:
                r_left.append(pygame.Rect(col_x, row_y, left_col_w, left_row_h))

        # ---- RIGHT: 3 VERTICAL chunky buttons (side-by-side) ----
        right_col_w = max(40, (right_area.w - 2 * gap_x) // 3)

        x0 = right_area.x + gap_x
        x1 = x0 + right_col_w + gap_x
        x2 = x1 + right_col_w + gap_x
        # Make the last column “fill” any rounding remainder so we hug the right edge.
        w_last = right_area.right - x2

        r_right = [
            pygame.Rect(x0, right_area.y, right_col_w, right_area.h),
            pygame.Rect(x1, right_area.y, right_col_w, right_area.h),
            pygame.Rect(x2, right_area.y, w_last,        right_area.h),
        ]

        # Map ids -> rects
        layout = {
            "left_1": r_left[0], "left_2": r_left[1], "left_3": r_left[2],
            "left_4": r_left[3], "left_5": r_left[4], "left_6": r_left[5],
            "right_1": r_right[0], "right_2": r_right[1], "right_3": r_right[2],
        }

        self._hit_rects.clear()
        for sid, rect in layout.items():
            self._draw_button(surface, rect, self.slots.get(sid))
            self._hit_rects[sid] = rect

    # ---------- internals ----------
    def _bar_rect(self, surface: pygame.Surface) -> pygame.Rect:
        sw, sh = surface.get_size()
        w = int(max(0.0, min(1.0, self.width_frac)) * sw)
        h = int(max(0.0, min(1.0, self.height_frac)) * sh)
        x = (sw - w) // 2
        y = sh - h - self.margin_px
        return pygame.Rect(x, y, w, h)

    def _draw_button(self, surface: pygame.Surface, rect: pygame.Rect, btn: Optional[BottomBarButton]) -> None:
        radius = max(4, int(getattr(self.theme, "border_radius", 12)) - 4)

        # Translucent fill via small overlay (always visible)
        fill_overlay = pygame.Surface(rect.size, pygame.SRCALPHA)
        pygame.draw.rect(fill_overlay, (255, 255, 255, 50), fill_overlay.get_rect(), border_radius=radius)
        surface.blit(fill_overlay, rect.topleft)

        # Opaque border
        border_rgb = _rgb(getattr(self.theme, "box_border", (255, 255, 255)))
        pygame.draw.rect(surface, border_rgb, rect, width=1, border_radius=radius)

        # Label
        if btn and btn.label:
            text_rgb = _rgb(getattr(self.theme, "text_rgb", (235, 235, 235)))
            surf = self._font.render(btn.label, True, text_rgb)
            tx = rect.x + (rect.w - surf.get_width()) // 2
            ty = rect.y + (rect.h - surf.get_height()) // 2
            surface.blit(surf, (tx, ty))
