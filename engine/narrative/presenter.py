from __future__ import annotations
from typing import List, Optional
from engine.narrative.types import Node, Choice, Story
from engine.ui.widgets.text_box import TextBox
from engine.ui.background_manager import BackgroundManager

class NodePresenter:
    def __init__(self, textbox: TextBox, story: Story, bg_manager: BackgroundManager =None):
        self.tb = textbox
        self.story = story
        self._prepared: Optional[List[str]] | None = None
        self._shown: bool = False
        self._choices: list[Choice] | None = None
        self.bg = bg_manager
        
    def _resolve_bg(self, raw):
        """
        Return (spec, transition, duration)
        - raw may be None, string path/key, or dict
        - If string matches a registry key (story.backgrounds), resolve to dict
        - If dict may include optional 'transition' and 'duration'
        """
        if raw is None:
            return None, "crossfade", 0.35

        # registry lookup by key (optional)
        if isinstance(raw, str) and hasattr(self.story, "backgrounds"):
            reg = getattr(self.story, "backgrounds") or {}
            if raw in reg:
                raw = reg[raw]

        transition = "crossfade"
        duration = 0.35

        if isinstance(raw, dict):
            # copy so we don't mutate node.bg
            spec = dict(raw)
            transition = spec.pop("transition", transition)
            duration = float(spec.pop("duration", duration))
            return spec, transition, duration

        # string path (or already-resolved)
        return raw, transition, duration

    def show_node(self, node: Node) -> None:
        # Background first, so the fade starts alongside the new text
        # Window background (if provided)
        if self.bg and getattr(node, "bg", None) is not None:
            spec, trans, dur = self._resolve_bg(node.bg)
            if spec is not None:
                self.bg.set(spec, slot="window", transition=trans, duration=dur)

        # Textbox background: set if provided, else clear so we fall back to original drawing
        if self.bg:
            if getattr(node, "textbox_bg", None) is not None:
                spec, trans, dur = self._resolve_bg(node.textbox_bg)
                if spec is not None:
                    self.bg.set(spec, slot="textbox", transition=trans, duration=dur)
            else:
                self.bg.clear("textbox")

        self.tb.hide_choice_box()
        self.tb.clear()
        self.tb.set_follow_bottom(True)

        # say block (queued as line-by-line, waiting for input)
        self.tb.model.queue_lines(node.say, wait_for_input=True)

        # Prepare the choices block (rendered later as an overlay)
        if node.choices:
            # self._prepared = [""] + lines  # optional spacer line at top
            self._prepared = [f"> {(c.text or c.id)}{(' [WIP]' if c.goto is None else '')}" for c in node.choices]
            self._choices = list(node.choices)
            self._shown = False
        else:
            self._prepared = None
            self._choices = None
            self._shown = True

        self.tb.scroll_to_bottom()

    def update(self, dt: float) -> None:
        if self._shown or not self._prepared:
            return
        # show when the say block is fully revealed (no pending + last line finished)
        vis = self.tb.model.visible_entries
        last_done = (not vis) or (vis[-1].t >= vis[-1].duration - 1e-4)
        if self.tb.model.pending_count == 0 and last_done:
            self.tb.show_choice_box(self._prepared)
            self._shown = True

    def submit_choice_index(self, idx: int) -> None:
        if not self._shown or self._choices is None:
            return
        if idx < 0 or idx >= len(self._choices):
            return
        ch = self._choices[idx]
        if not ch.goto:
            return # WIP choice
        next_node = self.story.nodes.get(ch.goto)
        if next_node:
            self.show_node(next_node)