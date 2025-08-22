from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple
import random


class RNG:
    """Small wrapper around random.Random so we can seed deterministically.

    Example:
        rng = RNG(seed=42)
        rng.randint(1, 6)
    """

    __slots__ = ("_r",)

    def __init__(self, seed: Optional[int] = None) -> None:
        self._r = random.Random(seed)

    def randint(self, a: int, b: int) -> int:
        return self._r.randint(a, b)

    def random(self) -> float:
        return self._r.random()

    def choice(self, seq):
        return self._r.choice(seq)

    def seed(self, seed: Optional[int]) -> None:
        self._r.seed(seed)


@dataclass(frozen=True)
class RollResult:
    total: int
    rolls: List[int]
    kept: List[int]
    discarded: List[int]
    modifier: int = 0

    def __str__(self) -> str:
        parts = ["+".join(map(str, self.kept))]
        if self.discarded:
            parts.append(f"(dropped:{self.discarded})")
        if self.modifier:
            parts.append(f"{'+' if self.modifier >= 0 else ''}{self.modifier}")
        parts.append(f"= {self.total}")
        return " ".join(parts)


class Dice:
    """Configurable dice roller.

    Supports:
      - NdS+M notation via constructor (count, sides, modifier)
      - keep-highest (khK), keep-lowest (klK) or drop-lowest (dlD)
      - roll(), roll_best_of(n) and roll_many(n)

    Examples:
        >>> rng = RNG(7)
        >>> Dice(3, 6).roll(rng)                   # 3d6
        >>> Dice(4, 6, keep=3).roll(rng)           # 4d6 keep highest 3
        >>> Dice(4, 6, keep_lowest=2).roll(rng)    # 4d6 keep lowest 2
        >>> Dice(1, 20).roll_best_of(2, rng)       # d20 advantage
        >>> Dice.parse("10d6kl3").roll_many(5)    # parse + keep-lowest + 5 trials
    """

    __slots__ = ("count", "sides", "modifier", "keep", "keep_lowest", "drop")

    def __init__(
        self,
        count: int = 1,
        sides: int = 6,
        modifier: int = 0,
        *,
        keep: Optional[int] = None,          # keep highest K
        keep_lowest: Optional[int] = None,   # keep lowest K
        drop: int = 0,                       # drop lowest D
    ) -> None:
        if count <= 0:
            raise ValueError("count must be >= 1")
        if sides <= 1:
            raise ValueError("sides must be >= 2")
        # enforce mutual exclusivity of keep/drop modes
        modes = sum(1 for x in (keep, keep_lowest, drop and True) if x)
        if modes > 1:
            raise ValueError("Specify at most one of keep, keep_lowest, or drop")
        if keep is not None and (keep < 1 or keep > count):
            raise ValueError("keep must be in [1, count]")
        if keep_lowest is not None and (keep_lowest < 1 or keep_lowest > count):
            raise ValueError("keep_lowest must be in [1, count]")
        if drop < 0 or drop >= count:
            raise ValueError("drop must be in [0, count-1]")

        self.count = int(count)
        self.sides = int(sides)
        self.modifier = int(modifier)
        self.keep = int(keep) if keep is not None else None
        self.keep_lowest = int(keep_lowest) if keep_lowest is not None else None
        self.drop = int(drop)

    # --- Constructors -----------------------------------------------------
    @classmethod
    def parse(cls, s: str) -> "Dice":
        """Parse minimal NdS(+/-)M with suffixes: 'khK', 'klK', 'dlD'.
        Examples: '3d6+2', '4d6kh3', '4d6kl2', '4d6dl1'.
        """
        s = s.strip().lower()
        # base NdS
        try:
            left, *rest = s.split("d", 1)
            count = int(left) if left else 1
            if rest:
                rhs = rest[0]
            else:
                raise ValueError
        except Exception as e:
            raise ValueError(f"Invalid dice string: {s}") from e

        # read sides then optional modifier/suffix
        sides_str = ""
        i = 0
        while i < len(rhs) and rhs[i].isdigit():
            sides_str += rhs[i]
            i += 1
        if not sides_str:
            raise ValueError(f"Invalid dice string: {s}")
        sides = int(sides_str)

        modifier = 0
        keep = None
        keep_lowest = None
        drop = 0
        tail = rhs[i:]

        # suffixes order-agnostic (simple scan)
        j = 0
        while j < len(tail):
            if tail.startswith("+", j) or tail.startswith("-", j):
                sign = 1 if tail[j] == "+" else -1
                j += 1
                num = ""
                while j < len(tail) and tail[j].isdigit():
                    num += tail[j]
                    j += 1
                if not num:
                    raise ValueError(f"Invalid modifier in: {s}")
                modifier += sign * int(num)
                continue

            if tail.startswith("kh", j):
                j += 2
                num = ""
                while j < len(tail) and tail[j].isdigit():
                    num += tail[j]
                    j += 1
                if not num:
                    raise ValueError(f"Invalid khK in: {s}")
                keep = int(num)
                continue

            if tail.startswith("kl", j):
                j += 2
                num = ""
                while j < len(tail) and tail[j].isdigit():
                    num += tail[j]
                    j += 1
                if not num:
                    raise ValueError(f"Invalid klK in: {s}")
                keep_lowest = int(num)
                continue

            if tail.startswith("dl", j):
                j += 2
                num = ""
                while j < len(tail) and tail[j].isdigit():
                    num += tail[j]
                    j += 1
                if not num:
                    raise ValueError(f"Invalid dlD in: {s}")
                drop = int(num)
                continue

            raise ValueError(f"Unrecognized token near '{tail[j:]}' in: {s}")

        return cls(count, sides, modifier, keep=keep, keep_lowest=keep_lowest, drop=drop)

    # --- Rolls ------------------------------------------------------------
    def roll(self, rng: Optional[RNG] = None) -> RollResult:
        r = rng or RNG()
        rolls = [r.randint(1, self.sides) for _ in range(self.count)]
        kept, discarded = self._apply_keep_drop(rolls)
        total = sum(kept) + self.modifier
        return RollResult(total=total, rolls=rolls, kept=kept, discarded=discarded, modifier=self.modifier)

    def roll_best_of(self, n: int, rng: Optional[RNG] = None) -> RollResult:
        """Roll this dice expression n times and keep the best total.
        Use for 'advantage' (n=2) or more exotic effects.
        """
        if n < 1:
            raise ValueError("n must be >= 1")
        r = rng or RNG()
        best: Optional[RollResult] = None
        for _ in range(n):
            cur = self.roll(r)
            if best is None or cur.total > best.total:
                best = cur
        assert best is not None
        return best

    def roll_many(self, n: int, rng: Optional[RNG] = None) -> List[RollResult]:
        """Roll this dice expression n independent times and return all results."""
        if n < 1:
            raise ValueError("n must be >= 1")
        r = rng or RNG()
        return [self.roll(r) for _ in range(n)]

    # --- Helpers ----------------------------------------------------------
    def _apply_keep_drop(self, rolls: List[int]) -> Tuple[List[int], List[int]]:
        if self.keep is not None:
            idx_sorted = sorted(range(len(rolls)), key=lambda i: rolls[i], reverse=True)
            keep_idx = set(idx_sorted[: self.keep])
            kept = [rolls[i] for i in range(len(rolls)) if i in keep_idx]
            discarded = [rolls[i] for i in range(len(rolls)) if i not in keep_idx]
            return kept, discarded
        if self.keep_lowest is not None:
            idx_sorted = sorted(range(len(rolls)), key=lambda i: rolls[i])
            keep_idx = set(idx_sorted[: self.keep_lowest])
            kept = [rolls[i] for i in range(len(rolls)) if i in keep_idx]
            discarded = [rolls[i] for i in range(len(rolls)) if i not in keep_idx]
            return kept, discarded
        if self.drop:
            idx_sorted = sorted(range(len(rolls)), key=lambda i: rolls[i])
            drop_idx = set(idx_sorted[: self.drop])
            kept = [rolls[i] for i in range(len(rolls)) if i not in drop_idx]
            discarded = [rolls[i] for i in range(len(rolls)) if i in drop_idx]
            return kept, discarded
        return rolls[:], []

    # --- Pretty -----------------------------------------------------------
    def __repr__(self) -> str:
        core = f"{self.count}d{self.sides}"
        suf = ""
        if self.keep is not None:
            suf += f"kh{self.keep}"
        if self.keep_lowest is not None:
            suf += f"kl{self.keep_lowest}"
        if self.drop:
            suf += f"dl{self.drop}"
        if self.modifier:
            suf += f"{self.modifier:+d}"
        return f"Dice({core}{suf})"


# Convenience predefs for common curves
D6 = Dice(1, 6)
D20 = Dice(1, 20)
BELL_2D6 = Dice(2, 6)
TIGHT_3D4 = Dice(3, 4)
VOLATILE_D20 = Dice(1, 20)


if __name__ == "__main__":
    rng = RNG(123)
    print("-- basic --")
    print(Dice(3, 6).roll(rng))
    print(Dice(4, 6, keep=3).roll(rng))
    print(Dice(4, 6, keep_lowest=2).roll(rng))
    print(Dice.parse("4d6kh3").roll(rng))
    print(Dice.parse("2d6+1").roll(rng))
    print(Dice.parse("10d6kl3").roll_many(5, rng))

    print("-- advantage (best of 2) --")
    print(D20.roll_best_of(2, rng))
