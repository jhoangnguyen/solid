from __future__ import annotations
from dataclasses import dataclass
from collections import OrderedDict
from typing import Tuple, Optional
import pygame

@dataclass(frozen=True)
class FontKey:
    path: Optional[str]
    size: int
    bold: bool = False
    italic: bool = False

class FontCache:
    """
    Tiny LRU cache for pygame.font.Font objects keyed by FontKey.
    Usage patterns supported:
      - font = fonts.get(path, size, bold=False, italic=False)
      - key  = fonts.key(path, size, bold=False, italic=False)
        surf = fonts.render(key, "Hello", (255,255,255))
        w,h  = fonts.measure(key, "Hello")
    """

    def __init__(self, max_entries: int = 64) -> None:
        self._cache: "OrderedDict[FontKey, pygame.font.Font]" = OrderedDict()
        self._max = max(1, int(max_entries))

    # ---------- Public: acquire fonts ----------
    def key(
        self,
        path: Optional[str],
        size: int,
        *,
        bold: bool = False,
        italic: bool = False,
    ) -> FontKey:
        """Create a normalized FontKey (helper for render/measure)."""
        return FontKey(path, int(size), bool(bold), bool(italic))

    def get(
        self,
        path: Optional[str],
        size: int,
        *,
        bold: bool = False,
        italic: bool = False,
    ) -> pygame.font.Font:
        """Get a pygame.font.Font for immediate use (cached)."""
        return self._get_by_key(self.key(path, size, bold=bold, italic=italic))

    # ---------- Public: draw/measure via key ----------
    def render(
        self,
        k: FontKey,
        text: str,
        color: Tuple[int, int, int],
        aa: bool = True,
    ) -> pygame.Surface:
        """Render text to a Surface using a cached font."""
        font = self._get_by_key(k)
        return font.render(text or "", aa, color)

    def measure(self, k: FontKey, text: str) -> Tuple[int, int]:
        """Return (width, height) of text using the cached font."""
        font = self._get_by_key(k)
        return font.size(text or "")

    def ascent(self, k: FontKey) -> int:
        return self._get_by_key(k).get_ascent()

    def descent(self, k: FontKey) -> int:
        return self._get_by_key(k).get_descent()

    # ---------- Cache management ----------
    def clear(self) -> None:
        self._cache.clear()

    def set_max_entries(self, n: int) -> None:
        self._max = max(1, int(n))
        self._shrink()

    # ---------- Internals ----------
    def _get_by_key(self, k: FontKey) -> pygame.font.Font:
        f = self._cache.get(k)
        if f is not None:
            # touch for LRU
            self._cache.move_to_end(k)
            return f

        # Create and configure new font
        f = pygame.font.Font(k.path, k.size)
        if k.bold:
            f.set_bold(True)
        if k.italic:
            f.set_italic(True)

        # Insert and enforce LRU size
        self._cache[k] = f
        self._shrink()
        return f

    def _shrink(self) -> None:
        while len(self._cache) > self._max:
            self._cache.popitem(last=False)