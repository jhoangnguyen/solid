from __future__ import annotations
from typing import Dict, Tuple, Optional
import pygame

class FontCache:
    """
    Tiny cache for pygame.fontFont objects.
    Keys by (path, size, bold, italic) so theme swaps are cheap.
    """
    def __init__(self) -> None:
        self._cache: Dict[Tuple[Optional[str], int, bool, bool], pygame.font.Font] = {}
        
    def get(self, path: Optional[str], size: int, *, bold: bool=False, italic: bool=False) -> pygame.font.Font:
        key = (path or None, int(size), bool(bold), bool(italic))
        f = self._cache.get(key)
        if f is None:
            f = pygame.font.Font(path, int(size))
            if bold: f.set_bold(True)
            if italic: f.set_italic(True)
            self._cache[key] = f
        return f