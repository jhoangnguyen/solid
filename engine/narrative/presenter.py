from __future__ import annotations
from typing import List, Optional
from collections import deque
from engine.narrative.types import Node, Choice, Story
from engine.ui.widgets.text_box import TextBox
from engine.ui.background_manager import BackgroundManager

class NodePresenter:
    def __init__(self, 
                 textbox: TextBox, 
                 story: Story, 
                 bg_manager: BackgroundManager = None,
                 clear_after_nodes: Optional[int] = None,   # None = never auto-clear, 0 = clear every node
                 insert_node_separator: bool = True,        # Add a blank line between nodes if not clearing
                 separator_text: str = ""):                 # Customize the separator if desired
        self.tb = textbox
        self.story = story
        self._prepared: Optional[List[str]] | None = None
        self._shown: bool = False
        self._choices: list[Choice] | None = None
        self.bg = bg_manager
        
        # None  -> never auto-clear
        # 0     -> always clear
        # N > 0   -> clear when we exceed N nodes since last clear
        self._clear_after_nodes = None if clear_after_nodes is None else int(clear_after_nodes)
        self._nodes_since_clear = 0
        self._insert_nodes_separator = bool(insert_node_separator)
        self._separator_text = separator_text
        self._node_sizes = deque()
        
    def _insert_separator_if_needed(self) -> Node:
        """ Insert a separator that visually belongs to the PREVIOUS node. """
        if self._insert_nodes_separator and self._node_sizes and self.tb.model.visible_entries:
            self.tb.append_visible_lines([self._separator_text], animated=False)
            # Count the separator with the previous node so it trims away together
            self._node_sizes[-1] += 1

    def _enforce_node_limit(self) -> None:
        """ Trim whole nodes from the top until we're within the node limit. """
        limit = self._clear_after_nodes
        if limit is None:
            return # Never auto-trim
        if limit == 0:
            # Keep only the current node. Drop everything before we start adding it.
            total_before = sum(self._node_sizes)
            if total_before:
                self.tb.trim_oldest_entries(total_before)
                self._node_sizes.clear()
            return
        # Limit > 0: keep at most 'limit' nodes; trim the oldest if we exceed
        while len(self._node_sizes) > limit:
            oldest_count = self._node_sizes.popleft()
            if oldest_count > 0:
                self.tb.trim_oldest_entries(oldest_count)
        
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
        
        # Sliding-window management
        # 0 => keep only current node: clear all prior content now
        if self._clear_after_nodes == 0:
            total_before = sum(self._node_sizes)
            if total_before:
                self.tb.clear()
                self._node_sizes.clear()
        else:
            # Add a separator that will be counted with the PREVIOUS node
            self._insert_separator_if_needed()

        self.tb.set_follow_bottom(True)

        # queue SAY lines for this node
        say_text = node.say or ""
        line_count = len(say_text.splitlines())
        self.tb.model.queue_lines(say_text, wait_for_input=True)

        # record size for this node and enforce limit
        self._node_sizes.append(line_count)
        self._enforce_node_limit()

        # choices (unchanged) ...
        if node.choices:
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
        # Insert the player's selected choice into the transcript
        # Prefix from theme (fallback "You: ")
        pc = getattr(self.tb.theme, "player_choice", None)
        prefix = "You: "
        if isinstance(pc, dict):
            prefix = str(pc.get("prefix", prefix))
        elif pc is not None and hasattr(pc, "prefix"):
            prefix = str(pc.prefix)
        chosen_text = f"{prefix}{(ch.text or ch.id)}"
        self.tb.model.append_player_choice(chosen_text, animated=False)
        # Count this with the current node so it trims together
        if hasattr(self, "_node_sizes") and self._node_sizes:
            self._node_sizes[-1] += 1
        self.tb.scroll_to_bottom()
            
        next_node = self.story.nodes.get(ch.goto)
        if next_node:
            self.show_node(next_node)