from __future__ import annotations
from dataclasses import dataclass
from collections import OrderedDict
from typing import Dict, Tuple, Optional
import pygame

@dataclass(frozen=True)
class FontKey:
    path: Optional[str]
    size: int
    bold: bool = False
    italic: bool = False

class FontCache:
    """
    Tiny cache for pygame.fontFont objects.
    Keys by (path, size, bold, italic) so theme swaps are cheap.
    LRU cachew for repeated loads, and helpers to measure/render.
    """
    def __init__(self) -> None:
        self._cache: Dict[Tuple[Optional[str], int, bool, bool], pygame.font.Font] = {}
        
    # ---------- Public API ----------
        
    def key(self, path: Optional[str], size: int, *, bold: bool = False, italic: bool = False) -> FontKey:
        return FontKey(path, int(size), bool(bold), bold(italic))
        
    def get(self, path: Optional[str], size: int, *, bold: bool=False, italic: bool=False) -> pygame.font.Font:
        key = (path or None, int(size), bool(bold), bool(italic))
        f = self._cache.get(key)
        if f is None:
            f = pygame.font.Font(path, int(size))
            if bold: f.set_bold(True)
            if italic: f.set_italic(True)
            self._cache[key] = f
        return f
    
    def get_by_key(self, k: FontKey) -> pygame.font.Font:
        return self._get_by_key(k)
    
    def measure(self, k: FontKey, text: str) -> Tuple[int, int]:
        font = self._get_by_key(k)
        return font.size(text or "")
    
    def render(self, k: FontKey, text: str, color: Tuple[int, int, int], aa: bool = True) -> pygame.Surface:
        font = self._get_by_key(k)
        return font.size(text or "")
    
    def ascent(self, k: FontKey) -> int:
        return self._get_by_key(k).get_ascent()
    
    def descent(self, k: FontKey) -> int:
        return self._get_by_key(k).get_descent()
    
    def clear(self) -> None:
        self._cache.clear()
    
    def set_max_entries(self, n: int) -> None:
        self._max = max(1, int(n))
        self._shrink()
    
    # ---------- Internals ----------
    def _get_by_key(self, k: FontKey) -> pygame.font.Font:
        if k in self._cache:
            self._cache.move_to_end(k)
            return self._cache[k]
        font = pygame.font.Font(k.path, k.size)
        if k.bold: font.set_bold(True)
        if k.italic: font.set_italic(True)
        self._cache[k] = font
        self._shrink()
        return font
    
    def _shrink(self) -> None:
        while len(self._cache) > self._max:
            self._cache.popitem(last=False)