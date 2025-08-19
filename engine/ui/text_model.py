from __future__ import annotations

from dataclasses import dataclass
from collections import deque
from typing import Deque, List, Tuple, Optional

@dataclass
class RevealParams:
    per_line_delay: float = 0.15
    intro_duration: float = 0.18
    intro_offset_px: int = 10
    stick_to_bottom_threshold_px: int = 24  # used by the wrapper to keep view anchored
    
    # Typewriter timing
    chars_per_sec: float = 45.0
    pause_short_s: float = 0.06             # Comma, semicolon, colon
    pause_long_s: float = 0.25              # Period, question, exclamation, new line
    pause_ellipsis_s: float = 0.35          # Special case for "..."
    
@dataclass(eq=False)
class Entry:
    text: str
    # animation state
    t: float = 0.0                              # elapsed animation time
    duration: float = 0.18                      # total animation duration
    offset_px: int = 10                         # slide-up distance
    # visibility & gating
    visible: bool = False
    wait_for_input: bool = False                # if True, only released on press
    cm_reveal: Optional[List[float]] = None     # Cumulative reveal fraction of total duration when the i-th visible char becomes visible
    
    is_player_choice: bool = False

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
            
    def append_visible_lines(self, lines: List[str], animated: bool = True) -> None:
        """
        Append lines that are visiblie immediately (not queued). If animated=True,
        the fade/slide animation will play
        """
        for line in lines or []:
            e = self._make_entry(line, animated=animated, wait=False)
            e.visible = True
            e.t = 0.0
            self._visible.append(e)
            
    def append_player_choice(self, line: str, animated: bool = False) -> None:
        """
        Append a single line immediately, tagged as as player-selected choice.
        """
        e = self._make_entry(line, animated=animated, wait=False)
        e.visible = True
        e.is_player_choice = True
        e.t = 0.0
        self._visible.append(e)
            
    def trim_oldest_entries(self, n: int) -> int:
        """
        Remove the first N visible entries. Returns how many were removed.
        """
        if n <= 0 or not self._visible:
            return 0
        n = min(n, len(self._visible))
        del self._visible[:n]
        return n

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
        # 1) Finish the current line if it's still animating
        if self._visible:
            last = self._visible[-1]
            if last.t < last.duration:
                last.t = last.duration
                return True  # consume this click just to complete the line

        # 2) No animation to finish -> advance to the next line
        if self._pending:
            self._release_timer = 0.0
            self._release_next()
            return True

        return False

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
        is_typewriter = animated and (rp.intro_offset_px == 0)
        if is_typewriter:
            dur, cm = self._compute_typewriter_timing(text, rp)
            return Entry(
                text=text,
                t=0.0,
                duration=dur,
                offset_px=0,                # Marks typewriter to the view
                visible=False,
                wait_for_input=wait,
                cm_reveal=cm,
            )
        else:
            return Entry(
                text=text,
                t=0.0,
                duration=(rp.intro_duration if animated else 0.0),
                offset_px=(rp.intro_offset_px if animated else 0),
                visible=False,
                wait_for_input=wait,
            )
            
        
    def _compute_typewriter_timing(self, text: str, rp: RevealParams) -> Tuple[float, List[float]]:
        """
        Returns (total_duration_seconds, cumulative_reveal_fracs) for typewriter:
        - Punctuation shows immediately, then we pause BEFORE the next visible char.
        - '\n' adds a long pause but is not a visible character.
        - Ellipsis '...' pauses after the first dot only.
        """
        cps = max(1e-6, float(rp.chars_per_sec))
        base = 1.0 / cps
        chars = list(text or "")
        n = len(chars)

        times: List[float] = []   # per-visible-char time
        carry = 0.0               # pause to apply before the NEXT visible char
        i = 0
        while i < n:
            c = chars[i]

            # newline -> just accumulate a long pause before the next visible char
            if c == "\n":
                carry += rp.pause_long_s
                i += 1
                continue

            # This character appears now; include any pending pause from previous punctuation
            t_char = base + carry
            carry = 0.0

            # Ellipsis: first dot shows now, then pause before the second dot only
            if c == "." and i + 2 < n and chars[i+1] == "." and chars[i+2] == ".":
                # First dot (with any previous carry)
                times.append(t_char)
                # Pause BEFORE second dot
                carry = rp.pause_ellipsis_s
                i += 1
                # Second dot (includes the carry), then no extra pause after it
                times.append(base + carry)
                i += 1
                # Third dot (plain base)
                times.append(base + carry)
                i += 1
                continue

            # Regular punctuation: pause AFTER this char (i.e., before the next one)
            if c in ",;:":
                times.append(t_char)
                carry = rp.pause_short_s
            elif c in ".!?":
                times.append(t_char)
                carry = rp.pause_long_s
            else:
                times.append(t_char)

            i += 1

        # If there’s a pending pause (e.g., line ends with punctuation), add it as a trailing delay
        trailing = carry
        total = sum(times) + trailing
        if total <= 0:
            return (0.0, [0.0])

        # Build cumulative reveal fractions (len = N_visible_chars + 1)
        cm: List[float] = [0.0]
        acc = 0.0
        for t in times:
            acc += t
            cm.append(acc / total)
        return (total, cm)


    def _release_next(self) -> None:
        e = self._pending.popleft()
        e.visible = True
        self._visible.append(e)
