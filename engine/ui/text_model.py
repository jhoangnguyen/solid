from __future__ import annotations

from dataclasses import dataclass
from collections import deque
from typing import Deque, List, Optional

@dataclass
class RevealParams:
    per_line_delay: float = 0.15
    intro_duration: float = 0.18
    intro_offset_px: int = 10
    stick_to_bottom_threshold_px: int = 24  # used by the wrapper to keep view anchored

@dataclass(eq=False)
class Entry:
    text: str
    # animation state
    t: float = 0.0                 # elapsed animation time
    duration: float = 0.18         # total animation duration
    offset_px: int = 10            # slide-up distance
    # visibility & gating
    visible: bool = False
    wait_for_input: bool = False   # if True, only released on press

class TextModel:
    """
    Owns the dialogue queue and reveal timing.
    No rendering/layout here — the view handles that.
    """
    def __init__(self, reveal: Optional[RevealParams] = None):
        self.reveal = reveal or RevealParams()
        self._visible: List[Entry] = []
        self._pending: Deque[Entry] = deque()
        self._release_timer: float = 0.0

    # ---------- authoring ----------
    def clear(self) -> None:
        self._visible.clear()
        self._pending.clear()
        self._release_timer = 0.0

    def set_text(self, text: str) -> None:
        self.clear()
        e = self._make_entry(text, animated=False, wait=False)
        e.visible = True
        e.t = e.duration
        self._visible.append(e)

    def queue_lines(self, text_block: str, wait_for_input: bool = False) -> None:
        for line in (text_block or "").splitlines():
            self.append_line(line, animated=True, wait_for_input=wait_for_input)

    def append_line(self, line: str, animated: bool = True, wait_for_input: bool = False) -> None:
        e = self._make_entry(line, animated=animated, wait=wait_for_input)
        if animated or wait_for_input:
            self._pending.append(e)
        else:
            e.visible = True
            e.t = e.duration
            self._visible.append(e)

    # ---------- progression ----------
    def update(self, dt: float) -> dict:
        """
        Returns dict flags: {"released": bool, "animating": bool}
        """
        released = False
        # auto-release if next doesn't require input and the last visible is finished
        if self._pending:
            first = self._pending[0]
            if not first.wait_for_input:
                last_done = (not self._visible) or (self._visible[-1].t >= self._visible[-1].duration - 1e-4)
                if last_done:
                    self._release_timer += dt
                    if self._release_timer >= self.reveal.per_line_delay:
                        self._release_timer = 0.0
                        self._release_next()
                        released = True

        animating = False
        for e in self._visible:
            if e.t < e.duration:
                e.t = min(e.duration, e.t + dt)
                animating = True

        return {"released": released, "animating": animating}

    def on_player_press(self) -> bool:
        """
        Finish current fade if any, then release the next line (if any).
        Returns True if something changed visibly.
        """
        changed = False
        if self._visible:
            last = self._visible[-1]
            if last.t < last.duration:
                last.t = last.duration
                changed = True
        if self._pending:
            self._release_timer = 0.0
            self._release_next()
            changed = True
        return changed

    def advance_line_now(self) -> bool:
        if self._pending:
            self._release_timer = 0.0
            self._release_next()
            return True
        return False

    # ---------- queries ----------
    @property
    def visible_entries(self) -> List[Entry]:
        return self._visible

    @property
    def pending_count(self) -> int:
        return len(self._pending)

    def last_entry_anim_offset(self) -> int:
        """
        Remaining slide distance on last visible entry; used for "visual height".
        """
        if not self._visible:
            return 0
        e = self._visible[-1]
        if e.duration <= 0 or e.t >= e.duration:
            return 0
        u = max(0.0, min(1.0, e.t / e.duration))
        return int((1.0 - u) * e.offset_px)

    # ---------- internals ----------
    def _make_entry(self, text: str, animated: bool, wait: bool) -> Entry:
        rp = self.reveal
        return Entry(
            text=text,
            t=0.0,
            duration=(rp.intro_duration if animated else 0.0),
            offset_px=(rp.intro_offset_px if animated else 0),
            visible=False,
            wait_for_input=wait,
        )

    def _release_next(self) -> None:
        e = self._pending.popleft()
        e.visible = True
        self._visible.append(e)
