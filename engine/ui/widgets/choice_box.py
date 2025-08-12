from __future__ import annotations
from typing import List, Tuple
from engine.ui.style import Theme
import pygame


def _ease_out_cubic(t: float) -> float:
    t = 0.0 if t < 0.0 else 1.0 if t > 1.0 else t
    return 1 - (1 - t) ** 3

def _scale_padding(padding: Tuple[int, int, int, int], factor: float) -> Tuple[int, int, int, int]:
    t, r, b, l = padding
    return (int(t * factor), int(r * factor), int(b * factor), int(l * factor))

class ChoiceBox:
    """
    Stateless renderer for a compact choice panel inside a textbox viewport.
    Draws a rounded rect and the provided choice lines.
    """
    def calc_height(viewport: pygame.Rect, lines: list[str], theme: Theme, fonts) -> int:
        inset = getattr(theme, "choice_inset_px", 12)
        pad_t, pad_r, pad_b, pad_l = getattr(
            theme, "choice_padding", _scale_padding(theme.padding, 0.6)
        )
        font = fonts.get(theme.font_path, theme.font_size)
        line_h = [font.render(s, True, theme.text_rgb).get_height() for s in (lines or [])]
        text_h = sum(line_h) + max(0, len(line_h)-1) * theme.line_spacing
        return text_h + pad_t + pad_b  # unclamped; let viewport clip

    @staticmethod
    def draw_flow(layer: pygame.Surface,
                  viewport: pygame.Rect,
                  lines: list[str],
                  theme,
                  fonts,
                  y_top: int,
                  anim_t: float,
                  anim_duration: float = 0.18,
                  selected_idx: int = -1) -> None:
        if not lines:
            return
        
        inset = getattr(theme, "choice_inset_px", 12)
        pad_t, pad_r, pad_b, pad_l = getattr(
            theme, "choice_padding", _scale_padding(theme.padding, 0.6)
        )
        radius = max(4, getattr(theme, "border_radius", 12) - 4)
        font = fonts.get(theme.font_path, theme.font_size)
        color = theme.text_rgb
        ls = theme.line_spacing

        # measure
        surfaces = [font.render(s, True, color) for s in lines]
        text_h = sum(s.get_height() for s in surfaces) + max(0, len(surfaces)-1) * ls
        box_w = max(0, viewport.w - inset*2)
        box_h = text_h + pad_t + pad_b

        # panel
        panel = pygame.Surface((box_w, box_h), pygame.SRCALPHA)
        pygame.draw.rect(panel, theme.box_bg, panel.get_rect(), border_radius=radius)
        pygame.draw.rect(panel, theme.box_border, panel.get_rect(), width=1, border_radius=radius)

        # text + underline
        y = pad_t
        for i, surf in enumerate(surfaces):
            panel.blit(surf, (pad_l, y))
            if i == selected_idx:
                # underline the full option text width
                uy = y + surf.get_height() - 2
                ux0 = pad_l
                ux1 = pad_l + surf.get_width()
                pygame.draw.line(panel, color, (ux0, uy), (ux1, uy), 2)
            y += surf.get_height()
            if i < len(surfaces)-1:
                y += ls

        # subtle intro
        u = 1.0 if anim_duration <= 0 else max(0.0, min(1.0, anim_t/anim_duration))
        offset = int((1.0 - u) * 8)
        panel.set_alpha(int(255*u))

        x = viewport.x + inset
        layer.blit(panel, (x, y_top - offset))
        
    @staticmethod
    def hit_test(viewport: pygame.Rect,
                    lines: List[str],
                    theme,
                    fonts,
                    y_top: int,
                    point_widget_coords: Tuple[int, int],
                    strict_text_x: bool = False) -> int | None:
        """ Return index of line under the mouse, or None. """
        if not lines:
            return None
        inset = getattr(theme, "choice_inset_px", 12)
        pad_t, pad_r, pad_b, pad_l = getattr(theme, "choice_padding", _scale_padding(theme.padding, 0.6))
        font = fonts.get(theme.font_path, theme.font_size)
        ls = theme.line_spacing
        
        box_x = viewport.x + inset
        box_w = max(0, viewport.w - inset * 2)
        xw, yw = point_widget_coords
        if xw < box_x or xw > box_x + box_w:
            # Needs to strictly be hovering the text
            if not strict_text_x:
                return None
        y_local = yw - y_top - pad_t
        if y_local < 0:
            return None
        
        y = 0
        for i, line in enumerate(lines):
        # measure current row
            text_w, text_h = font.size(line or "")
            row_h = text_h + (ls if i < len(lines) - 1 else 0)

            # vertical row bounds
            if y <= y_local < y + row_h:
                if strict_text_x:
                    x0 = box_x + pad_l
                    x1 = x0 + text_w
                    if x0 <= xw <= x1:
                        return i
                    return None
                else:
                    return i

            y += row_h

        return None