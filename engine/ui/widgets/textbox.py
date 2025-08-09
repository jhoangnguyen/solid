"""
engine/ui/widgets/textbox.py

A lightweight, scrollable text box widget for a pure-Python (pygame) VN-style UI.

Features
- Sets/augments text; wraps to viewport width; scrolls with pixels.
- Reflows on resize or theme change; caches rendered line surfaces.
- Theme-aware (font, colors, padding, line spacing).
- Opacity support (0..1) for fades via your Animator/tweens.
- No external deps beyond pygame; safe to use from a simple main loop.

Expected companion:
- engine/ui/style.py defines Theme with fields used here:
  - font_path: str | None
  - font_size: int
  - text_rgb: tuple[int,int,int]
  - box_bg: tuple[int,int,int]
  - box_border: tuple[int,int,int]
  - border_radius: int
  - padding: (top, right, bottom, left)
  - line_spacing: int
"""

from __future__ import annotations

from typing import List
import pygame

from engine.ui.style import Theme


class TextBox:
    """
    A simple, scrollable text container.

    Public API
    ----------
    set_text(text: str) -> None
    append_text(text: str) -> None
    clear() -> None

    on_resize(new_rect: pygame.Rect) -> None
    set_theme(theme: Theme) -> None

    scroll(dy: float) -> None
    scroll_to_top() -> None
    scroll_to_bottom() -> None

    draw(surface: pygame.Surface) -> None

    Properties
    ----------
    rect: pygame.Rect
    opacity: float      # 0..1, affects entire widget (bg + text)
    content_height: int
    viewport_height: int
    max_scroll(): float
    is_at_top / is_at_bottom
    """

    __slots__ = (
        "rect",
        "theme",
        "font",
        "scroll_y",
        "_cache_wrap_w",
        "_cache_surfaces",
        "_content_h",
        "_text",
        "opacity",
    )

    def __init__(self, rect: pygame.Rect, theme: Theme):
        self.rect = rect.copy()
        self.theme: Theme = theme
        self.font = pygame.font.Font(theme.font_path, theme.font_size)

        # scrolling (in pixels)
        self.scroll_y: float = 0.0

        # render cache
        self._cache_wrap_w: int = -1
        self._cache_surfaces: List[pygame.Surface] = []
        self._content_h: int = 0

        # content
        self._text: str = ""

        # effects
        self.opacity: float = 1.0

    # -------------------------- Public API --------------------------

    def set_text(self, text: str) -> None:
        self._text = text or ""
        self.scroll_y = 0.0
        self._invalidate_layout()

    def append_text(self, text: str) -> None:
        if not text:
            return
        self._text = (self._text + ("\n" if self._text else "") + text)
        self._invalidate_layout()

    def clear(self) -> None:
        self._text = ""
        self.scroll_y = 0.0
        self._invalidate_layout()

    def on_resize(self, new_rect: pygame.Rect) -> None:
        """Update geometry; layout is recomputed lazily on draw()."""
        self.rect = new_rect.copy()
        self._invalidate_layout()

    def set_theme(self, theme: Theme) -> None:
        """Swap to a new theme (colors/font/spacing)."""
        self.theme = theme
        self._invalidate_layout(rebuild_font=True)

    def scroll(self, dy: float) -> None:
        """Scroll by dy pixels (positive = down)."""
        if dy == 0:
            return
        self.scroll_y = max(0.0, min(self.max_scroll(), self.scroll_y + dy))

    def scroll_to_top(self) -> None:
        self.scroll_y = 0.0

    def scroll_to_bottom(self) -> None:
        self.scroll_y = self.max_scroll()

    # Properties
    @property
    def content_height(self) -> int:
        return int(self._content_h)

    @property
    def viewport_height(self) -> int:
        t, r, b, l = self.theme.padding
        return max(0, self.rect.h - (t + b))

    @property
    def is_at_top(self) -> bool:
        return self.scroll_y <= 0.0 + 1e-3

    @property
    def is_at_bottom(self) -> bool:
        return self.scroll_y >= self.max_scroll() - 1e-3

    # --------------------------- Drawing ---------------------------

    def draw(self, surface: pygame.Surface) -> None:
        """
        Render the textbox into an offscreen layer, then blit with optional opacity.

        This avoids re-rendering text for alpha effects and keeps clipping simple.
        """
        th = self.theme
        if self.rect.w <= 0 or self.rect.h <= 0:
            return  # nothing to draw

        # Offscreen layer with per-pixel alpha
        layer = pygame.Surface(self.rect.size, pygame.SRCALPHA)

        # Background + border
        full = pygame.Rect(0, 0, self.rect.w, self.rect.h)
        pygame.draw.rect(layer, th.box_bg, full, border_radius=th.border_radius)
        pygame.draw.rect(layer, th.box_border, full, width=1, border_radius=th.border_radius)

        # Inner viewport (relative to layer)
        t, r, b, l = th.padding
        viewport = pygame.Rect(l, t, max(0, self.rect.w - (l + r)), max(0, self.rect.h - (t + b)))

        # Ensure we have layout for current width
        self._ensure_layout(viewport.width)

        # Clip and blit visible lines
        prev_clip = layer.get_clip()
        layer.set_clip(viewport)

        y = viewport.y - int(self.scroll_y)
        line_gap = th.line_spacing
        for line_surf in self._cache_surfaces:
            h = line_surf.get_height()
            if y + h >= viewport.y and y <= viewport.bottom:
                layer.blit(line_surf, (viewport.x, y))
            y += h + line_gap

        layer.set_clip(prev_clip)

        # Opacity
        if self.opacity < 1.0:
            layer.set_alpha(int(255 * max(0.0, min(1.0, self.opacity))))

        # Present
        surface.blit(layer, self.rect.topleft)

    # -------------------------- Internals --------------------------

    def max_scroll(self) -> float:
        """Maximum scroll offset in pixels given current content and viewport."""
        return max(0.0, float(self._content_h - self.viewport_height))

    def _invalidate_layout(self, rebuild_font: bool = False) -> None:
        if rebuild_font:
            # rebuild font for new size / path
            self.font = pygame.font.Font(self.theme.font_path, self.theme.font_size)
        self._cache_wrap_w = -1  # force rebuild at next draw

    def _ensure_layout(self, wrap_w: int) -> None:
        """(Re)build wrapped line surfaces if width or content changed."""
        # Guard against zero/negative width (e.g., very small window)
        if wrap_w <= 0:
            self._cache_wrap_w = wrap_w
            self._cache_surfaces = []
            self._content_h = 0
            self.scroll_y = 0.0
            return

        if wrap_w == self._cache_wrap_w:
            return

        # (Re)create font to reflect theme changes (cheap in pygame)
        self.font = pygame.font.Font(self.theme.font_path, self.theme.font_size)

        self._cache_wrap_w = wrap_w
        wrapped_lines = self._wrap_text(self._text, wrap_w)

        # Render all lines once (subsequent draws just blit)
        color = self.theme.text_rgb
        render = self.font.render
        self._cache_surfaces = [render(line, True, color) for line in wrapped_lines]

        # Compute total content height
        line_gap = self.theme.line_spacing
        if self._cache_surfaces:
            heights = [surf.get_height() for surf in self._cache_surfaces]
            self._content_h = sum(heights) + (len(heights) - 1) * line_gap
        else:
            self._content_h = 0

        # Clamp scroll if content shrank
        self.scroll_y = min(self.scroll_y, self.max_scroll())

    def _wrap_text(self, text: str, wrap_w: int) -> List[str]:
        """
        Word-wrap text for the given width in pixels.

        - Respects existing '\n'.
        - Splits overlong "words" with a binary search into fitting chunks.
        - Keeps empty lines.
        """
        if not text:
            return []

        out: List[str] = []
        measure = self.font.size

        for raw in text.splitlines():
            words = raw.split(" ")
            if not words:
                out.append("")  # preserve empty line
                continue

            cur = ""
            for w in words:
                cand = w if not cur else f"{cur} {w}"
                if measure(cand)[0] <= wrap_w:
                    cur = cand
                    continue

                # current line full; flush it
                if cur:
                    out.append(cur)
                # handle long single word
                if measure(w)[0] <= wrap_w:
                    cur = w
                else:
                    chunks = self._hard_wrap_long_word(w, wrap_w, measure)
                    # all chunks except last are complete lines
                    out.extend(chunks[:-1])
                    cur = chunks[-1] if chunks else ""

            out.append(cur)

        return out

    def _hard_wrap_long_word(
        self, word: str, wrap_w: int, measure
    ) -> List[str]:
        """
        Split a single long token into chunks that fit wrap_w using binary search.
        Returns a list of chunks (no hyphen inserted).
        """
        parts: List[str] = []
        i = 0
        n = len(word)
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
            seg = word[i:i + best]
            if not seg:
                break
            parts.append(seg)
            i += best
        return parts
