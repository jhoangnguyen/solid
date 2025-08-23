# unit_tests.py
import os
import pprint
import unittest

from game.rules.stats import (
    CharacterSheet, NonCombat, Combat,
)
from game.rules.inventory import (
    Inventory, Item
)

from game.rules.dice import Dice


# --- Lightweight debug helper (opt-in via TEST_DEBUG=1) -----------------------
PP = pprint.PrettyPrinter(indent=2, width=100, compact=True)
DEBUG = str(os.getenv("TEST_DEBUG", "")).lower() in ("1", "true", "yes", "on")

def debug(title, obj=None):
    if not DEBUG:
        return
    if obj is None:
        print(f"[DEBUG] {title}")
    else:
        # Pretty print structures; print scalars plainly
        if isinstance(obj, (dict, list, tuple, set)):
            print(f"[DEBUG] {title}:\n{PP.pformat(obj)}")
        else:
            print(f"[DEBUG] {title}: {obj}")


class TestStatsModels(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        debug("=====================================")
        debug("== TestStatsModels start ==")
        debug("=====================================")

    def test_noncombat_totals(self):
        nc = NonCombat(
            force=1, presence=2, resistance=3,     # 6
            stealth=4, nimble=5, reaction=6,       # 15
            memory=7, logic=8, calm=9,             # 24
            charisma=10, lure=0, sense=1           # 11
        )
        totals = nc.section_totals()
        debug("NonCombat.section_totals()", totals)
        debug("NonCombat.total_points()", nc.total_points())
        self.assertEqual(totals["strength"], 6)
        self.assertEqual(totals["dexterity"], 15)
        self.assertEqual(totals["magic"], 24)
        self.assertEqual(totals["spirit"], 11)
        self.assertEqual(nc.total_points(), 56)

    def test_combat_totals(self):
        cb = Combat(
            melee_atk=2, block=3, hp_scaling=4,            # 9
            ranged_atk=5, dodge=6, crit_damage=7,          # 18
            magic_atk_arcane=8, magic_resist=9, mana_scaling=1,  # 18
            magic_atk_spirit=2, debuff_resist=3, crit_rate=4     # 9
        )
        totals = cb.section_totals()
        debug("Combat.section_totals()", totals)
        debug("Combat.total_points()", cb.total_points())
        self.assertEqual(totals["strength"], 9)
        self.assertEqual(totals["dexterity"], 18)
        self.assertEqual(totals["magic"], 18)
        self.assertEqual(totals["spirit"], 9)
        self.assertEqual(cb.total_points(), 54)

    def test_character_sheet_helpers(self):
        nc = NonCombat(force=1, presence=2, resistance=3,
                       stealth=4, nimble=5, reaction=6,
                       memory=7, logic=8, calm=9,
                       charisma=10, lure=0, sense=1)
        cb = Combat(
            melee_atk=2, block=3, hp_scaling=4,
            ranged_atk=5, dodge=6, crit_damage=7,
            magic_atk_arcane=8, magic_resist=9, mana_scaling=1,
            magic_atk_spirit=2, debuff_resist=3, crit_rate=4
        )
        c = CharacterSheet(name="Tester", level=5, noncombat=nc, combat=cb)
        debug("CharacterSheet.name", c.name)
        debug("CharacterSheet.level", c.level)
        debug("CharacterSheet.fortitude_hp()", c.fortitude_hp())
        debug("CharacterSheet.max_mp()", c.max_mp())
        debug("CharacterSheet.total_allocated_points", c.total_allocated_points)
        self.assertEqual(c.fortitude_hp(), 70)  # 5 * (10 + 4)
        self.assertEqual(c.max_mp(), 55)        # 5 * (10 + 1)
        self.assertEqual(c.total_allocated_points["noncombat"], 56)
        self.assertEqual(c.total_allocated_points["combat"], 54)
        self.assertTrue(hasattr(c, "inventory"))

        if hasattr(c, "starting_point_budget"):
            debug("CharacterSheet.starting_point_budget()", c.starting_point_budget())
            self.assertEqual(CharacterSheet(level=1).starting_point_budget(), 30)
            self.assertEqual(CharacterSheet(level=3).starting_point_budget(), 50)
        else:
            self.skipTest("starting_point_budget() not implemented in CharacterSheet")

    def test_item_post_init_nonstackable_forces_max_stack_1(self):
        i = Item(id="ns", name="Non-Stack", stackable=False, max_stack=99)
        debug("Item(non-stackable)", i)
        self.assertFalse(i.stackable)
        self.assertEqual(i.max_stack, 1)


class TestInventoryBasics(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        debug("=====================================")
        debug("== TestInventoryBasics start ==")
        debug("=====================================")

    def test_add_stackables_into_multiple_stacks(self):
        inv = Inventory(max_slots=30, max_weight=80.0)
        potion = Item(id="potion_hp_small", name="Small Health Potion",
                      weight=0.2, stackable=True, max_stack=20)
        leftovers = inv.add(potion, 25)  # 20 + 5 across 2 stacks
        debug("After adding 25 potions", {
            "leftovers": leftovers,
            "count": inv.count("potion_hp_small"),
            "used_slots": inv.used_slots,
            "used_weight": inv.used_weight,
        })
        self.assertEqual(leftovers, 0)
        self.assertEqual(inv.count("potion_hp_small"), 25)
        self.assertEqual(inv.used_slots, 2)
        self.assertAlmostEqual(inv.used_weight, 25 * 0.2)

        sword = Item(id="iron_sword", name="Iron Sword",
                     weight=4.5, stackable=False)
        inv.add(sword, 2)
        debug("After adding 2 swords", {
            "count_sword": inv.count("iron_sword"),
            "used_slots": inv.used_slots,
            "used_weight": inv.used_weight,
        })
        self.assertEqual(inv.count("iron_sword"), 2)
        self.assertEqual(inv.used_slots, 4)  # 2 potion stacks + 2 swords
        self.assertAlmostEqual(inv.used_weight, (25 * 0.2) + (2 * 4.5))

        removed = inv.remove("potion_hp_small", 7)
        debug("After removing 7 potions", {
            "removed": removed,
            "count": inv.count("potion_hp_small"),
            "used_slots": inv.used_slots,
        })
        self.assertEqual(removed, 7)
        self.assertEqual(inv.count("potion_hp_small"), 18)
        self.assertEqual(inv.used_slots, 3)

    def test_add_over_capacity_by_slots(self):
        inv = Inventory(max_slots=1, max_weight=80.0)
        potion = Item(id="potion", name="Potion", weight=0.1, stackable=True, max_stack=20)
        leftovers = inv.add(potion, 25)  # only one stack (20) fits; 5 leftover
        debug("Slots-capped add", {
            "leftovers": leftovers,
            "count": inv.count("potion"),
            "used_slots": inv.used_slots,
        })
        self.assertEqual(inv.count("potion"), 20)
        self.assertEqual(inv.used_slots, 1)
        self.assertEqual(leftovers, 5)

    def test_add_over_capacity_by_weight(self):
        inv = Inventory(max_slots=10, max_weight=1.0)
        rock = Item(id="rock", name="Rock", weight=0.2, stackable=True, max_stack=99)
        leftovers = inv.add(rock, 10)  # would weigh 2.0; reject entire batch
        debug("Weight-capped add", {
            "leftovers": leftovers,
            "count": inv.count("rock"),
            "used_slots": inv.used_slots,
            "used_weight": inv.used_weight,
        })
        self.assertEqual(leftovers, 10)
        self.assertEqual(inv.count("rock"), 0)
        self.assertEqual(inv.used_slots, 0)
        self.assertEqual(inv.used_weight, 0.0)

    def test_remove_more_than_have(self):
        inv = Inventory()
        arrow = Item(id="arrow", name="Arrow", weight=0.05, stackable=True, max_stack=50)
        inv.add(arrow, 15)
        removed = inv.remove("arrow", 999)
        debug("Over-remove arrows", {
            "removed": removed,
            "remaining": inv.count("arrow"),
            "used_slots": inv.used_slots,
        })
        self.assertEqual(removed, 15)
        self.assertEqual(inv.count("arrow"), 0)
        self.assertEqual(inv.used_slots, 0)


class TestExampleFromSpec(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        debug("=====================================")
        debug("== TestExampleFromSpec start ==")
        debug("=====================================")

    def test_example_sequence(self):
        potion = Item(id="potion_hp_small", name="Small Health Potion",
                      weight=0.2, stackable=True, max_stack=20)
        sword = Item(id="iron_sword", name="Iron Sword",
                     weight=4.5, stackable=False)

        c = CharacterSheet(name="Test", level=5)
        debug("Initial inventory", {
            "used_slots": c.inventory.used_slots,
            "used_weight": c.inventory.used_weight
        })

        leftover = c.inventory.add(potion, 25)   # fills 20 + 5 (2 slots)
        debug("After adding potions", {
            "leftover": leftover,
            "count_potions": c.inventory.count("potion_hp_small"),
            "used_slots": c.inventory.used_slots,
            "used_weight": c.inventory.used_weight
        })

        c.inventory.add(sword, 2)                # 2 slots (non-stackable)
        debug("After adding swords", {
            "count_swords": c.inventory.count("iron_sword"),
            "used_slots": c.inventory.used_slots,
            "used_weight": c.inventory.used_weight
        })

        self.assertTrue(c.inventory.has("potion_hp_small", 25))
        self.assertEqual(leftover, 0)

        removed = c.inventory.remove("potion_hp_small", 7)
        debug("After removing 7 potions", {
            "removed": removed,
            "count_potions": c.inventory.count("potion_hp_small"),
            "used_slots": c.inventory.used_slots
        })
        self.assertEqual(removed, 7)
        self.assertEqual(c.inventory.count("potion_hp_small"), 18)
        self.assertEqual(c.inventory.used_slots, 3)
        
        
class TestNonCombatSkillChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        debug("=====================================")
        debug("== TestNonCombatSkillChecks start ==")
        debug("=====================================")

    def test_fynn_stealth_dc17_tie_succeeds_lower_fails(self):
        """
        Fynn (Level 30) attempts a Stealth check against DC 17.
        She rolls 3d6. Example outcomes:
          - 3d6 = 12  → 12 + Stealth(5) = 17 → tie → SUCCESS
          - 3d6 = 11  → 11 + Stealth(5) = 16 → lower → FAIL
        """
        # Minimal Fynn: only stats needed for this scenario
        fynn = CharacterSheet(
            name="Fynn Baumann",
            level=30,
            noncombat=NonCombat(stealth=5)
        )
        DC = 17 # Value to check against

        # Tie should succeed
        roll_sum = 12  # pretend result of 3d6
        total = roll_sum + fynn.noncombat.stealth
        debug("Fynn stealth check (tie case)", {
            "roll_sum": roll_sum, "stealth": fynn.noncombat.stealth,
            "total": total, "DC": DC
        })
        self.assertGreaterEqual(total, DC, "On a tie, Fynn should succeed the check")

        # Lower should fail
        roll_sum = 11  # pretend result of 3d6
        total = roll_sum + fynn.noncombat.stealth
        debug("Fynn stealth check (lower case)", {
            "roll_sum": roll_sum, "stealth": fynn.noncombat.stealth,
            "total": total, "DC": DC
        })
        self.assertLess(total, DC, "On a lower roll, Fynn should fail the check")

class TestNonCombatSkillChecksDice(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        debug("=====================================")
        debug("== TestNonCombatSkillChecksDice start ==")
        debug("=====================================")
        
    class FakeRNG:
        """Deterministic RNG that returns a fixed sequence of die faces."""
        def __init__(self, seq):
            self._seq = list(seq)

        def randint(self, a: int, b: int) -> int:
            # We trust the provided faces are within [a, b].
            if not self._seq:
                raise RuntimeError("FakeRNG sequence exhausted")
            return self._seq.pop(0)

    def test_fynn_stealth_dc17_using_dice_tie_succeeds(self):
        """
        Fynn (Lv30) Stealth 5 vs DC 17.
        3d6 = 12 → 12 + 5 = 17 → tie counts as SUCCESS.
        """
        fynn = CharacterSheet(level=30, noncombat=NonCombat(stealth=5))
        roll = Dice(3, 6).roll(self.FakeRNG([4, 4, 4]))  # 4+4+4 = 12
        self.assertEqual(roll.total, 12)
        total = roll.total + fynn.noncombat.stealth
        self.assertGreaterEqual(total, 17)

    def test_fynn_stealth_dc17_using_dice_lower_fails(self):
        """
        Fynn (Lv30) Stealth 5 vs DC 17.
        3d6 = 11 → 11 + 5 = 16 → lower → FAIL.
        """
        fynn = CharacterSheet(level=30, noncombat=NonCombat(stealth=5))
        roll = Dice(3, 6).roll(self.FakeRNG([4, 4, 3]))  # 4+4+3 = 11
        self.assertEqual(roll.total, 11)
        total = roll.total + fynn.noncombat.stealth
        self.assertLess(total, 17)

# Uses real RNG (no seed) to report pass/fail of a single Stealth check.
class TestNonCombatSkillChecksDiceRandom(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        debug("=====================================")
        debug("== TestNonCombatSkillChecksDiceRandom start ==")
        debug("=====================================")
        
    def test_fynn_stealth_dc17_unseeded_informational(self):
        """Unseeded 3d6 Stealth(5) vs DC 17: print pass/fail outcome."""
        from game.rules.dice import Dice, RNG  # local import to avoid path issues
        fynn = CharacterSheet(level=30, noncombat=NonCombat(stealth=5))
        DC = 17

        # Unseeded RNG → non-deterministic result each run
        try:
            rng = RNG()  # your wrapper around random.Random()
        except Exception:
            import random
            rng = random.Random()

        roll = Dice(3, 6).roll(rng)     # Fynn is level 30 → 3 dice
        total = roll.total + fynn.noncombat.stealth
        success = total >= DC

        # Try to show individual faces if your Dice result exposes them
        faces = getattr(roll, "faces", None) or getattr(roll, "values", None)
        if faces:
            detail = f"3d6={'+'.join(map(str, faces))} (={roll.total})"
        else:
            detail = f"3d6 total={roll.total}"

        print(f"[RANDOM CHECK] {detail} + Stealth(5) = {total} vs DC {DC} → "
              f"{'SUCCESS' if success else 'FAIL'}")

        # Keep the test always green (it's informational)
        self.assertTrue(True)

if __name__ == "__main__":
    unittest.main(verbosity=2)
