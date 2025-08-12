from __future__ import annotations
from typing import List, Optional
from engine.narrative.types import Node, Choice, Story
from engine.ui.widgets.text_box import TextBox

class NodePresenter:
    def __init__(self, textbox: TextBox, story: Story):
        self.tb = textbox
        self.story = story
        self._prepared: Optional[List[str]] | None = None
        self._shown: bool = False
        self._choices: list[Choice] | None = None

    def show_node(self, node: Node) -> None:
        self.tb.hide_choice_box()
        self.tb.clear()
        self.tb.set_follow_bottom(True)
        # Queue the say block (one per press)
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