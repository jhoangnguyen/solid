from copy import deepcopy
from game.rules.combat import calc_acc, calc_dod, AutoBattle, AttackKind
from game.characters.example_fynn import fynn

def _thr_label(kind: AttackKind) -> str:
    if kind in (AttackKind.MELEE, AttackKind.RANGED): return "Block"
    if kind is AttackKind.ARCANE: return "MagicRes"
    if kind is AttackKind.SPIRIT: return "DebuffRes"
    return "Threshold"

fynn1 = deepcopy(fynn)
fynn2 = deepcopy(fynn)
fynn2.name = "Fynn (Mirror)"

fynn1.restore_full()
fynn2.restore_full()

# (A) Chance: 1.67% (set base to 0 if you don't want the default +5%)
fynn1.combat.base_crit_chance_pct = 0.0
fynn2.combat.base_crit_chance_pct = 0.0
fynn1.combat.crit_rate = 19
fynn2.combat.crit_rate = 19

# (B) Multiplier: 1.67x
fynn1.combat.crit_multiplier = 1.67
fynn2.combat.crit_multiplier = 1.67

fynn1.combat.accuracy = 120
fynn2.combat.dodge = 110

fynn1.combat.block = 30
fynn2.combat.block = 30


print(f"START: {fynn1.name} HP={fynn1.current_hp}/{fynn1.fortitude_hp()}  MP={fynn1.current_mp}/{fynn1.max_mp()} | "
      f"{fynn2.name} HP={fynn2.current_hp}/{fynn2.fortitude_hp()}  MP={fynn2.current_mp}/{fynn2.max_mp()}")

battle = AutoBattle(fynn1, fynn2, kind=AttackKind.MELEE)
# A, B, logs = battle.run(rng_seed=42)
A, B, logs = battle.run()

# map names to live BattleState so we can look up stats
who = {A.name: A, B.name: B}

for i, ev in enumerate(logs, 1):
    atk = who[ev.attacker]
    dfn = who[ev.defender]
    acc = calc_acc(atk.sheet)
    dod = calc_dod(dfn.sheet)
    kind_str = ev.kind.value.upper()

    # Header: who is attacking whom
    print(f"{i:02d} {ev.attacker} → {ev.defender} [{kind_str}]")

    # Phase 1: Evasion (ACC vs DOD)
    # If evasion failed, your code records no attack_faces and base_hit=0
    evaded = (not ev.attack_faces) and not ev.hit
    if evaded:
        # ev.note already contains the p/roll when it was an evasion fail
        print(f"   Evasion: ACC {acc} vs DOD {dod} — FAILED  {('— ' + ev.note) if ev.note else ''}")
        continue
    else:
        print(f"   Evasion: ACC {acc} vs DOD {dod} — PASSED")

    # Phase 2: To-hit (base-hit vs threshold)
    thr_lbl = _thr_label(ev.kind)
    hit_str = "HIT" if ev.hit else "MISS"
    print(f"   To-hit: base {ev.base_attack_total} vs THR {ev.threshold} ({thr_lbl}) — {hit_str}   [rolls {ev.attack_faces}]")
    if not ev.hit:
        if ev.note:
            print(f"   Note: {ev.note}")
        continue

    # Phase 3: Damage (crit only affects damage now)
    crit_tag = "CRIT " if ev.crit else ""
    print(f"   Damage: {crit_tag}{ev.damage} (base {ev.base_damage}, from rolls {ev.damage_faces}) → "
          f"{ev.defender} HP/MP {ev.defender_hp_after}/{ev.defender_mp_after}")

print(f"END:   {fynn1.name} HP={fynn1.current_hp}/{fynn1.fortitude_hp()}  MP={fynn1.current_mp}/{fynn1.max_mp()} | "
      f"{fynn2.name} HP={fynn2.current_hp}/{fynn2.fortitude_hp()}  MP={fynn2.current_mp}/{fynn2.max_mp()}")