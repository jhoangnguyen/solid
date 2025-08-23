# game/rules/stats.py
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict
from .inventory import Inventory


# --- Non-combat breakdown -----------------------------------------------------

@dataclass
class NonCombat:
    # Core section point buckets (optional, useful for ratios/allocations)
    strength: int = 0
    dexterity: int = 0
    magic: int = 0
    spirit: int = 0

    # Strength (Deliverance)
    force: int = 0
    presence: int = 0
    resistance: int = 0

    # Dexterity (Lithe)
    stealth: int = 0
    nimble: int = 0
    reaction: int = 0

    # Magic (Conscious)
    memory: int = 0
    logic: int = 0
    calm: int = 0

    # Spirit (Wisdom)
    charisma: int = 0
    lure: int = 0
    sense: int = 0

    def section_totals(self) -> Dict[str, int]:
        """Convenience: totals per core section based on their sub-skills."""
        return {
            "strength": self.force + self.presence + self.resistance,
            "dexterity": self.stealth + self.nimble + self.reaction,
            "magic": self.memory + self.logic + self.calm,
            "spirit": self.charisma + self.lure + self.sense,
        }

    def total_points(self) -> int:
        """Sum of all non-combat sub-skills (not the core buckets)."""
        return sum(self.section_totals().values())


# --- Combat breakdown ---------------------------------------------------------

@dataclass
class Combat:
    # Core section point buckets (optional, useful for ratios/allocations)
    strength: int = 0   # (Destruction)
    dexterity: int = 0  # (Lethality)
    magic: int = 0      # (Command)
    spirit: int = 0     # (Wish)

    # Strength (Destruction)
    melee_atk: int = 0         # chance + phys scaling
    block: int = 0             # flat block threshold
    hp_scaling: int = 0        # contributes to Fortitude/HP

    # Dexterity (Lethality)
    ranged_atk: int = 0        # chance + ranged phys scaling
    dodge: int = 0             # flat dodge threshold
    crit_damage: int = 0       # % per point (base 150%)

    # Magic (Command)
    magic_atk_arcane: int = 0  # chance + arcane dmg scaling
    magic_resist: int = 0      # flat arcane resistance threshold
    mana_scaling: int = 0      # contributes to MP

    # Spirit (Wish)
    magic_atk_spirit: int = 0  # chance + spirit dmg scaling
    debuff_resist: int = 0     # flat spirit/aura/debuff resist
    crit_rate: int = 0         # % per point (base 5%)

    def section_totals(self) -> Dict[str, int]:
        """Convenience: totals per core section based on their sub-skills."""
        return {
            "strength": self.melee_atk + self.block + self.hp_scaling,
            "dexterity": self.ranged_atk + self.dodge + self.crit_damage,
            "magic": self.magic_atk_arcane + self.magic_resist + self.mana_scaling,
            "spirit": self.magic_atk_spirit + self.debuff_resist + self.crit_rate,
        }

    def total_points(self) -> int:
        """Sum of all combat sub-skills (not the core buckets)."""
        return sum(self.section_totals().values())


# --- Character sheet ----------------------------------------------------------

@dataclass
class CharacterSheet:
    name: str = "Unnamed"
    level: int = 1

    # Time/turn economy + RNG knobs (kept simple for now)
    speed: float = 1.0           # actions per 1 unit of time (can be fractional)
    dice_sides: int = 6          # e.g., 2, 4, 6, 8, 10, 12, 20...
    dice_count: int = 1          # keep explicit (dice-per-level rule is TBD)

    # Sections
    noncombat: NonCombat = field(default_factory=NonCombat)
    combat: Combat = field(default_factory=Combat)
    
    inventory: Inventory = field(default_factory=Inventory)

    # --- Derived helpers (pure math; no side effects) ------------------------

    @property
    def total_allocated_points(self) -> Dict[str, int]:
        """
        High-level view of allocated points per sheet section.
        Only sums sub-skills (core buckets are advisory for ratios).
        """
        return {
            "noncombat": self.noncombat.total_points(),
            "combat": self.combat.total_points(),
        }

    def fortitude_hp(self) -> int:
        """
        Fortitude / HP:
            HP = level × (10 + hp_scaling)
        """
        return int(self.level * (10 + self.combat.hp_scaling))

    def max_mp(self) -> int:
        """
        Resolve/Sanity/Hope baseline pool (aggregate):
            MP = level × (10 + mana_scaling)
        (Splitting into three pools can be layered later.)
        """
        return int(self.level * (10 + self.combat.mana_scaling))

    def starting_point_budget(self) -> int:
        """
        Baseline point budget rule of thumb:
            level 1 starts at ~30; +10 per level up.
        (Callers can ignore if they track budgets elsewhere.)
        """
        return 30 + max(0, self.level - 1) * 10
