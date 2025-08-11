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

from typing import List, Deque, Optional
from collections import deque
import pygame
import math

from engine.ui.style import Theme
from dataclasses import dataclass


def _clamp01(x: float) -> float:
    return 0.0 if x < 0.0 else 1.0 if x > 1.0 else x

def _ease_out_cubic(t: float) -> float:
    t = _clamp01(t)
    return 1 - (1 - t) ** 3

@dataclass
class RevealParams:
    per_line_delay: float = 0.15
    intro_duration: float = 0.18
    intro_offset_px: int = 10
    stick_to_bottom_threshold_px: int = 24

@dataclass
class _Entry:
    text: str
    
    # Layout
    surfaces: List[pygame.Surface]
    height: int             # Total pixel height including line gaps
    
    # Animation
    t: float = 0.0          # 0..duration
    duration: float = 0.18
    offset_px: int = 10
    
    # State
    visible: bool = False   # Becomes True when released from queue
    
    wait_for_input: bool = False

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
        "opacity",
        "_content_h",
        "_text",
        "_wrap_w",
        "_entries_visible",
        "_entries_pending",
        "_release_timer",
        "_reveal_params",
    )

    def __init__(self, rect: pygame.Rect, theme: Theme, reveal: Optional[RevealParams]=None):
        self.rect = rect.copy()
        self.theme: Theme = theme
        self.font = pygame.font.Font(theme.font_path, theme.font_size)

        # scrolling (in pixels)
        self.scroll_y: float = 0.0

        # effects
        self.opacity: float = 1.0
        
        # Layout
        self._wrap_w: int = -1
        self._entries_visible: List[_Entry] = []
        self._entries_pending: Deque[_Entry] = deque()
        self._content_h: int = 0
        self._release_timer: float = 0.0
        
        self._reveal_params = reveal or RevealParams()

    # -------------------------- Public API --------------------------
    
    def set_reveal_params(self, rp: RevealParams) -> None:
        self._reveal_params = rp

    def set_text(self, text: str) -> None:
        """Immediate replace (no animation), useful for debug or static screens."""
        self.clear()
        e = self._make_entry(text, animated=False)
        e.visible = True
        e.t = e.duration
        self._entries_visible.append(e)
        self._recalc_content_height()
        self.scroll_to_top()
        
    def queue_lines(self, text_block: str, wait_for_input: bool = False) -> None:
        """Split on newline and enqueue each logical line with animation."""
        for line in (text_block or "").splitlines():
            self.append_line(line, animated=True, wait_for_input=wait_for_input)
            
    def append_line(self, line: str, animated: bool = True, wait_for_input: bool = False) -> None:
        e = self._make_entry(line, animated=animated, wait_for_input=wait_for_input)
        if animated or wait_for_input:
            self._entries_pending.append(e)
        else:
            e.visible = True
            e.t = e.duration
            self._entries_visible.append(e)
            self._recalc_content_height()
            if self._should_stick_to_bottom():
                self.scroll_to_bottom()

    def clear(self) -> None:
        self._entries_visible.clear()
        self._entries_pending.clear()
        self._content_h = 0
        self.scroll_y = 0.0
        self._release_timer = 0

    def on_resize(self, new_rect: pygame.Rect) -> None:
        # remember where we were before changing geometry
        was_bottom = self._near_bottom()
        old_max = max(1e-6, self.max_scroll())
        ratio = self.scroll_y / old_max  # 0..1

        # apply new geometry
        self.rect = new_rect.copy()

        # force relayout NOW for the new width so max_scroll() is accurate
        self._wrap_w = -1
        self._ensure_layout(self._viewport_width())

        # restore position
        if was_bottom:
            self.scroll_to_bottom()
        else:
            self.scroll_y = self.max_scroll() * ratio

    def set_theme(self, theme: Theme) -> None:
        """Swap to a new theme (colors/font/spacing)."""
        self.theme = theme
        self.font = pygame.font.Font(theme.font_path, theme.font_size)
        self._wrap_w = -1   # Force relayout
        
    def update(self, dt: float) -> None:
        """Advance line intro animations and release queued lines over time."""
        if dt <= 0: return
        rp = self._reveal_params
        
        # Release next line when last visible is done + delay
        if self._entries_pending:
            first = self._entries_pending[0]
            if not first.wait_for_input:
                # last_done = (not self._entries_visible) or self._entries_visible[-1]
                last_done = (not self._entries_visible) or (self._entries_visible[-1].t >= self._entries_visible[-1].duration - 1e-4)
                if last_done:
                    self._release_timer += dt
                    if self._release_timer >= rp.per_line_delay:
                        self._release_timer = 0.0
                        was_bottom = self._near_bottom()
                        nxt = self._entries_pending.popleft()
                        nxt.visible = True
                        self._entries_visible.append(nxt)
                        self._recalc_content_height()
                        if was_bottom:
                            self.scroll_to_bottom()
                        
        animating = False
        for e in self._entries_visible:
            if e.t < e.duration:
                e.t = min(e.duration, e.t + dt)
                animating = True
        
        # If user is near the bottom, keep bottom anchored to avoid clipping during slide
        if animating and self._should_stick_to_bottom():
            self.scroll_to_bottom()
            
    def on_player_press(self) -> None:
        # A) if the newest visible line is mid-animation, finish it
        if self._entries_visible:
            last = self._entries_visible[-1]
            if last.t < last.duration:
                last.t = last.duration
                # don't return; also release the next line so one press always advances

        # B) release the next queued line (manual or auto)
        if self._entries_pending:
            was_bottom = self._near_bottom()
            self._release_timer = 0.0  # skip auto delay
            nxt = self._entries_pending.popleft()
            nxt.visible = True
            self._entries_visible.append(nxt)
            self._recalc_content_height()
            if was_bottom:
                self.scroll_to_bottom()
                
    def advance_line_now(self) -> None:
        """Immediately show the next queued line (e.g., on click)."""
        self._release_timer = 0.0
        if self._entries_pending:
            nxt = self._entries_pending.popleft()
            nxt.visible = True
            self._entries_visible.append(nxt)
            self._recalc_content_height()
            if self._should_stick_to_bottom():
                self.scroll_to_bottom()

    def scroll(self, dy: float) -> None:
        """Scroll by dy pixels (positive = down)."""
        if dy == 0:
            return
        self.scroll_y = max(0.0, min(self.max_scroll(), self.scroll_y + dy))
        
    def max_scroll(self) -> float:
        """Maximum scroll offset in pixels given current content and viewport."""
        return max(0.0, float(math.ceil(self._visual_content_height() - self.viewport_height)))

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
        viewport = self._viewport_rect()

        # Ensure we have layout for current width
        self._ensure_layout(viewport.width)

        # Clip and blit visible lines
        prev_clip = layer.get_clip()
        layer.set_clip(viewport)

        y = viewport.y - int(round(self.scroll_y))
        
        gap = th.line_spacing

        for e in self._entries_visible:
            # animation easing per entry
            u = 1.0 if e.duration <= 0 else _ease_out_cubic(e.t / e.duration)
            offset = int((1.0 - u) * e.offset_px)
            alpha = int(255 * u)

            for j, surf in enumerate(e.surfaces):
                h = surf.get_height()
                if y + h + offset >= viewport.y and y + offset <= viewport.bottom:
                    prev_alpha = surf.get_alpha()
                    surf.set_alpha(alpha)
                    layer.blit(surf, (viewport.x, y + offset))
                    surf.set_alpha(prev_alpha)

                y += h
                if j < len(e.surfaces) - 1:
                    y += gap  # add spacing ONLY between wrapped lines inside the same entr
            
            if e is not self._entries_visible[-1]:
                y += th.entry_gap
                

        layer.set_clip(prev_clip)
        
        self._draw_scrollbar(layer, viewport)

        # Opacity
        if self.opacity < 1.0:
            layer.set_alpha(int(255 * max(0.0, min(1.0, self.opacity))))

        # Present
        surface.blit(layer, self.rect.topleft)

    # -------------------------- Internals --------------------------

    def _should_stick_to_bottom(self) -> bool:
        """Stay glued to bottom if user hasn't scrolled far up."""
        px = self._reveal_params.stick_to_bottom_threshold_px
        return self.max_scroll() - self.scroll_y <= max(0, px)
    
    def _recalc_content_height(self) -> None:
        total = 0
        for idx, e in enumerate(self._entries_visible):
            total += e.height
            if idx < len(self._entries_visible) - 1:
                total += self.theme.entry_gap
        self._content_h = total
        # Clamp scroll if content shrank
        self.scroll_y = min(self.scroll_y, self.max_scroll())
        
    def _make_entry(self, text: str, animated: bool, wait_for_input: bool = False) -> _Entry:
        # Temporary layout using current wrap width; will be reubit on draw if width changes
        surfaces, height = self._layout_text(text, self._wrap_w if self._wrap_w > 0 else 1024)
        rp = self._reveal_params
        return _Entry(
            text=text,
            surfaces=surfaces,
            height=height,
            t=0.0,
            duration=(rp.intro_duration if animated else 0.0),
            offset_px=(rp.intro_offset_px if animated else 0),
            visible=False,
            wait_for_input=wait_for_input,
        )

    def _invalidate_layout(self, rebuild_font: bool = False) -> None:
        if rebuild_font:
            # rebuild font for new size / path
            self.font = pygame.font.Font(self.theme.font_path, self.theme.font_size)
        self._wrap_w = -1  # force rebuild at next draw

    def _ensure_layout(self, wrap_w: int) -> None:
        """(Re)build wrapped line surfaces if width or content changed."""
        if wrap_w <= 0:
            self._wrap_w = wrap_w
            for e in self._entries_visible:
                e.surfaces, e.height = [], 0
            self._content_h = 0
            return
        if wrap_w == self._wrap_w:
            return

        # Recreate font to reflect theme change
        self.font = pygame.font.Font(self.theme.font_path, self.theme.font_size)
        self._wrap_w = wrap_w

        for e in self._entries_visible:
            e.surfaces, e.height = self._layout_text(e.text, wrap_w)

        # pending entries don't affect height yet, but keep them prewrapped for quick release
        for e in self._entries_pending:
            e.surfaces, e.height = self._layout_text(e.text, wrap_w)

        self._recalc_content_height()
        
    def _layout_text(self, text: str, wrap_w: int) -> tuple[list[pygame.Surface], int]:
        lines = self._wrap_text(text or "", wrap_w)
        render = self.font.render
        color = self.theme.text_rgb
        surfaces = [render(line, True, color) for line in lines]
        gap = self.theme.line_spacing
        height = sum((s.get_height() for s in surfaces)) + (len(surfaces) - 1) * gap if surfaces else 0
        return surfaces, height

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
                    if cur: out.append(cur)
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

    def _draw_scrollbar(self, layer: pygame.Surface, viewport: pygame.Rect) -> None:
        sb = self.theme.scrollbar
        t, r, b, l = self.theme.padding
        track_x = self.rect.w - r - sb.margin - sb.width
        track_y = t
        track_h = self.rect.h - (t + b)
        if track_h <= 0 or sb.width <= 0: return

        overflow = self._visual_content_height() > viewport.h
        if not overflow and not sb.show_when_no_overflow:
            return

        track_rect = pygame.Rect(track_x, track_y, sb.width, track_h)
        pygame.draw.rect(layer, sb.track_color, track_rect, border_radius=sb.radius)

        if overflow:
            ratio = max(0.0, min(1.0, viewport.h / max(1, self._visual_content_height())))
            thumb_h = max(sb.min_thumb_size, int(track_h * ratio))
            max_sc = max(1e-6, self.max_scroll())
            # pos_ratio = 0.0 if self.max_scroll() <= 0 else self.scroll_y / self.max_scroll()
            pos_ratio = self.scroll_y / max_sc
            free = max(0, track_h - thumb_h)
            thumb_y = track_y + int(free * pos_ratio)
        else:
            thumb_h = track_h
            thumb_y = track_y

        thumb_rect = pygame.Rect(track_x, thumb_y, sb.width, thumb_h)
        pygame.draw.rect(layer, sb.thumb_color, thumb_rect, border_radius=sb.radius)
        
    def _anim_bottom_extra(self) -> int:
        if not self._entries_visible:
            return 0
        e = self._entries_visible[-1]
        if e.duration <= 0 or e.t >= e.duration:
            return 0
        # Remaining slide distance (how far below it starts)
        u = min(1.0, max(0.0, e.t / e.duration))
        return int((1.0 - u) * e.offset_px)
    
    def _visual_content_height(self) -> int:
        return self._content_h + self._anim_bottom_extra()

    def _near_bottom(self) -> bool:
        px = getattr(self._reveal_params, "stick_to_bottom_threshold_px", 24)
        return (self.max_scroll() - self.scroll_y) <= max(0, px)
    
    def _viewport_width(self) -> int:
        t, r, b, l = self.theme.padding
        sb = self.theme.scrollbar
        reserve_w = max(0, sb.width + sb.margin)
        return max(0, self.rect.w - (l + r + reserve_w))
    
    def _viewport_rect(self) -> pygame.Rect:
        t, r, b, l = self.theme.padding
        return pygame.Rect(l, t, self._viewport_width(), max(0, self.rect.h - (t + b)))