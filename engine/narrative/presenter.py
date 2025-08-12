# # from __future__ import annotations
# # from engine.narrative.types import Node
# # from engine.ui.widgets.textbox import TextBox

# # def render_node_into_textbox(tb: TextBox, node: Node) -> None:
# #     """
# #     Dump `say` and then show choices with a leading '>'.
# #     All lines gate on click (wait_for_input=True) to match VN flow.
# #     """
# #     tb.clear()
# #     # Say block
# #     tb.queue_lines(node.say, wait_for_input=True)
    
# #     # Blank line before options if any
# #     if node.choices:
# #         tb.append_line("", animated=False)  # Spacer line
# #         # Present choices; routing WIP
# #         for ch in node.choices:
# #             label = ch.text or ch.id
# #             # Mark WIP choices that have no goto
# #             if ch.goto is None:
# #                 label += " [WIP]"
# #             tb.append_line(f"> {label}", animated=True, wait_for_input=True)
            
# #     tb.scroll_to_bottom()

# from __future__ import annotations
# from typing import List, Optional
# from engine.narrative.types import Node
# from engine.ui.widgets.text_box import TextBox

# class NodePresenter:
#     """
#     Presents one Node into a TextBox.
#     - Queues the node.say as wait-for-input lines (one per press).
#     - When the say block has fully revealed, appends ALL choices at once.
#     """
#     def __init__(self, textbox: TextBox):
#         self.tb = textbox
#         self._pending_choice_lines: Optional[List[str]] = None
#         self._choices_shown: bool = False

#     def show_node(self, node: Node) -> None:
#         self.tb.clear()
#         # queue the say block (click through)
#         self.tb.model.queue_lines(node.say, wait_for_input=True)

#         # prepare the choices block (spacer + one line per choice)
#         if node.choices:
#             lines = []
#             lines.append("")  # spacer line
#             for ch in node.choices:
#                 label = ch.text or ch.id
#                 if ch.goto is None:
#                     label += " [WIP]"
#                 lines.append(f"> {label}")
#             self._pending_choice_lines = lines
#             self._choices_shown = False
#         else:
#             self._pending_choice_lines = None
#             self._choices_shown = True

#         # start anchored at bottom
#         self.tb.scroll_to_bottom()

#     def update(self, dt: float) -> None:
#         """
#         Call this every frame (before or after tb.update). When the say block
#         finishes (no more pending lines and last visible is done), reveal the
#         entire choices block at once.
#         """
#         if not self._pending_choice_lines or self._choices_shown:
#             return

#         # Say block is done when the model has no pending entries AND the last
#         # visible entry (the last say line) has finished animating.
#         vis = self.tb.model.visible_entries
#         last_done = (not vis) or (vis[-1].t >= vis[-1].duration - 1e-4)
#         if self.tb.model.pending_count == 0 and last_done:
#             # Append all choices as *visible* entries (animated=True for a unified fade/slide)
#             self.tb.model.append_visible_lines(self._pending_choice_lines, animated=True)
#             self.tb.scroll_to_bottom()
#             self._choices_shown = True

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