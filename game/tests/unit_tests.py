# unit_tests.py
import unittest

# Adjust the import path if your package layout differs
from game.rules.stats import (
    CharacterSheet, NonCombat, Combat,
)
from game.rules.inventory import Inventory, Item


class TestStatsModels(unittest.TestCase):
    def test_noncombat_totals(self):
        nc = NonCombat(
            force=1, presence=2, resistance=3,     # 6
            stealth=4, nimble=5, reaction=6,       # 15
            memory=7, logic=8, calm=9,             # 24
            charisma=10, lure=0, sense=1           # 11
        )
        self.assertEqual(nc.section_totals()["strength"], 6)
        self.assertEqual(nc.section_totals()["dexterity"], 15)
        self.assertEqual(nc.section_totals()["magic"], 24)
        self.assertEqual(nc.section_totals()["spirit"], 11)
        self.assertEqual(nc.total_points(), 56)

    def test_combat_totals(self):
        cb = Combat(
            melee_atk=2, block=3, hp_scaling=4,           # 9
            ranged_atk=5, dodge=6, crit_damage=7,        # 18
            magic_atk_arcane=8, magic_resist=9, mana_scaling=1,  # 18
            magic_atk_spirit=2, debuff_resist=3, crit_rate=4     # 9
        )
        self.assertEqual(cb.section_totals()["strength"], 9)
        self.assertEqual(cb.section_totals()["dexterity"], 18)
        self.assertEqual(cb.section_totals()["magic"], 18)
        self.assertEqual(cb.section_totals()["spirit"], 9)
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
        # HP = L * (10 + hp_scaling) = 5 * 14 = 70
        self.assertEqual(c.fortitude_hp(), 70)
        # MP = L * (10 + mana_scaling) = 5 * 11 = 55
        self.assertEqual(c.max_mp(), 55)
        self.assertEqual(c.total_allocated_points["noncombat"], 56)
        self.assertEqual(c.total_allocated_points["combat"], 54)
        # Inventory is present by default
        self.assertTrue(hasattr(c, "inventory"))

        # Optional: starting_point_budget if implemented
        if hasattr(c, "starting_point_budget"):
            self.assertEqual(CharacterSheet(level=1).starting_point_budget(), 30)
            self.assertEqual(CharacterSheet(level=3).starting_point_budget(), 50)
        else:
            self.skipTest("starting_point_budget() not implemented in CharacterSheet")

    def test_item_post_init_nonstackable_forces_max_stack_1(self):
        i = Item(id="ns", name="Non-Stack", stackable=False, max_stack=99)
        self.assertFalse(i.stackable)
        self.assertEqual(i.max_stack, 1)


class TestInventoryBasics(unittest.TestCase):
    def test_add_stackables_into_multiple_stacks(self):
        inv = Inventory(max_slots=30, max_weight=80.0)
        potion = Item(id="potion_hp_small", name="Small Health Potion",
                      weight=0.2, stackable=True, max_stack=20)
        leftovers = inv.add(potion, 25)  # 20 + 5 across 2 stacks
        self.assertEqual(leftovers, 0)
        self.assertEqual(inv.count("potion_hp_small"), 25)
        self.assertEqual(inv.used_slots, 2)
        self.assertAlmostEqual(inv.used_weight, 25 * 0.2)

        sword = Item(id="iron_sword", name="Iron Sword",
                     weight=4.5, stackable=False)
        inv.add(sword, 2)
        self.assertEqual(inv.count("iron_sword"), 2)
        self.assertEqual(inv.used_slots, 4)  # 2 potion stacks + 2 swords
        self.assertAlmostEqual(inv.used_weight, (25 * 0.2) + (2 * 4.5))

        # Remove 7 potions: should collapse one small stack and reduce the other
        removed = inv.remove("potion_hp_small", 7)
        self.assertEqual(removed, 7)
        self.assertEqual(inv.count("potion_hp_small"), 18)
        # Expect one potion stack left + 2 swords = 3 slots
        self.assertEqual(inv.used_slots, 3)

    def test_add_over_capacity_by_slots(self):
        inv = Inventory(max_slots=1, max_weight=80.0)
        potion = Item(id="potion", name="Potion", weight=0.1, stackable=True, max_stack=20)
        leftovers = inv.add(potion, 25)  # only one stack (20) fits; 5 leftover
        self.assertEqual(inv.count("potion"), 20)
        self.assertEqual(inv.used_slots, 1)
        self.assertEqual(leftovers, 5)

    def test_add_over_capacity_by_weight(self):
        inv = Inventory(max_slots=10, max_weight=1.0)
        rock = Item(id="rock", name="Rock", weight=0.2, stackable=True, max_stack=99)
        leftovers = inv.add(rock, 10)  # would weigh 2.0; implementation rejects batch
        self.assertEqual(leftovers, 10)
        self.assertEqual(inv.count("rock"), 0)
        self.assertEqual(inv.used_slots, 0)
        self.assertEqual(inv.used_weight, 0.0)

    def test_remove_more_than_have(self):
        inv = Inventory()
        arrow = Item(id="arrow", name="Arrow", weight=0.05, stackable=True, max_stack=50)
        inv.add(arrow, 15)
        removed = inv.remove("arrow", 999)
        self.assertEqual(removed, 15)
        self.assertEqual(inv.count("arrow"), 0)
        self.assertEqual(inv.used_slots, 0)


class TestExampleFromSpec(unittest.TestCase):
    """Exact scenario the user outlined (potions + swords)."""
    def test_example_sequence(self):
        potion = Item(id="potion_hp_small", name="Small Health Potion",
                      weight=0.2, stackable=True, max_stack=20)
        sword = Item(id="iron_sword", name="Iron Sword",
                     weight=4.5, stackable=False)

        c = CharacterSheet(name="Test", level=5)
        leftover = c.inventory.add(potion, 25)   # fills 20 + 5 (2 slots)
        c.inventory.add(sword, 2)                # 2 slots (non-stackable)

        self.assertTrue(c.inventory.has("potion_hp_small", 25))
        self.assertEqual(leftover, 0)

        removed = c.inventory.remove("potion_hp_small", 7)
        self.assertEqual(removed, 7)
        self.assertEqual(c.inventory.count("potion_hp_small"), 18)
        # Post-removal slot count: 1 potion stack + 2 swords = 3
        self.assertEqual(c.inventory.used_slots, 3)


if __name__ == "__main__":
    unittest.main()
