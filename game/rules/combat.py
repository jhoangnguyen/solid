# game/rules/combat.py
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Tuple

from game.rules.dice import Dice
try:
    from game.rules.dice import RNG
except Exception:  # pragma: no cover
    import random as RNG  # fallback; has randint

from game.rules.stats import CharacterSheet, Combat


# ---- helpers ---------------------------------------------------------------

def _effective_dice_count(sheet: CharacterSheet) -> int:
    """
    One die per 10 levels, starting at 1 (e.g., Lv1->1d, Lv30->3d).
    If the sheet already sets a higher dice_count, prefer that.
    """
    by_level = max(1, sheet.level // 10)
    return max(getattr(sheet, "dice_count", 1) or 1, by_level)

def _attack_mod(cb: Combat, kind: "AttackKind") -> int:
    if kind is AttackKind.MELEE:   return cb.melee_atk
    if kind is AttackKind.RANGED:  return cb.ranged_atk
    if kind is AttackKind.ARCANE:  return cb.magic_atk_arcane
    if kind is AttackKind.SPIRIT:  return cb.magic_atk_spirit
    return 0

def _defense_threshold(cb: Combat, kind: "AttackKind") -> int:
    # Simple first pass:
    # - Physical attacks check vs max(block, dodge).
    # - Arcane checks vs magic_resist; Spirit checks vs debuff_resist.
    if kind in (AttackKind.MELEE, AttackKind.RANGED):
        return max(cb.block, cb.dodge)
    if kind is AttackKind.ARCANE:
        return cb.magic_resist
    if kind is AttackKind.SPIRIT:
        return cb.debuff_resist
    return 0

def _crit_roll(rng: RNG, cb: Combat) -> tuple[bool, float]:
    """
    Crit chance supports floats (e.g., 1.67 means 1.67%).
    Default base chance is 5% unless you override via `base_crit_chance_pct`.
    Multiplier defaults to 1.5 + crit_damage% unless you set `crit_multiplier`.
    """
    base = float(getattr(cb, "base_crit_chance_pct", 5.0))
    rate = float(getattr(cb, "crit_rate", 0.0))
    chance = max(0.0, base + rate) / 100.0

    # use RNG.random() to support sub-percent precision
    is_crit = (rng.random() < chance)

    # allow a direct override, else fall back to 1.5 + crit_damage%
    override = getattr(cb, "crit_multiplier", None)
    if override is not None:
        mult = float(override)
    else:
        mult = 1.5 + (max(0.0, float(getattr(cb, "crit_damage", 0.0))) / 100.0)

    return is_crit, mult


# ---- public API ------------------------------------------------------------

class AttackKind(str, Enum):
    MELEE  = "melee"
    RANGED = "ranged"
    ARCANE = "arcane"
    SPIRIT = "spirit"

@dataclass
class AttackLog:
    attacker: str
    defender: str
    kind: AttackKind
    hit: bool
    attack_total: int
    attack_faces: List[int]
    threshold: int
    damage: int = 0
    damage_faces: Optional[List[int]] = None
    crit: bool = False
    crit_mult: float = 1.00
    defender_hp_after: int = 0
    defender_mp_after: int = 0
    note: str = ""
    base_attack_total: int = 0   # to-hit total before crit multiplier
    base_damage: int = 0         # damage before crit multiplier

@dataclass
class BattleState:
    name: str
    sheet: CharacterSheet
    hp: int
    mp: int

    @classmethod
    def from_sheet(cls, s: CharacterSheet) -> "BattleState":
        return cls(
            name=s.name or "Unknown",
            sheet=s,
            hp=s.fortitude_hp(),  # Lv * (10 + hp_scaling)
            mp=s.max_mp(),        # Lv * (10 + mana_scaling)
        )

    def defeated(self) -> bool:
        # “Downed” once HP==0 and MP has been fully drained.
        return self.hp <= 0 and self.mp <= 0


class AutoBattle:
    """
    Minimal auto-battler:
      - To-hit: roll (NdS + atk_mod) vs defense threshold (tie = success).
      - On hit: roll damage (NdS + atk_mod) and apply crit.
      - HP to 0 spills to MP at 10:1 thereafter.
      - Turn order by speed (acts / time unit).
    """

    def __init__(self, a: CharacterSheet, b: CharacterSheet, *, kind: AttackKind = AttackKind.MELEE):
        self.A = BattleState.from_sheet(a)
        self.B = BattleState.from_sheet(b)
        self.kind = kind

    # def _step_attack(self, atk: BattleState, dfn: BattleState, rng: RNG) -> AttackLog:
    #     count = _effective_dice_count(atk.sheet)
    #     sides = getattr(atk.sheet, "dice_sides", 6)
    #     atk_mod = _attack_mod(atk.sheet.combat, self.kind)
    #     thr    = _defense_threshold(dfn.sheet.combat, self.kind)

    #     # roll crit first so it can amplify the to-hit roll
    #     crit, mult = _crit_roll(rng, atk.sheet.combat)

    #     # --- To-hit ---
    #     hit_roll = Dice(count, sides).roll(rng)
    #     attack_total = hit_roll.total + atk_mod
    #     if crit:
    #         attack_total = int(attack_total * mult)  # apply crit to the to-hit total

    #     hit = (attack_total >= thr)  # tie still succeeds

    #     log = AttackLog(
    #         attacker=atk.name, defender=dfn.name, kind=self.kind,
    #         hit=hit, attack_total=attack_total, attack_faces=hit_roll.rolls, threshold=thr,
    #         crit=crit, crit_mult=mult
    #     )

    #     if not hit:
    #         if self.kind in (AttackKind.MELEE, AttackKind.RANGED):
    #             log.note = "Blocked" if dfn.sheet.combat.block >= dfn.sheet.combat.dodge else "Dodged"
    #         else:
    #             log.note = "Resisted"
    #         # optional clarity when a crit still misses:
    #         if crit:
    #             log.note += " (crit triggered)"
    #         log.defender_hp_after, log.defender_mp_after = dfn.hp, dfn.mp
    #         return log

    #     # --- Damage ---
    #     dmg_roll = Dice(count, sides).roll(rng)
    #     raw = dmg_roll.total + atk_mod
    #     if crit:
    #         raw = int(raw * mult)  # apply the same crit to damage

    #     dmg = max(0, raw)

    #     # Apply to defender with HP→MP spill at 10:1 after HP=0
    #     if dfn.hp > 0:
    #         if dmg >= dfn.hp:
    #             overflow = dmg - dfn.hp
    #             dfn.hp = 0
    #             if overflow > 0:
    #                 # drain MP at 10:1 (ceil)
    #                 mp_loss = (overflow + 9) // 10
    #                 dfn.mp = max(0, dfn.mp - mp_loss)
    #         else:
    #             dfn.hp -= max(0, dmg)
    #     else:
    #         # Already at 0 HP → all damage drains MP at 10:1
    #         mp_loss = (dmg + 9) // 10
    #         dfn.mp = max(0, dfn.mp - mp_loss)

    #     log.damage = dmg
    #     log.damage_faces = dmg_roll.rolls
    #     log.crit = crit
    #     log.crit_mult = mult
    #     log.defender_hp_after, log.defender_mp_after = dfn.hp, dfn.mp
    #     return log

    def _step_attack(self, atk: BattleState, dfn: BattleState, rng: RNG) -> AttackLog:
        count = _effective_dice_count(atk.sheet)
        sides = getattr(atk.sheet, "dice_sides", 6)
        atk_mod = _attack_mod(atk.sheet.combat, self.kind)
        thr    = _defense_threshold(dfn.sheet.combat, self.kind)

        # roll crit first so it can affect to-hit and damage
        crit, mult = _crit_roll(rng, atk.sheet.combat)

        # --- To-hit ---
        hit_roll = Dice(count, sides).roll(rng)
        base_attack_total = hit_roll.total + atk_mod
        attack_total = int(base_attack_total * mult) if crit else base_attack_total
        hit = (attack_total >= thr)  # tie succeeds

        log = AttackLog(
            attacker=atk.name, defender=dfn.name, kind=self.kind,
            hit=hit, attack_total=attack_total, attack_faces=hit_roll.rolls, threshold=thr,
            crit=crit, crit_mult=mult, base_attack_total=base_attack_total
        )

        if not hit:
            if self.kind in (AttackKind.MELEE, AttackKind.RANGED):
                log.note = "Blocked" if dfn.sheet.combat.block >= dfn.sheet.combat.dodge else "Dodged"
            else:
                log.note = "Resisted"
            if crit:
                log.note += " (crit triggered)"
            log.defender_hp_after, log.defender_mp_after = dfn.hp, dfn.mp
            return log

        # --- Damage ---
        dmg_roll = Dice(count, sides).roll(rng)
        base_damage = dmg_roll.total + atk_mod
        raw = int(base_damage * mult) if crit else base_damage
        dmg = max(0, raw)

        # Apply to defender with HP→MP spill at 10:1 after HP=0
        if dfn.hp > 0:
            if dmg >= dfn.hp:
                overflow = dmg - dfn.hp
                dfn.hp = 0
                if overflow > 0:
                    mp_loss = (overflow + 9) // 10
                    dfn.mp = max(0, dfn.mp - mp_loss)
            else:
                dfn.hp -= dmg
        else:
            mp_loss = (dmg + 9) // 10
            dfn.mp = max(0, dfn.mp - mp_loss)

        log.damage = dmg
        log.damage_faces = dmg_roll.rolls
        log.base_damage = base_damage
        log.defender_hp_after, log.defender_mp_after = dfn.hp, dfn.mp
        return log

    def run(self, *, rng_seed: Optional[int] = None, max_actions: int = 200) -> Tuple[BattleState, BattleState, List[AttackLog]]:
        # rng with seed for determinism if desired
        rng = RNG(rng_seed) if rng_seed is not None else RNG()

        # Simple speed scheduler (lower next_time acts first)
        def period(s: BattleState) -> float:
            spd = max(0.0001, getattr(s.sheet, "speed", 1))  # avoid div/0; default=1 act/unit
            return 1.0 / float(spd)

        tA, tB = 0.0, 0.0
        pA, pB = period(self.A), period(self.B)
        logs: List[AttackLog] = []

        actions = 0
        while actions < max_actions and not self.A.defeated() and not self.B.defeated():
            if tA <= tB:
                logs.append(self._step_attack(self.A, self.B, rng))
                tA += pA
            else:
                logs.append(self._step_attack(self.B, self.A, rng))
                tB += pB
            actions += 1

        return self.A, self.B, logs
