from __future__ import annotations
from typing import Optional, Tuple, Protocol

# Minimal protocols, no pygame import here
class _HasHitTest(Protocol):
    def hit_test(self, pos: Tuple[int, int]) -> bool: ...

class _HasRect(Protocol):
    # typed as "any" to avoid importing pygame.Rect
    rect: object

class InputRouter:
    """
    Central gatekeeper for 'should a click progress dialogue?'

    Rules:
      - If click is on BottomBar / TopIcons / any Window -> do NOT progress.
      - If click is inside the TextBox -> progress.
      - Otherwise (empty space) -> progress.
    """
    def __init__(
        self,
        *,
        windows: Optional[_HasHitTest] = None,
        textbox: Optional[_HasRect] = None,
        top_icons: Optional[_HasHitTest] = None,
        bottom_bar: Optional[_HasHitTest] = None,
    ) -> None:
        self.windows = windows
        self.textbox = textbox
        self.top_icons = top_icons
        self.bottom_bar = bottom_bar

    # --- public API ---------------------------------------------------------
    def click_progress_allowed(self, pos: Tuple[int, int]) -> bool:
        """
        Return True if a left-click at `pos` should advance dialogue,
        according to the UI hit rules above.
        """
        if self._ui_blocker_hit(pos):
            return False

        # Click inside the textbox always allowed to progress.
        if self._rect_hit(self.textbox, pos):
            return True

        # If it's not on any UI element, it's "empty space" -> allow.
        return True

    # --- helpers ------------------------------------------------------------
    def _ui_blocker_hit(self, pos: Tuple[int, int]) -> bool:
        if self._hit(self.bottom_bar, pos):
            return True
        if self._hit(self.top_icons, pos):
            return True
        if self._hit(self.windows, pos):  # clicking *any* window never progresses
            return True
        return False

    @staticmethod
    def _hit(obj: Optional[_HasHitTest], pos: Tuple[int, int]) -> bool:
        return bool(obj and getattr(obj, "hit_test", None) and obj.hit_test(pos))

    @staticmethod
    def _rect_hit(obj: Optional[_HasRect], pos: Tuple[int, int]) -> bool:
        # Works with any object that has a pygame.Rect-like "rect"
        if not obj or not hasattr(obj, "rect"):
            return False
        rect = getattr(obj, "rect")
        # Defer attribute check to avoid importing pygame here
        return bool(getattr(rect, "collidepoint", None) and rect.collidepoint(pos))
