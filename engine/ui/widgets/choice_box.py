from __future__ import annotations
from typing import List, Optional, Tuple
import pygame

from engine.ui.style import Theme
from engine.ui.fonts import FontCache


# ---------- Helpers ----------

def _choice_font(theme: Theme, fonts: FontCache) -> pygame.font.Font:
    """Use the UI font from the theme."""
    return fonts.get(theme.font_path, theme.font_size)

def _choice_box_metrics(viewport: pygame.Rect, theme: Theme, fonts: FontCache):
    """
    Geometry + font metrics for the choice overlay.
    Returns: inset, (pad_t, pad_r, pad_b, pad_l), max_text_w, font, line_h, gap_between_items, line_gap
    """
    inset = getattr(theme, "choice_inset_px", 12)
    pad_t, pad_r, pad_b, pad_l = getattr(theme, "choice_padding", (8, 10, 8, 10))
    max_text_w = max(0, viewport.w - (inset * 2 + pad_l + pad_r))
    font = _choice_font(theme, fonts)
    line_h = font.get_linesize()
    line_gap = getattr(theme, "line_spacing", 4)            # spacing between wrapped sublines
    gap_between_items = getattr(theme, "line_spacing", 4)   # vertical gap between items
    return inset, (pad_t, pad_r, pad_b, pad_l), max_text_w, font, line_h, gap_between_items, line_gap

def _split_long_word(word: str, font: pygame.font.Font, max_w: int) -> List[str]:
    """
    Fallback split for a single token that exceeds max_w (e.g., URLs).
    Greedy char-chunking to avoid overflow.
    """
    if font.size(word)[0] <= max_w:
        return [word]
    out: List[str] = []
    cur = ""
    for ch in word:
        trial = cur + ch
        if font.size(trial)[0] <= max_w or cur == "":
            cur = trial
        else:
            out.append(cur)
            cur = ch
    if cur:
        out.append(cur)
    return out

def _wrap_text_to_width(text: str, font: pygame.font.Font, max_w: int) -> List[str]:
    """
    Greedy word-wrap. Preserves explicit newlines.
    - Splits long tokens if a single word exceeds max_w.
    - Guarantees at least one output line.
    """
    if not text:
        return [""]
    wrapped: List[str] = []
    for raw in (text.splitlines() or [""]):
        words = raw.split(" ")
        cur = ""
        for w in words:
            parts = _split_long_word(w, font, max_w) if font.size(w)[0] > max_w else [w]
            for part in parts:
                trial = part if cur == "" else (cur + " " + part)
                if font.size(trial)[0] <= max_w or cur == "":
                    cur = trial
                else:
                    wrapped.append(cur)
                    cur = part
        wrapped.append(cur)
    return wrapped or [""]

# ---------- Renderer ----------

