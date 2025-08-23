from __future__ import annotations
from typing import List, Tuple, Optional
from engine.ui.style import Theme
from engine.ui.fonts import FontCache, FontKey
import pygame
import re

_TAG_RE = re.compile(r"\{(/?)(b|i)\}")

class TextLayout:
    """
    Wrap + Render helper that centralizes all text measurement rules.
    - Uses a FontCache (passed in) for font objects
    - Knows the active theme (font path/size, colors, line spacing)
    - Provides wrap() and render() building blocks, plus convenience layout()
    """
    
    def __init__(self, fonts: FontCache, theme: Theme):
        self.fonts = fonts
        self.theme = theme
        self.font = self.fonts.get(theme.font_path, theme.font_size)
        
    # --- Theme / Font ---
    def set_theme(self, theme: Theme) -> None:
        self.theme = theme
        self.font = self.fonts.get(theme.font_path, theme.font_size)
        
    # --- Public API ---
    def wrap(self, text: str, wrap_w: int) -> List[str]:
        """
        Soft-wrap on spaces, with a hard-wrap fallback for very long words.
        Returns the wrapped lines (strings) including markup tags.
        Width measurements ignore the tags (use visible text width).
        """
        if wrap_w <= 0:
            return [text] if text else []
        if not text:
            return []

        out: List[str] = []
        measure = self.font.size  # width of *visible* text; feed stripped strings here

        for raw in text.splitlines():
            words = raw.split(" ")
            if not words:
                out.append("")
                continue

            cur = ""
            for w in words:
                cand = w if not cur else f"{cur} {w}"
                # measure *visible* candidate (tags stripped)
                if measure(self._strip_markup(cand))[0] <= wrap_w:
                    cur = cand
                else:
                    if cur:
                        out.append(cur)
                    # Try the word alone
                    if measure(self._strip_markup(w))[0] <= wrap_w:
                        cur = w
                    else:
                        # Hard wrap the (possibly marked-up) "word"
                        chunks = self._hard_wrap_long_word(w, wrap_w, measure)
                        if chunks:
                            out.extend(chunks[:-1])
                            cur = chunks[-1]
                        else:
                            cur = ""
            out.append(cur)

        return out
    
    def render_lines(self, lines: List[str], color: Optional[Tuple[int, int, int]] = None) -> Tuple[List[pygame.Surface], int]:
        """
        Render already-wrapped lines to surfaces asnd compute their stacked height
        using theme.line_spacing between lines.
        """
        # color = color or self.theme.text_rgb
        # render = self.font.render
        # surfs = [render(line, True, color) for line in (lines or [])]
        # gap = self.theme.line_spacing
        # height = sum(s.get_height() for s in surfs) + (len(surfs) - 1) * gap if surfs else 0
        # return surfs, height
        surfs: list[pygame.Surface] = []
        total_h = 0
        gap = int(getattr(self.theme, "line_spacing", 0))
        for i, line in enumerate(lines):
            srf = self.render_line_with_markup(line, color=color)
            surfs.append(srf)
            total_h += srf.get_height()
            if i < len(lines) - 1:
                total_h += gap
        return surfs, total_h
    
    def layout(self, text: str, wrap_w: int, color: Optional[Tuple[int, int, int]] = None) -> Tuple[List[pygame.Surface], int]:
        """
        Convenience: Wrap + Render in one go.
        """
        lines = self.wrap(text or "", wrap_w)
        return self.render_lines(lines, color=color)
    
    def wrap_lines(self, raw_text: str, wrap_w: int, fonts: FontCache, key: FontKey) -> List[str]:
        """ Soft-wrap by spaces, hard-wrap long words; preserve explicit newlines. """
        if wrap_w <= 0 or not raw_text:
            return [] if not raw_text else raw_text.splitlines()
        size = fonts.measure
        out: List[str] = []
        for raw in (raw_text or "").splitlines():
            words = raw.split(" ")
            if not words:
                out.append("")
                continue
            cur = ""
            for w in words:
                cand = w if not cur else f"{cur} {w}"
                if size(key, cand)[0] <= wrap_w:
                    cur = cand
                else:
                    if cur:
                        out.append(cur)
                    if size(key, w)[0] <= wrap_w:
                        cur = w
                    else:
                        chunks = self._hard_wrap_long_word(w, wrap_w, lambda s: size(key, s)[0])
                        out.extend(chunks[:-1])
            out.append(cur)
        return out
                
    def render_wrapped(self, raw_text: str, wrap_w: int, line_spacing: int, color: Tuple[int, int, int], fonts: FontCache, key: FontKey) -> Tuple[List, int]:
        """ Return [Surface,...] for each wrapped line + total height with spacing. """
        lines = self.wrap_lines(raw_text, wrap_w, fonts, key)
        surfaces = [fonts.render(key, ln, color) for ln in lines]
        if not surfaces:
            return [], 0
        heights = [s.get_height() for s in surfaces]
        total_h = sum(heights) + (len(surfaces) - 1) * max(0, line_spacing)
        return surfaces, total_h
        
    def measure_wrapped(self, raw_text: str, wrap_w: int, line_spacing: int, fonts: FontCache, key: FontKey) -> Tuple[List[int], int]:
        """ Return [line_heights,...] + total height (no renders). """
        lines = self.wrap_lines(raw_text, wrap_w, fonts, key)
        # Fast measure via a representative glyph (height), using font.get_height()
        # but to be safe with tall glyphs, measure each line:
        line_heights = [fonts.get_by_key(key).get_height() if ln == "" else fonts.measure(key, ln)[1] for ln in lines]
        total_h = sum(line_heights) + (len(line_heights) - 1) * max(0, line_spacing)
        return line_heights, total_h
        
    # --- Cursor/Indicator Helpers ---
    
    def line_height(self) -> int:
        # Rough line box height based on current font; line-spacing is theme-controlled.
        return self.font.get_linesize()
    
    def ascent(self) -> int:
        return self.font.get_ascent()
    
    # --- Internals ---
    def _hard_wrap_long_word(self, word: str, wrap_w: int, measure) -> List[str]:
        parts: List[str] = []
        i, n = 0, len(word)
        while i < n:
            lo, hi = 1, n - i
            best = 1
            while lo <= hi:
                mid = (lo + hi) // 2
                seg = word[i:i + mid]
                # measure *visible* text width
                if measure(self._strip_markup(seg))[0] <= wrap_w:
                    best = mid
                    lo = mid + 1
                else:
                    hi = mid - 1
            seg = word[i:i + best]
            if not seg:
                break
            parts.append(seg)
            i += best
        return parts
    
    def _strip_markup(self, s: str) -> str:
        # Remove {b}, {/b}, {i}, {/i}
        return _TAG_RE.sub("", s or "")
    
    def _parse_markup(self, s: str):
        """
        Parse {b}/{/b}/{i}/{/i} tags into runs.
        Returns list of (text, bold, italic).
        """
        out = []
        bold = italic = False
        buf = []
        i = 0
        for m in _TAG_RE.finditer(s):
            if m.start() > i:
                buf.append(s[i:m.start()])
            if buf:
                out.append(("".join(buf), bold, italic))
                buf = []
            closing, which = m.groups()  # closing == "/" for {/x}, "" for {x}
            is_close = (closing == "/")
            if which == "b":
                bold = not is_close
            elif which == "i":
                italic = not is_close
            i = m.end()
        if i < len(s):
            buf.append(s[i:])
        if buf:
            out.append(("".join(buf), bold, italic))
        return [(t, b, it) for (t, b, it) in out if t]
    
    def measure_prefix_widths_for_line(self, s: str) -> list[int]:
        """
        Per-character cumulative widths for a markup line.
        Uses kerning-aware substring measurements within each run so clipping matches
        the composed surface width exactly.
        """
        widths = [0]
        base_path = getattr(self.theme, "font_path", None)
        base_px = int(getattr(self.theme, "font_size", 22))

        base = 0  # cumulative width so far across runs
        for text, is_bold, is_ital in self._parse_markup(s):
            if not text:
                continue
            try:
                f = self.fonts.get(base_path, base_px, bold=is_bold, italic=is_ital)
            except TypeError:
                f = self.fonts.get(base_path, base_px)

            # IMPORTANT: measure substrings, not single chars (respects kerning)
            for i in range(1, len(text) + 1):
                widths.append(base + f.size(text[:i])[0])

            base = widths[-1]  # advance cumulative base for next run

        return widths

    def render_line_with_markup(self, s: str, color: Optional[tuple[int,int,int]] = None) -> pygame.Surface:
        """
        Render a single markup line into one surface by blitting styled runs side-by-side.
        """
        runs = self._parse_markup(s)
        if not runs:
            runs = [(self._strip_markup(s), False, False)]
        # choose a baseline font for line height
        base_font = self.fonts.get(getattr(self.theme, "font_path", None),
                                int(getattr(self.theme, "font_size", 22)))
        line_h = base_font.get_linesize()
        # render runs
        run_surfs = []
        total_w = 0
        for text, b, it in runs:
            if not text:
                continue
            f = self.fonts.get(getattr(self.theme, "font_path", None),
                            int(getattr(self.theme, "font_size", 22)),
                            bold=b, italic=it)
            surf = f.render(text, True, color or getattr(self.theme, "text_rgb", (237, 237, 237)))
            if not (surf.get_flags() & pygame.SRCALPHA):
                surf = surf.convert_alpha()
            run_surfs.append(surf)
            total_w += surf.get_width()
            line_h = max(line_h, surf.get_height())
        # compose
        out = pygame.Surface((max(1, total_w), max(1, line_h)), pygame.SRCALPHA)
        x = 0
        for srf in run_surfs:
            out.blit(srf, (x, 0))
            x += srf.get_width()
        return out