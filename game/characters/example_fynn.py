from game.rules.stats import CharacterSheet, NonCombat, Combat

fynn = CharacterSheet(
    name="Fynn Baumann",
    level=30,
    speed=4.0,
    dice_sides=6,
    dice_count=3,  # per doc: L30 example rolls 3 dice

    noncombat=NonCombat(
        # section buckets
        strength=96, dexterity=38, magic=38, spirit=146,
        # Strength (Deliverance)
        force=38, presence=10, resistance=48,
        # Dexterity (Lithe)
        stealth=2, nimble=9, reaction=27,
        # Magic (Conscious)
        memory=8, logic=15, calm=15,
        # Spirit (Wisdom)
        charisma=44, lure=0, sense=102,
    ),

    combat=Combat(
        # section buckets
        strength=96, dexterity=38, magic=38, spirit=146,
        # Strength (Destruction)
        melee_atk=14, block=38, hp_scaling=38,
        # Dexterity (Lethality)
        ranged_atk=4, dodge=17, crit_damage=17,
        # Magic (Command)
        magic_atk_arcane=0, magic_resist=30, mana_scaling=8,
        # Spirit (Wish)
        magic_atk_spirit=66, debuff_resist=66, crit_rate=14,
    ),
)

# assert fynn.fortitude_hp() == 1440
# assert fynn.max_mp() == 540
