from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional
import pygame
import math
import bisect

from engine.ui.style import Theme
from engine.ui.text_model import Entry
from engine.ui.text_layout import TextLayout
from engine.ui.fonts import FontCache
from engine.ui.background_manager import BackgroundManager

def _ease_out_cubic(t: float) -> float:
    t = 0.0 if t < 0.0 else 1.0 if t > 1.0 else t
    return 1 - (1 - t) ** 3

@dataclass
class _Layout:
    surfaces: List[pygame.Surface]
    height: int                         # sum(heights) + (lines-1)*line_spacing
    lines: List[str]                    # Wrapped strings (for typing)
    prefix_w: List[List[int]]           # Per-line prefix widths for fast clipping
    total_chars: int                    # Sum of len(lines) over wrapped lines

class TextView:
    """
    Pure rendering + layout cache for a list of Entries.

    Responsibilities:
    - wrap text to width
    - render lines with animation (fade + slide)
    - draw the wait-for-input indicator
    - compute content height (inc. Theme.entry_gap)
    """
    def __init__(self, theme: Theme, fonts: FontCache):
        self.theme = theme
        self.fonts = fonts
        self.layout = TextLayout(fonts, theme)
        
        self._wrap_w: int = -1
        self._cache: Dict[Entry, _Layout] = {}
        self._blink_t: float = 0.0  # for wait-indicator
        
        self._bg_manager = None
        self._bg_slot = None
        # wait-indicator glyph cache
        self._wi_cache = {
            "char": None, "size": None, "color": None, "font_path": None,
            "glyph": None, "font": None
        }

    # --------- public ---------
    def set_theme(self, theme: Theme) -> None:
        self.theme = theme
        self.layout.set_theme(theme)
        self.invalidate_layout()
        
    def set_background_slot(self, bg_manager: BackgroundManager, slot: str) -> None:
        """ Make this view ask a BackgroundManager slot to paint the panel. """
        self._bg_manager = bg_manager
        self._bg_slot = slot

    def update(self, dt: float) -> None:
        self._blink_t += dt
        
    def invalidate_layout(self) -> None:
        self._wrap_w = -1
        self._cache.clear()

    def ensure_layout(self, wrap_w: int, entries: List[Entry]) -> None:
        """
        Make sure we have wrapped+rendered layouts for all `entries` at `wrap_w`.
        If width changed, rewrap everything we see; otherwise only build missing ones.
        """
        if wrap_w <= 0:
            self._wrap_w = wrap_w
            self._cache.clear()
            return

        # Always grab the font via FontCache (in case theme changed)
        _ = self.layout.font

        if wrap_w != self._wrap_w:
            # Width changed -> rewrap/re-render the entries we were asked about.
            self._wrap_w = wrap_w
            self._cache.clear()
            for e in entries:
                self._cache[e] = self._layout_entry(e, wrap_w)
        else:
            # Width unchanged -> add any new entries that aren't cached yet.
            for e in entries:
                if e not in self._cache:
                    self._cache[e] = self._layout_entry(e, wrap_w)
            stale = [k for k in self._cache.keys() if k not in entries]
            for k in stale: self._cache.pop(k, None)


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
        # Background + border
        full = pygame.Rect(0, 0, widget_rect.w, widget_rect.h)
        
        use_managed_bg = (
            self._bg_manager is not None
            and self._bg_slot is not None
            and getattr(self._bg_manager, "slot_has_image")(self._bg_slot)
        )
        
        if use_managed_bg:
            # Ensure rounded corners if the ImageBrush clips the rect
            if hasattr(self._bg_manager, "_slot"):
                ch = self._bg_manager._slot(self._bg_slot)
                ch.current.radius = getattr(self.theme, "border_radius", 12)
                if ch.next:
                    ch.next.radius = getattr(self.theme, "border_radius", 12)
            self._bg_manager.draw_slot(self._bg_slot, layer, full)
        else:
              # Fallback to the original themed box
            pygame.draw.rect(layer, self.theme.box_bg, full, border_radius=self.theme.border_radius)
   
            
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
            # Is this a typewriter entry? (This will be eoncded as animated with no slide)
            is_typing = (e.duration > 0 and e.offset_px == 0)
            u = 1.0 if e.duration <= 0 else _ease_out_cubic(e.t / e.duration)
            offset = 0 if is_typing else int((1.0 - u) * e.offset_px)
            alpha = 255 if is_typing else int(255 * u)
            
            if not is_typing:
                chars_to_show = lay.total_chars
            else:
                if getattr(e, "cm_reveal", None):
                    frac = max(0.0, min(1.0, (e.t / e.duration) if e.duration > 0 else 1.0))
                    # cm_reveal has length N + 1; find larges index where cm <= frac
                    chars_to_show = bisect.bisect_right(e.cm_reveal, frac) - 1
                    chars_to_show = max(0, min(lay.total_chars, chars_to_show))
                else:
                    # Fallback: proportional to time (no punctuation weighting)
                    frac = max(0.0, min(1.0, e.t / e.duration)) if e.duration > 0 else 1.0
                    chars_to_show = int(round(lay.total_chars * frac))

            for j, surf in enumerate(lay.surfaces):
                h = surf.get_height()

                # bookmark ▼ position for the last line of the last visible entry
                if e.wait_for_input and e.t >= e.duration - 1e-4 \
                   and j == len(lay.surfaces) - 1 and idx_entry == len(entries) - 1:
                    indicator_pos = (viewport.x + surf.get_width(), y + offset, h)

                if y + h + offset >= viewport.y and y + offset <= viewport.bottom:
                    if is_typing:
                        # Determine how many chars of this wrapped line are visible
                        line_len = len(lay.lines[j])
                        show_in_line = max(0, min(line_len, chars_to_show))
                        if show_in_line > 0:
                            w_clip = lay.prefix_w[j][show_in_line]
                            prev_alpha = surf.get_alpha()
                            surf.set_alpha(alpha)
                            layer.blit(surf, (viewport.x, y + offset), area=pygame.Rect(0, 0, w_clip, h))
                            surf.set_alpha(prev_alpha)
                        # Consume budget for next lines in this entry
                        chars_to_show = max(0, chars_to_show - line_len)
                    else:
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
        # Wrap, render, and precompute prefix widths for fast typewriter clipping
        lines = self.layout.wrap(e.text or "", wrap_w)
        surfaces, height = self.layout.render_lines(lines)
        measure = self.layout.font.size
        
        prefix_w: List[List[int]] = []
        for s in lines:
            widths = [0]
            for i in range(1, len(s) + 1):
                widths.append(measure(s[:i])[0])
            prefix_w.append(widths)
        
        total_chars = sum(len(s) for s in lines)
        return _Layout(surfaces, height, lines, prefix_w, total_chars)

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
        char = str(wi["char"])
        cache = self._wi_cache
        if (cache["char"], cache["size"], cache["color"], cache["font_path"]) != (char, size, tuple(wi["color"]), font_path):
            cache["font"] = self.fonts.get(font_path, size)
            cache["glyph"] = cache["font"].render(char, True, wi["color"])
            cache["char"], cache["size"], cache["color"], cache["font_path"] = char, size, tuple(wi["color"]), font_path
        font = cache["font"]
        glyph = cache["glyph"]
        has_glyph = glyph is not None and glyph.get_width() > 0
        if has_glyph:
            if not (glyph.get_flags() & pygame.SRCALPHA):
                glyph = glyph.convert_alpha()
            # compose onto a fresh surface, multiply alpha
            blended = pygame.Surface(glyph.get_size(), pygame.SRCALPHA)
            blended.blit(glyph, (0, 0))
            blended.fill((255, 255, 255, alpha), special_flags=pygame.BLEND_RGBA_MULT)

            # baseline alignment
            if wi.get("align", "baseline") == "baseline":
                baseline_y = y_top + self.layout.ascent()
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
