from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Dict, Iterable, Optional
import math

# Keep items immutable so they can be shared safely
@dataclass(frozen=True)
class Item:
    id: str
    name: str
    weight: float = 0.0
    value: int = 0
    stackable: bool = True
    max_stack: int = 99
    tags: frozenset[str] = frozenset()
    # Optional: future stat hooks (not applied automatically)
    # e.g., {"combat.melee_atk": 2, "noncombat.charisma": 1}
    modifiers: Dict[str, int] = field(default_factory=dict, compare=False)

    def __post_init__(self):
        if not self.stackable and self.max_stack != 1:
            # Non-stackable items always have stack size 1
            object.__setattr__(self, "max_stack", 1)


@dataclass
class _Stack:
    item: Item
    qty: int = 1

    @property
    def weight(self) -> float:
        return self.item.weight * self.qty

    def room_left(self) -> int:
        return (self.item.max_stack - self.qty) if self.item.stackable else 0

    def add_into(self, n: int) -> int:
        """Adds up to n items into this stack; returns leftover not added."""
        if not self.item.stackable:
            return n
        take = min(n, self.room_left())
        self.qty += take
        return n - take


@dataclass
class Inventory:
    max_slots: Optional[int] = 30       # set None for unlimited slots
    max_weight: Optional[float] = 80.0  # set None for unlimited weight
    stacks: List[_Stack] = field(default_factory=list)
    coins: int = 0

    # --- Introspection --------------------------------------------------------
    @property
    def used_slots(self) -> int:
        return len(self.stacks)

    @property
    def used_weight(self) -> float:
        return sum(s.weight for s in self.stacks)

    def count(self, item_id: str) -> int:
        return sum(s.qty for s in self.stacks if s.item.id == item_id)

    def items(self) -> Iterable[_Stack]:
        return iter(self.stacks)

    # --- Capacity checks ------------------------------------------------------
    def _predict_after_add(self, item: Item, qty: int) -> tuple[int, float, int]:
        """Return (new_slots, new_weight, new_stacks_needed) after adding qty."""
        # Fill existing stacks first
        remaining = qty
        for s in self.stacks:
            if s.item.id == item.id and item.stackable and remaining > 0:
                can_put = min(remaining, s.room_left())
                remaining -= can_put

        # How many *new* stacks do we need?
        if item.stackable:
            new_stacks_needed = math.ceil(remaining / item.max_stack) if remaining > 0 else 0
        else:
            new_stacks_needed = remaining  # each copy takes one stack

        new_slots = self.used_slots + new_stacks_needed
        new_weight = self.used_weight + (item.weight * qty)
        return new_slots, new_weight, new_stacks_needed

    def can_add(self, item: Item, qty: int = 1) -> bool:
        new_slots, new_weight, _ = self._predict_after_add(item, qty)
        if self.max_slots is not None and new_slots > self.max_slots:
            return False
        if self.max_weight is not None and new_weight > self.max_weight:
            return False
        return True

    # --- Mutations ------------------------------------------------------------
    def add(self, item: Item, qty: int = 1) -> int:
        """
        Try to add qty of item. Returns leftover that could NOT be added (0 if all fit).
        Fills existing stacks, then creates new stacks up to slot/weight limits.
        """
        if qty <= 0:
            return 0

        # First, fill existing stacks
        remaining = qty
        if item.stackable:
            for s in self.stacks:
                if s.item.id == item.id and remaining > 0:
                    remaining = s.add_into(remaining)

        # Then, create new stacks as allowed
        while remaining > 0:
            # Check capacity if we create one more stack (or one item if non-stackable)
            batch = min(remaining, item.max_stack if item.stackable else 1)
            new_slots, new_weight, _ = self._predict_after_add(item, batch)
            if (self.max_slots is not None and new_slots > self.max_slots) or \
               (self.max_weight is not None and new_weight > self.max_weight):
                break

            self.stacks.append(_Stack(item=item, qty=batch))
            remaining -= batch

        return remaining  # leftover that didn't fit

    def remove(self, item_id: str, qty: int = 1) -> int:
        """
        Remove up to qty of item_id. Returns how many were actually removed.
        Removes from partially filled stacks first.
        """
        if qty <= 0:
            return 0

        removed = 0
        # Prefer draining smaller stacks first to reduce fragmentation
        self.stacks.sort(key=lambda s: (s.item.id != item_id, s.qty))
        i = 0
        while i < len(self.stacks) and removed < qty:
            s = self.stacks[i]
            if s.item.id != item_id:
                i += 1
                continue
            take = min(s.qty, qty - removed)
            s.qty -= take
            removed += take
            if s.qty == 0:
                del self.stacks[i]
            else:
                i += 1
        return removed

    def has(self, item_id: str, qty: int = 1) -> bool:
        return self.count(item_id) >= qty
