from __future__ import annotations
from typing import List, Tuple, Optional
from engine.ui.style import Theme
from engine.ui.fonts import FontCache
import pygame

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
        Returns the wrawpped lines (strings).
        """
        if wrap_w <= 0:
            return [text] if text else []
        
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
                    # Try word alone
                    if measure(w)[0] <= wrap_w:
                        cur = w
                    else:
                        # Hard wrap the word into chunks
                        chunks = self._hard_wrap_long_word(w, wrap_w, measure)
                        out.extend(chunks[:-1])
                        cur = chunks[-1] if chunks else ""
            out.append(cur)
            
        return out
    
    def render_lines(self, lines: List[str], color: Optional[Tuple[int, int, int]] = None) -> Tuple[List[pygame.Surface], int]:
        """
        Render already-wrapped lines to surfaces asnd compute their stacked height
        using theme.line_spacing between lines.
        """
        color = color or self.theme.text_rgb
        render = self.font.render
        surfs = [render(line, True, color) for line in (lines or [])]
        gap = self.theme.line_spacing
        height = sum(s.get_height() for s in surfs) + (len(surfs) - 1) * gap if surfs else 0
        return surfs, height
    
    def layout(self, text: str, wrap_w: int, color: Optional[Tuple[int, int, int]] = None) -> Tuple[List[pygame.Surface], int]:
        """
        Convenience: Wrap + Render in one go.
        """
        lines = self.wrap(text or "", wrap_w)
        return self.render_lines(lines, color=color)
    
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
                if measure(seg)[0] <= wrap_w:
                    best = mid
                    lo = mid + 1
                else:
                    hi = mid - 1
            seg = word[i:i+best]
            if not seg:
                break
            parts.append(seg)
            i += best
        return parts