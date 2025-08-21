from __future__ import annotations

import os
import sys
import logging
from pathlib import Path
from typing import Dict, Tuple, Optional, Union

import pygame

logger = logging.getLogger(__name__)

# --- Project / assets root ----------------------------------------------------

def _project_root() -> Path:
    """
    Works in dev and with PyInstaller/pyoxidizer-like bundles.
    """
    if getattr(sys, "_MEIPASS", None):  # PyInstaller temp dir
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    # Use this file's directory as anchor and go up to repo root if needed
    return Path(__file__).resolve().parents[1]  # engine/ -> [project root]

_ASSETS_ROOT = _project_root() / "game" / "assets"


def asset_path(*parts: str) -> str:
    """
    Build an absolute path into game/assets. Example:
        asset_path("ui", "menu.png")
    """
    p = _ASSETS_ROOT.joinpath(*parts)
    return str(p)


# --- Image cache + loading ----------------------------------------------------

# Cache key: (relpath, scale, colorkey)
# - relpath: str like "ui/menu.png"
# - scale: None | float | (w,h)
# - colorkey: None | (r,g,b)
_ImageKey = Tuple[str, Union[None, float, Tuple[int, int]], Optional[Tuple[int, int, int]]]
_image_cache: Dict[_ImageKey, pygame.Surface] = {}


def _display_ready() -> bool:
    try:
        return pygame.display.get_init() and pygame.display.get_surface() is not None
    except pygame.error:
        return False


def _convert_for_display(surf: pygame.Surface, colorkey: Optional[Tuple[int, int, int]]) -> pygame.Surface:
    """
    Convert surface to the current display format, preserving alpha if present.
    Apply a color key if provided.
    """
    if not _display_ready():
        # Can't convert yet; return as-is.
        if colorkey is not None:
            surf = surf.copy()
            surf.set_colorkey(colorkey)
        return surf

    # If per-pixel alpha is present, keep it
    if surf.get_alpha() is not None:
        surf = surf.convert_alpha()
    else:
        surf = surf.convert()

    if colorkey is not None:
        surf.set_colorkey(colorkey)

    return surf


def _scaled(surf: pygame.Surface, scale: Union[None, float, Tuple[int, int]]) -> pygame.Surface:
    if scale is None:
        return surf
    if isinstance(scale, (float, int)):
        w, h = surf.get_width(), surf.get_height()
        new_size = (max(1, int(w * scale)), max(1, int(h * scale)))
        return pygame.transform.smoothscale(surf, new_size)
    # Tuple[int,int]
    w, h = scale
    return pygame.transform.smoothscale(surf, (max(1, w), max(1, h)))


def _fallback_surface(size: Tuple[int, int] = (48, 48)) -> pygame.Surface:
    """
    A loud magenta/black checker so missing assets are obvious.
    """
    surf = pygame.Surface(size, pygame.SRCALPHA)
    surf.fill((255, 0, 255))
    pygame.draw.rect(surf, (0, 0, 0), surf.get_rect(), 2)
    # Big X
    pygame.draw.line(surf, (0, 0, 0), (0, 0), (size[0], size[1]), 2)
    pygame.draw.line(surf, (0, 0, 0), (0, size[1]), (size[0], 0), 2)
    return surf


def load_image(
    relpath: str,
    *,
    scale: Union[None, float, Tuple[int, int]] = None,
    colorkey: Optional[Tuple[int, int, int]] = None,
    fallback_size: Tuple[int, int] = (48, 48),
) -> pygame.Surface:
    """
    Load and cache an image from game/assets by relative path, e.g. "ui/menu.png".
    - Auto-converts to display format (convert_alpha() if appropriate).
    - Optional `scale`: float (uniform) or (w,h).
    - Optional `colorkey`: (r,g,b) for transparency if the asset lacks alpha.
    - Returns a visible fallback surface if the file is missing.

    NOTE: If called before setting the display mode, conversion will happen later
    when you call `after_display_init()`.
    """
    key: _ImageKey = (relpath, scale, colorkey)
    cached = _image_cache.get(key)
    if cached is not None:
        return cached

    abs_path = asset_path(*Path(relpath).parts)
    try:
        surf = pygame.image.load(abs_path)
    except Exception as e:
        logger.warning("Could not load image '%s': %s", abs_path, e)
        surf = _fallback_surface(fallback_size)

    # Scale, then convert
    surf = _scaled(surf, scale)
    surf = _convert_for_display(surf, colorkey)

    _image_cache[key] = surf
    return surf


def after_display_init() -> None:
    """
    Call this once right after pygame.display.set_mode(...).
    It re-converts any cached surfaces that were loaded before the display existed.
    """
    if not _display_ready():
        return

    to_update: Dict[_ImageKey, pygame.Surface] = {}
    for key, surf in _image_cache.items():
        relpath, scale, colorkey = key
        # Re-load raw (to ensure best conversion), re-scale, then convert.
        abs_path = asset_path(*Path(relpath).parts)
        try:
            raw = pygame.image.load(abs_path)
        except Exception:
            raw = surf  # keep what we have (likely fallback)
        raw = _scaled(raw, scale)
        conv = _convert_for_display(raw, colorkey)
        to_update[key] = conv

    _image_cache.update(to_update)


# --- (Optional) helpers you'll likely want later ------------------------------

def clear_image_cache() -> None:
    _image_cache.clear()
