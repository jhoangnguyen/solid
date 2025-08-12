from __future__ import annotations

from typing import Optional
import pygame

from engine.ui.style import Theme
from engine.ui.text_model import TextModel, RevealParams
from engine.ui.text_view import TextView
from engine.ui.scroll_bar import Scrollbar
from engine.ui.widgets.choice_box import ChoiceBox
from engine.ui.scroll_model import ScrollModel
from engine.ui.choice_controller import ChoiceController

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
        "scroller", 
        "model", 
        "view", 
        "choices",
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

        self.model = TextModel(reveal)
        self.view = TextView(theme)
        self.scroller = ScrollModel(content_h=0, viewport_h=self.viewport_height, offset=0.0)

        self.choices = ChoiceController()
        self._follow_bottom = True

    # ---------- authoring ----------
    def set_reveal_params(self, rp: RevealParams) -> None:
        """ Fetches RevealParams, used to determine the speed lines are released. """
        self.model.reveal = rp

    def set_text(self, text: str) -> None:
        """ Sets text directly into the box. No animations. """
        self.model.set_text(text)
        self.scroller.to_top()
        
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
            self.scroller.to_bottom()
            
    def clear(self) -> None:
        """ Clears all queued dialogue and resets scroll. """
        self.model.clear()
        self.scroller.to_top()

    # ---------- lifecycle ----------
    def on_resize(self, new_rect: pygame.Rect) -> None:
        """ Adjusts all visible ratios for drawn rects and viewports to match the current resolution."""
        was_bottom = self._near_bottom()
        old_max = max(1e-6, self.scroller.max())
        ratio = self.scroller.offset / old_max

        self.rect = new_rect.copy()
        # force relayout now so scroll math is correct immediately
        viewport = self.view.viewport_rect(self.rect)
        self.view.ensure_layout(viewport.width, self.model.visible_entries)

        self._sync_scroll_metrics()
        if was_bottom:
            self.scroller.to_bottom()
        else:
            self.scroller.offset = self.scroller.max() * ratio

    def set_theme(self, theme: Theme) -> None:
        """ Sets the theme of the textbox object. Also sets the theme of the text, if provided. """
        self.theme = theme
        self.view.set_theme(theme)

    def update(self, dt: float) -> None:
        """ Updates the current state of the text box based on delta line. Releases lines and autoscrolls. """
        flags = self.model.update(dt)
        self.view.update(dt)
        self._sync_scroll_metrics()
        # keep anchored during slides if close to bottom
        if (flags.get("released") or flags.get("animating")) and (self._follow_bottom or self._near_bottom()):
            self.scroller.to_bottom()
        # Tick overlay
        if self.choices.active():
            prev = self.choices.anim_t
            self.choices.tick(dt)
            if (self.choices.anchor_bottom or self._follow_bottom) and self.choices.anim_t > prev:
                self.scroller.to_bottom()

    def on_player_press(self) -> None:
        """ Function to scroll on player mouse click or pressing a key. """
        if self.model.on_player_press() and (self._follow_bottom or self._near_bottom()):
            self.scroller.to_bottom()

    def advance_line_now(self) -> None:
        """ Advances the line immediately and autoscroll. """
        if self.model.advance_line_now() and (self._follow_bottom or self._near_bottom()):
            self.scroller.to_bottom()
            
    def show_choice_box(self, lines: list[str]) -> None:
        """ Show a choices overlay (renders inside the textbox viewport). """
        was_bottom = self._near_bottom()
        self.choices.show(lines, anchor_bottom=was_bottom)
        if was_bottom: self.scroller.to_bottom()
        
    def hide_choice_box(self) -> None:
        """ Hide the choices overlay. """
        self.choices.hide()
    
    # ---------- presenter ------------
    def choice_active(self) -> bool:
        return self.choices.active()
    
    def choice_move_cursor(self, delta: int) -> None:
        self.choices.move(delta)
        
    def choice_get_selected_index(self) -> int:
        return self.choices.sel
    
    def _choice_y_flow(self, viewport: pygame.Rect) -> int:
        return (viewport.y - int(round(self.scroller.offset)) + self.view.content_height(self.model.visible_entries) + self.model.last_entry_anim_offset() + max(self.theme.entry_gap, self.theme.line_spacing))
    
    def choice_hover_at(self, window_pos: tuple[int, int]) -> None:
        if not self.choices.active():
            return

        vx, vy = window_pos
        wx = vx - self.rect.x
        wy = vy - self.rect.y
        viewport = self.view.viewport_rect(self.rect)

        # Base flow Y (same as draw)
        y_flow = self._choice_y_flow(viewport)
        
        # Slide offset used in ChoiceBox.draw_flow (8px -> 0px)
        u = 1.0 if self.choices.anim_dur <= 0 else min(1.0, self.choices.anim_t / self.choices.anim_dur)
        slide_offset = int((1.0 - u) * 8)
        y_effective = y_flow - slide_offset

        # Hover: row-wide is friendlier (strict_text_x=False)
        idx = ChoiceBox.hit_test(
            viewport=viewport,
            lines=self.choices.lines,
            theme=self.theme,
            y_top=y_effective,
            point_widget_coords=(wx, wy),
            strict_text_x=False,
        )
        # Apply hover -> also sets selection for underline
        self.choices.set_hover_index(idx)
    
    def choice_click(self, window_pos: tuple[int, int]) -> int | None:
        if not self.choices.active():
            return None

        vx, vy = window_pos
        wx = vx - self.rect.x
        wy = vy - self.rect.y
        viewport = self.view.viewport_rect(self.rect)

        y_flow = self._choice_y_flow(viewport)

        u = 1.0 if self.choices.anim_dur <= 0 else min(1.0, self.choices.anim_t / self.choices.anim_dur)
        slide_offset = int((1.0 - u) * 8)
        y_effective = y_flow - slide_offset

        # Click: require pointer over actual text
        idx = ChoiceBox.hit_test(
            viewport=viewport,
            lines=self.choices.lines,
            theme=self.theme,
            y_top=y_effective,
            point_widget_coords=(wx, wy),
            strict_text_x=True,
        )
        if idx is None:
            return None
        self.choices.set_hover_index(idx)  # sync selection to clicked row
        return idx

    # ---------- scrolling ----------
    def scroll(self, dy: float) -> None:
        """ Scrolls the textbox by a delta y amount. Blocks any negatives values. """
        if dy == 0: return
        prev_bottom = self.is_at_bottom
        self.scroller.scroll(dy)
        if not self.is_at_bottom and not prev_bottom:
            self._follow_bottom = False
        if self.is_at_bottom:
            self._follow_bottom = True # Optional

    def max_scroll(self) -> float:
        """ Scrolls the textbox to the bottom of the visible content. """
        self._sync_scroll_metrics()
        return self.scroller.max()

    def scroll_to_top(self) -> None:
        self.scroller.to_top()
        self._follow_bottom = False

    def scroll_to_bottom(self) -> None:
        self._sync_scroll_metrics()
        self.scroller.to_bottom()
        self._follow_bottom = True
        
    def _sync_scroll_metrics(self) -> None:
        """ Update ScrollModel content/viewport from current layout. """
        self.scroller.viewport_h = self.viewport_height
        self.scroller.content_h = int(self._visual_content_height())
        self.scroller.clamp()
                
    # ---------- properties ----------
    @property
    def viewport_height(self) -> int:
        t, r, b, l = self.theme.padding
        return max(0, self.rect.h - (t + b))

    @property
    def is_at_top(self) -> bool:
        return self.scroller.offset <= 1e-3

    @property
    def is_at_bottom(self) -> bool:
        return (self.scroller.max() - self.scroller.offset) <= 1e-3

    # ---------- drawing ----------
    def draw(self, surface: pygame.Surface) -> None:
        if self.rect.w <= 0 or self.rect.h <= 0:
            return

        layer = pygame.Surface(self.rect.size, pygame.SRCALPHA)

        entries = self.model.visible_entries
        viewport = self.view.viewport_rect(self.rect)

        # draw background + text
        self.view.draw_into(layer, self.rect, entries, self.scroller.offset)

        # draw scrollbar
        Scrollbar.draw(
            layer,
            self.rect,
            viewport,
            self._visual_content_height(),
            self.scroller.offset,
            self.scroller.max(),
            self.theme,
        )
        
        # if self._choice_lines:
        if self.choices.active():
            viewport = self.view.viewport_rect(self.rect)
            y_flow = viewport.y - int(round(self.scroller.offset)) + self.view.content_height(entries) + self.model.last_entry_anim_offset() + self._choice_gap_above()
            ChoiceBox.draw_flow(
                layer=layer,
                viewport=viewport,
                lines=self.choices.lines,
                theme=self.theme,
                y_top=y_flow,
                anim_t=self.choices.anim_t,
                anim_duration=self.choices.anim_dur,
                selected_idx=self.choices.sel
            )

        # widget opacity
        if self.opacity < 1.0:
            layer.set_alpha(int(255 * max(0.0, min(1.0, self.opacity))))

        surface.blit(layer, self.rect.topleft)

    # ---------- helpers ----------
    def _near_bottom(self) -> bool:
        px = getattr(self.model.reveal, "stick_to_bottom_threshold_px", 24)
        self._sync_scroll_metrics()
        return (self.max_scroll() - self.scroller.offset) <= max(0, px)

    def _visual_content_height(self) -> int:
        # content height from view + any remaining animation offset on last line
        h = self.view.content_height(self.model.visible_entries) + self.model.last_entry_anim_offset()
        if self.choices.active():
            viewport = self.view.viewport_rect(self.rect)
            h += self._choice_gap_above() + ChoiceBox.calc_height(viewport, self.choices.lines, self.theme)
        return h
    
    def _choice_gap_above(self) -> int:
        # space between last text line and the panel
        return max(self.theme.entry_gap, self.theme.line_spacing)