class ChoiceBox:
    """
    Stateless renderer for a compact choice panel inside a textbox viewport.
    All methods are static; call as ChoiceBox.calc_height / draw_flow / hit_test.
    """

    @staticmethod
    def calc_height(viewport: pygame.Rect, lines: List[str], theme: Theme, fonts: FontCache) -> int:
        inset, pads, max_w, font, line_h, gap_items, line_gap = _choice_box_metrics(viewport, theme, fonts)
        pad_t, pad_r, pad_b, pad_l = pads

        # Overall overlay height = top/bottom inset margins + panel content height
        total_h = inset * 2
        for text in (lines or []):
            sub = _wrap_text_to_width(text or "", font, max_w)
            lines_h = (len(sub) * line_h) + (max(0, len(sub) - 1) * line_gap)
            item_h = pad_t + lines_h + pad_b
            total_h += item_h + gap_items

        if lines:
            total_h -= gap_items  # remove last between-item gap
        return total_h

    @staticmethod
    def draw_flow(
        layer: pygame.Surface,
        viewport: pygame.Rect,
        lines: List[str],
        theme: Theme,
        fonts: FontCache,
        y_top: int,
        anim_t: float,
        anim_duration: float,
        selected_idx: int | None,
    ) -> None:
        if not lines:
            return

        inset, pads, max_w, font, line_h, gap_items, line_gap = _choice_box_metrics(viewport, theme, fonts)
        pad_t, pad_r, pad_b, pad_l = pads

        # Animation
        slide_px = getattr(theme, "choice_slide_px", 8)
        u = 1.0 if anim_duration <= 0 else min(1.0, anim_t / anim_duration)
        slide_offset = int((1.0 - u) * slide_px)

        color = getattr(theme, "text_rgb", (235, 235, 235))
        underline_th = int(getattr(theme, "choice_underline_thickness", 2))
        radius = max(4, int(getattr(theme, "border_radius", 12)) + int(getattr(theme, "choice_radius_delta", -4)))

        # Pre-wrap to measure
        wrapped_blocks: List[List[str]] = []
        item_heights: List[int] = []
        for text in lines:
            sub = _wrap_text_to_width(text or "", font, max_w)
            wrapped_blocks.append(sub)
            lines_h = (len(sub) * line_h) + (max(0, len(sub) - 1) * line_gap)
            item_heights.append(pad_t + lines_h + pad_b)

        content_h = sum(item_heights) + (len(lines) - 1) * gap_items if lines else 0
        panel_w = max(0, viewport.w - inset * 2)
        panel_h = max(0, content_h)
        panel_x = viewport.x + inset
        panel_y = y_top + inset - slide_offset
        panel_rect = pygame.Rect(panel_x, panel_y, panel_w, panel_h)

        # ---------- BLUR BACKDROP (robust to scrolling/clipping) ----------
        blur_scale = float(getattr(theme, "choice_blur_scale", 0.25))
        blur_passes = int(getattr(theme, "choice_blur_passes", 1))
        tint_rgba = getattr(theme, "choice_tint_rgba", (0, 0, 0, 96))

        # Only capture what is actually visible on the layer
        layer_rect = layer.get_rect()
        capture_rect = panel_rect.clip(viewport).clip(layer_rect)
        if capture_rect.w > 0 and capture_rect.h > 0:
            snap = layer.subsurface(capture_rect).copy()

            # Fast blur via scale-down / up
            if 0.0 < blur_scale < 1.0:
                sw, sh = snap.get_size()
                dw, dh = max(1, int(sw * blur_scale)), max(1, int(sh * blur_scale))
                small = pygame.transform.smoothscale(snap, (dw, dh))
                # optional extra passes (very mild additional blur)
                for _ in range(max(0, blur_passes - 1)):
                    small = pygame.transform.smoothscale(small, (max(1, int(dw * 0.85)), max(1, int(dh * 0.85))))
                blurred = pygame.transform.smoothscale(small, (sw, sh))
            else:
                blurred = snap

            # Rounded mask on the visible portion
            mask = pygame.Surface(capture_rect.size, pygame.SRCALPHA)
            pygame.draw.rect(mask, (255, 255, 255, 255), mask.get_rect(), border_radius=radius)
            blurred.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)

            # Optional tint to improve readability
            if tint_rgba:
                tinted = pygame.Surface(capture_rect.size, pygame.SRCALPHA)
                tinted.fill(tint_rgba)
                blurred.blit(tinted, (0, 0))  # normal alpha blend

            # Put the blurred+masked backdrop back exactly where it was captured
            layer.blit(blurred, capture_rect.topleft)

        # Draw border on the full (unclipped) panel; the layer's clip will handle visibility
        pygame.draw.rect(
            layer, getattr(theme, "box_border", (255, 255, 255, 160)),
            panel_rect, width=1, border_radius=radius
        )

        # ---------- TEXT + UNDERLINE ----------
        x_text = panel_x + pad_l
        y = panel_y
        for idx, sub in enumerate(wrapped_blocks):
            item_h = item_heights[idx]
            y_line = y + pad_t
            for s in sub:
                if s:
                    surf = font.render(s, True, color)
                    layer.blit(surf, (x_text, y_line))
                y_line += line_h + line_gap

            if selected_idx is not None and idx == selected_idx:
                widest = max((font.size(s or "")[0] for s in sub), default=0)
                ux = x_text
                uw = min(widest, max_w)
                uy = y + item_h - pad_b - underline_th
                if uw > 0:
                    pygame.draw.rect(layer, color, pygame.Rect(ux, uy, uw, underline_th))

            y += item_h + gap_items

    @staticmethod
    def hit_test(
        viewport: pygame.Rect,
        lines: List[str],
        theme: Theme,
        fonts: FontCache,
        y_top: int,
        point_widget_coords: Tuple[int, int],
        strict_text_x: bool,
    ) -> Optional[int]:
        if not lines:
            return None

        vx, vy = point_widget_coords
        inset, pads, max_w, font, line_h, gap_items, line_gap = _choice_box_metrics(viewport, theme, fonts)
        pad_t, pad_r, pad_b, pad_l = pads

        panel_x = viewport.x + inset
        panel_y = y_top + inset
        panel_w = max(0, viewport.w - inset * 2)

        x_text = panel_x + pad_l
        x_text_max = x_text + max_w

        y = panel_y
        for idx, text in enumerate(lines or []):
            sub = _wrap_text_to_width(text or "", font, max_w)
            lines_h = (len(sub) * line_h) + (max(0, len(sub) - 1) * line_gap)
            item_h = pad_t + lines_h + pad_b

            # Y within this item's block?
            if y <= vy < y + item_h:
                if not strict_text_x:
                    return idx
                # strict: require X within actual text width (widest subline)
                widest = max((font.size(s or "")[0] for s in sub), default=0)
                xt_max = min(x_text + widest, x_text_max)
                if x_text <= vx <= xt_max:
                    return idx
                return None

            y += item_h + gap_items

        return None
