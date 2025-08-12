from __future__ import annotations

from typing import Optional
import pygame
import math

from engine.ui.style import Theme
from engine.ui.text_model import TextModel, RevealParams
from engine.ui.text_view import TextView
from engine.ui.scroll_bar import Scrollbar
from engine.ui.widgets.choice_box import ChoiceBox

class TextBox:
    """
    Thin wrapper that wires:
      - TextModel (queue & reveal)
      - TextView  (layout & draw)
      - Scrollbar (draw)

    Also includes a Public API to match the current widget.
    """
    __slots__ = (
        "rect", 
        "theme", 
        "opacity", 
        "scroll_y", 
        "model", 
        "view", 
        "_choice_lines", 
        "_choice_anim_t", 
        "_choice_anim_dur",
        "_choice_anchor_bottom",
        "_choice_selected_idx",
        "_choice_hover_idx",
        "_follow_bottom",
        )

    def __init__(self, rect: pygame.Rect, theme: Theme, reveal: Optional[RevealParams] = None):
        """ 
        Creates a textbox instance.
            - Rect - Any rect passed in will become a textbox
            - Theme - Preconfigurable theme that sets font and dialogue typings
            - Opacity - Transparency of the textbox
            - Scroll_y - Setting for the current scroll value of the text box. 0.0 is the top of the box.
            - Model - Text model object that serves as an event handler for all text in the box.
            - View - Text view object that handles visibility (theme, wrapping) for the text in the box.
            
        """
        self.rect = rect.copy()
        self.theme = theme
        self.opacity: float = 1.0
        self.scroll_y: float = 0.0

        self.model = TextModel(reveal)
        self.view = TextView(theme)
        
        self._choice_lines = None
        self._choice_anim_t = 0.0
        self._choice_anim_dur = 0.18
        self._choice_anchor_bottom = False
        self._choice_selected_idx = -1
        self._choice_hover_idx = -1
        self._follow_bottom = True

    # ---------- authoring ----------
    def set_reveal_params(self, rp: RevealParams) -> None:
        """ Fetches RevealParams, used to determine the speed lines are released. """
        self.model.reveal = rp

    def set_text(self, text: str) -> None:
        """ Sets text directly into the box. No animations. """
        self.model.set_text(text)
        self.scroll_to_top()
        
    def set_follow_bottom(self, on: bool) -> None:
        self._follow_bottom = bool(on)

    def queue_lines(self, text_block: str, wait_for_input: bool = False) -> None:
        """ Adds lines of dialogue to the stack. Handles multi-line strings with \n. """
        self.model.queue_lines(text_block, wait_for_input)

    def append_line(self, line: str, animated: bool = True, wait_for_input: bool = False) -> None:
        """ Adds a single line of dialogue to the stack. """
        self.model.append_line(line, animated, wait_for_input)
        # if adding immediately-visible content, keep anchored when near bottom
        if not (animated or wait_for_input) and self._near_bottom():
            self.scroll_to_bottom()
            
    def clear(self) -> None:
        """ Clears all queued dialogue and resets scroll. """
        self.model.clear()
        self.scroll_y = 0.0

    # ---------- lifecycle ----------
    def on_resize(self, new_rect: pygame.Rect) -> None:
        """ Adjusts all visible ratios for drawn rects and viewports to match the current resolution."""
        was_bottom = self._near_bottom()
        old_max = max(1e-6, self.max_scroll())
        ratio = self.scroll_y / old_max

        self.rect = new_rect.copy()
        # force relayout now so scroll math is correct immediately
        viewport = self.view.viewport_rect(self.rect)
        self.view.ensure_layout(viewport.width, self.model.visible_entries)

        if was_bottom:
            self.scroll_to_bottom()
        else:
            self.scroll_y = self.max_scroll() * ratio

    def set_theme(self, theme: Theme) -> None:
        """ Sets the theme of the textbox object. Also sets the theme of the text, if provided. """
        self.theme = theme
        self.view.set_theme(theme)

    def update(self, dt: float) -> None:
        """ Updates the current state of the text box based on delta line. Releases lines and autoscrolls. """
        flags = self.model.update(dt)
        self.view.update(dt)
        # keep anchored during slides if close to bottom
        if (flags.get("released") or flags.get("animating")) and (self._follow_bottom or self._near_bottom()):
            self.scroll_to_bottom()
        # Tick overlay
        if self._choice_lines is not None and self._choice_anim_t < self._choice_anim_dur:
            self._choice_anim_t = min(self._choice_anim_dur, self._choice_anim_t + dt)
            # if we were at bottom when the panel appeared, keep anchoring during its growth
            if self._choice_anchor_bottom or self._follow_bottom:
                self.scroll_to_bottom()
        elif self._choice_lines is not None:
            self._choice_anchor_bottom = False

    def on_player_press(self) -> None:
        """ Function to scroll on player mouse click or pressing a key. """
        if self.model.on_player_press() and (self._follow_bottom or self._near_bottom()):
            self.scroll_to_bottom()

    def advance_line_now(self) -> None:
        """ Advances the line immediately and autoscroll. """
        if self.model.advance_line_now() and (self._follow_bottom or self._near_bottom()):
            self.scroll_to_bottom()
            
    def show_choice_box(self, lines: list[str]) -> None:
        """ Show a choices overlay (renders inside the textbox viewport). """
        was_bottom = self._near_bottom()
        
        self._choice_lines = list(lines or [])
        self._choice_anim_t = 0.0
        self._choice_anchor_bottom = was_bottom
        self._choice_selected_idx = 0 if self._choice_lines else -1 # Keyboard-ready
        self._choice_hover_idx = -1
        
        if was_bottom:
            self.scroll_to_bottom()
        
    def hide_choice_box(self) -> None:
        """ Hide the choices overlay. """
        self._choice_lines = None
        self._choice_anim_t = 0.0
        self._choice_anchor_bottom = False
        self._choice_selected_idx = -1
        self._choice_hover_idx = -1
    
    # ---------- presenter ------------
    def choice_active(self) -> bool:
        return bool(self._choice_lines)
    
    def choice_move_cursor(self, delta: int) -> None:
        if not self._choice_lines:
            return
        n = len(self._choice_lines)
        self._choice_selected_idx = (self._choice_selected_idx + delta) % n
        
    def choice_get_selected_index(self) -> int:
        return self._choice_selected_idx
    
    def _choice_y_flow(self, viewport: pygame.Rect) -> int:
        return (viewport.y - int(round(self.scroll_y)) + self.view.content_height(self.model.visible_entries) + self.model.last_entry_anim_offset() + max(self.theme.entry_gap, self.theme.line_spacing))
    
    def choice_hover_at(self, window_pos: tuple[int, int]) -> None:
        if not self._choice_lines:
            return
        vx, vy = window_pos
        # Convert to widget-layer coords
        wx = vx - self.rect.x
        wy = vy - self.rect.y
        viewport = self.view.viewport_rect(self.rect)
        y_flow = self._choice_y_flow(viewport)
        idx = ChoiceBox.hit_test(viewport, self._choice_lines, self.theme, y_flow, (wx, wy))
        self._choice_hover_idx = (-1 if idx is None else idx)
        if idx is not None:
            self._choice_selected_idx = idx # Hover also selects for underline
            
    def choice_click(self, window_pos: tuple[int, int]) -> int | None:
        self.choice_hover_at(window_pos)
        return self._choice_selected_idx if self._choice_selected_idx >= 0 else None

    # ---------- scrolling ----------
    def scroll(self, dy: float) -> None:
        """ Scrolls the textbox by a delta y amount. Blocks any negatives values. """
        if dy == 0:
            return
        prev_bottom = self.is_at_bottom
        self.scroll_y = max(0.0, min(self.max_scroll(), self.scroll_y + dy))
        if not self.is_at_bottom and not prev_bottom:
            self._follow_bottom = False

    def max_scroll(self) -> float:
        """ Scrolls the textbox to the bottom of the visible content. """
        return max(0.0, float(math.ceil(self._visual_content_height() - self.viewport_height)))

    def scroll_to_top(self) -> None:
        self.scroll_y = 0.0

    def scroll_to_bottom(self) -> None:
        self.scroll_y = self.max_scroll()
        self._follow_bottom = True

    # ---------- properties ----------
    @property
    def viewport_height(self) -> int:
        t, r, b, l = self.theme.padding
        return max(0, self.rect.h - (t + b))

    @property
    def is_at_top(self) -> bool:
        return self.scroll_y <= 1e-3

    @property
    def is_at_bottom(self) -> bool:
        return self.scroll_y >= self.max_scroll() - 1e-3

    # ---------- drawing ----------
    def draw(self, surface: pygame.Surface) -> None:
        if self.rect.w <= 0 or self.rect.h <= 0:
            return

        layer = pygame.Surface(self.rect.size, pygame.SRCALPHA)

        entries = self.model.visible_entries
        viewport = self.view.viewport_rect(self.rect)

        # draw background + text
        self.view.draw_into(layer, self.rect, entries, self.scroll_y)

        # draw scrollbar
        Scrollbar.draw(
            layer,
            self.rect,
            viewport,
            self._visual_content_height(),
            self.scroll_y,
            self.max_scroll(),
            self.theme,
        )
        
        if self._choice_lines:
            viewport = self.view.viewport_rect(self.rect)
            y_flow = viewport.y - int(round(self.scroll_y)) + self.view.content_height(entries) + self.model.last_entry_anim_offset() + self._choice_gap_above()
            ChoiceBox.draw_flow(
                layer=layer,
                viewport=viewport,
                lines=self._choice_lines,
                theme=self.theme,
                y_top=y_flow,
                anim_t=self._choice_anim_t,
                anim_duration=self._choice_anim_dur,
                selected_idx=self._choice_selected_idx
            )

        # widget opacity
        if self.opacity < 1.0:
            layer.set_alpha(int(255 * max(0.0, min(1.0, self.opacity))))

        surface.blit(layer, self.rect.topleft)

    # ---------- helpers ----------
    def _near_bottom(self) -> bool:
        px = getattr(self.model.reveal, "stick_to_bottom_threshold_px", 24)
        return (self.max_scroll() - self.scroll_y) <= max(0, px)

    def _visual_content_height(self) -> int:
        # content height from view + any remaining animation offset on last line
        # return self.view.content_height(self.model.visible_entries) + self.model.last_entry_anim_offset()
        h = self.view.content_height(self.model.visible_entries) + self.model.last_entry_anim_offset()
        if self._choice_lines:
            viewport = self.view.viewport_rect(self.rect)
            # y_flow = self._choice_y_flow(viewport)
            # ChoiceBox.draw_flow(layer, viewport, self._choice_lines, self.theme, y_flow, self._choice_anim_t, self._choice_anim_dur, selected_idx=self._choice_selected_idx)
            h += self._choice_gap_above() + ChoiceBox.calc_height(viewport, self._choice_lines, self.theme)
        return h
    
    def _choice_gap_above(self) -> int:
        # space between last text line and the panel
        return max(self.theme.entry_gap, self.theme.line_spacing)
