from copy import deepcopy
from game.rules.combat import AutoBattle, AttackKind
from game.characters.example_fynn import fynn

fynn1 = deepcopy(fynn)
fynn2 = deepcopy(fynn)
fynn2.name = "Fynn (Mirror)"

# (A) Chance: 1.67% (set base to 0 if you don't want the default +5%)
fynn1.combat.base_crit_chance_pct = 0.0
fynn2.combat.base_crit_chance_pct = 0.0
fynn1.combat.crit_rate = 19
fynn2.combat.crit_rate = 19

# (B) Multiplier: 1.67x
fynn1.combat.crit_multiplier = 1.67
fynn2.combat.crit_multiplier = 1.67


battle = AutoBattle(fynn1, fynn2, kind=AttackKind.MELEE)
A, B, logs = battle.run(rng_seed=42)

for i, ev in enumerate(logs, 1):
    if ev.hit:
        hit_bits = (f"base-hit {ev.base_attack_total}"
                    f"{f' → ×{ev.crit_mult:.2f} = {ev.attack_total}' if ev.crit else ''}")
        dmg_bits = (f"{'CRIT ' if ev.crit else ''}damage {ev.damage} "
                    f"(base {ev.base_damage}) from {ev.damage_faces}")
        print(f"{i:02d} {ev.attacker} hits {ev.defender} [{ev.kind}] "
              f"(thr {ev.threshold}; to-hit using {ev.attack_faces}: {hit_bits}); "
              f"{dmg_bits}. {ev.defender} HP/MP → {ev.defender_hp_after}/{ev.defender_mp_after}")
    else:
        hit_bits = (f"base-hit {ev.base_attack_total}"
                    f"{f' → ×{ev.crit_mult:.2f} = {ev.attack_total}' if ev.crit else ''}")
        print(f"{i:02d} {ev.attacker} misses {ev.defender} [{ev.kind}] "
              f"(thr {ev.threshold}; to-hit using {ev.attack_faces}: {hit_bits}) — {ev.note}")

print("\nResult:")
print(f"{A.name}: HP={A.hp}, MP={A.mp}")
print(f"{B.name}: HP={B.hp}, MP={B.mp}")
