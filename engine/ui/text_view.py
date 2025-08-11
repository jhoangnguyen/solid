from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional
import pygame
import math

from engine.ui.style import Theme
from engine.ui.text_model import Entry

def _ease_out_cubic(t: float) -> float:
    t = 0.0 if t < 0.0 else 1.0 if t > 1.0 else t
    return 1 - (1 - t) ** 3

@dataclass
class _Layout:
    surfaces: List[pygame.Surface]
    height: int  # sum(heights) + (lines-1)*line_spacing

class TextView:
    """
    Pure rendering + layout cache for a list of Entries.

    Responsibilities:
    - wrap text to width
    - render lines with animation (fade + slide)
    - draw the wait-for-input indicator
    - compute content height (inc. Theme.entry_gap)
    """
    def __init__(self, theme: Theme):
        self.theme = theme
        self.font = pygame.font.Font(theme.font_path, theme.font_size)
        self._wrap_w: int = -1
        self._cache: Dict[Entry, _Layout] = {}
        self._blink_t: float = 0.0  # for wait-indicator

    # --------- public ---------
    def set_theme(self, theme: Theme) -> None:
        self.theme = theme
        self.font = pygame.font.Font(theme.font_path, theme.font_size)
        self.invalidate_layout()

    def update(self, dt: float) -> None:
        self._blink_t += dt

    def invalidate_layout(self) -> None:
        self._wrap_w = -1
        self._cache.clear()

    def ensure_layout(self, wrap_w: int, entries: List[Entry]) -> None:
        if wrap_w <= 0:
            self._wrap_w = wrap_w
            self._cache.clear()
            return
        if wrap_w == self._wrap_w:
            return
        self.font = pygame.font.Font(self.theme.font_path, self.theme.font_size)
        self._wrap_w = wrap_w
        self._cache.clear()
        for e in entries:
            self._cache[e] = self._layout_entry(e, wrap_w)

    def content_height(self, entries: List[Entry]) -> int:
        if not entries:
            return 0
        total = 0
        for i, e in enumerate(entries):
            lay = self._cache.get(e)
            if not lay:
                lay = self._layout_entry(e, self._wrap_w if self._wrap_w > 0 else 1024)
                self._cache[e] = lay
            total += lay.height
            if i < len(entries) - 1:
                total += getattr(self.theme, "entry_gap", 0)
        return total

    def viewport_rect(self, widget_rect: pygame.Rect) -> pygame.Rect:
        t, r, b, l = self.theme.padding
        sb = self.theme.scrollbar
        reserve_w = max(0, sb.width + sb.margin)  # stable layout
        return pygame.Rect(
            l, t,
            max(0, widget_rect.w - (l + r + reserve_w)),
            max(0, widget_rect.h - (t + b))
        )

    def draw_into(self, layer: pygame.Surface, widget_rect: pygame.Rect,
                  entries: List[Entry], scroll_y: float) -> None:
        th = self.theme
        # bg + border
        full = pygame.Rect(0, 0, widget_rect.w, widget_rect.h)
        pygame.draw.rect(layer, th.box_bg, full, border_radius=th.border_radius)
        pygame.draw.rect(layer, th.box_border, full, width=1, border_radius=th.border_radius)

        viewport = self.viewport_rect(widget_rect)
        self.ensure_layout(viewport.width, entries)

        prev_clip = layer.get_clip()
        layer.set_clip(viewport)

        y = viewport.y - int(round(scroll_y))
        gap = th.line_spacing

        # bookmark indicator draw position
        indicator_pos: Optional[Tuple[int, int, int]] = None  # (x_end, y_top, line_h)

        for idx_entry, e in enumerate(entries):
            lay = self._cache[e]
            # entry easing
            u = 1.0 if e.duration <= 0 else _ease_out_cubic(e.t / e.duration)
            offset = int((1.0 - u) * e.offset_px)
            alpha = int(255 * u)

            for j, surf in enumerate(lay.surfaces):
                h = surf.get_height()

                # bookmark ▼ position for the last line of the last visible entry
                if e.wait_for_input and e.t >= e.duration - 1e-4 \
                   and j == len(lay.surfaces) - 1 and idx_entry == len(entries) - 1:
                    indicator_pos = (viewport.x + surf.get_width(), y + offset, h)

                if y + h + offset >= viewport.y and y + offset <= viewport.bottom:
                    prev_alpha = surf.get_alpha()
                    surf.set_alpha(alpha)
                    layer.blit(surf, (viewport.x, y + offset))
                    surf.set_alpha(prev_alpha)

                y += h
                if j < len(lay.surfaces) - 1:
                    y += gap

            if idx_entry < len(entries) - 1:
                y += th.entry_gap

        if indicator_pos:
            self._draw_wait_indicator(layer, viewport, indicator_pos)

        layer.set_clip(prev_clip)

    # --------- internals ---------
    def _layout_entry(self, e: Entry, wrap_w: int) -> _Layout:
        lines = self._wrap_text(e.text or "", wrap_w)
        render = self.font.render
        color = self.theme.text_rgb
        surfaces = [render(line, True, color) for line in lines]
        gap = self.theme.line_spacing
        height = sum(s.get_height() for s in surfaces) + (len(surfaces) - 1) * gap if surfaces else 0
        return _Layout(surfaces, height)

    def _wrap_text(self, text: str, wrap_w: int) -> List[str]:
        if not text:
            return []
        out: List[str] = []
        measure = self.font.size
        for raw in text.splitlines():
            words = raw.split(" ")
            if not words:
                out.append("")
                continue
            cur = ""
            for w in words:
                cand = w if not cur else f"{cur} {w}"
                if measure(cand)[0] <= wrap_w:
                    cur = cand
                else:
                    if cur:
                        out.append(cur)
                    if measure(w)[0] <= wrap_w:
                        cur = w
                    else:
                        chunks = self._hard_wrap_long_word(w, wrap_w, measure)
                        out.extend(chunks[:-1])
                        cur = chunks[-1] if chunks else ""
            out.append(cur)
        return out

    def _hard_wrap_long_word(self, word: str, wrap_w: int, measure) -> List[str]:
        parts: List[str] = []
        i, n = 0, len(word)
        while i < n:
            lo, hi = 1, n - i
            best = 1
            while lo <= hi:
                mid = (lo + hi) // 2
                seg = word[i:i+mid]
                if measure(seg)[0] <= wrap_w:
                    best = mid; lo = mid + 1
                else:
                    hi = mid - 1
            seg = word[i:i+best]
            if not seg: break
            parts.append(seg); i += best
        return parts

    # ---------- wait indicator ----------
    def _get_wait_style(self) -> dict:
        defaults = {
            "enabled": True,
            "char": "▼",
            "color": getattr(self.theme, "text_rgb", (237, 237, 237)),
            "period": 1.0,
            "alpha_min": 40,
            "alpha_max": 255,
            "offset_x": 6,
            "offset_y": 2,
            "scale": 1.0,
            "font_path": None,
            "align": "baseline",
        }
        wi = getattr(self.theme, "wait_indicator", None)
        if isinstance(wi, dict):
            for k in defaults:
                if k in wi: defaults[k] = wi[k]
        elif wi is not None:
            for k in defaults:
                if hasattr(wi, k): defaults[k] = getattr(wi, k)
        return defaults

    def _draw_wait_indicator(self, layer: pygame.Surface, viewport: pygame.Rect, info: Tuple[int,int,int]) -> None:
        x_end, y_top, line_h = info
        wi = self._get_wait_style()
        if not wi.get("enabled", True):
            return

        # robust time source
        period = max(1e-6, float(wi["period"]))
        t = self._blink_t if self._blink_t > 1e-8 else pygame.time.get_ticks() * 0.001
        phase = (t / period) % 1.0
        s = 0.5 * (1.0 + math.sin(2.0 * math.pi * phase))
        alpha = int(wi["alpha_min"] + (wi["alpha_max"] - wi["alpha_min"]) * s)

        # pick font for the indicator
        size = max(8, int(self.theme.font_size * max(0.1, float(wi["scale"]))))
        font_path = wi.get("font_path") or self.theme.font_path
        font = pygame.font.Font(font_path, size)
        char = str(wi["char"])

        has_glyph = bool(font.metrics(char) and font.metrics(char)[0])
        if has_glyph:
            glyph = font.render(char, True, wi["color"])
            if not (glyph.get_flags() & pygame.SRCALPHA):
                glyph = glyph.convert_alpha()
            # compose onto a fresh surface, multiply alpha
            blended = pygame.Surface(glyph.get_size(), pygame.SRCALPHA)
            blended.blit(glyph, (0, 0))
            blended.fill((255, 255, 255, alpha), special_flags=pygame.BLEND_RGBA_MULT)

            # baseline alignment
            if wi.get("align", "baseline") == "baseline":
                baseline_y = y_top + self.font.get_ascent()
                y = baseline_y - font.get_ascent() + int(wi["offset_y"])
            else:
                baseline_bottom = y_top + line_h
                y = baseline_bottom - blended.get_height() - int(wi["offset_y"])

            x = x_end + int(wi["offset_x"])
            if x + blended.get_width() > viewport.right:
                x = viewport.right - blended.get_width()
            if y < viewport.y:
                y = viewport.y
            layer.blit(blended, (x, y))
        else:
            # vector fallback
            h = max(6, int(line_h * 0.5))
            w = max(6, int(h * 1.1))
            x = x_end + int(wi["offset_x"])
            baseline_bottom = y_top + line_h
            y = baseline_bottom - h - int(wi["offset_y"])
            if x + w > viewport.right:
                x = viewport.right - w
            tri = pygame.Surface((w, h), pygame.SRCALPHA)
            tri.fill((0, 0, 0, 0))
            pygame.draw.polygon(tri, (*wi["color"], alpha), [(0, 0), (w, 0), (w // 2, h)])
            layer.blit(tri, (x, y))
