"""Rates you can trust (Chapter 25): the Wilson interval, and whether every run passed."""
from __future__ import annotations

import math
import statistics


def wilson(passed: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """The Wilson score interval for a pass rate: sound near zero and one, where the textbook
    interval fails, and for the small run counts a voice test can afford."""
    if n == 0:
        return (0.0, 1.0)
    p = passed / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, centre - half), min(1.0, centre + half))


def rate(passed: int, n: int) -> dict:
    lo, hi = wilson(passed, n)
    return {"passed": passed, "runs": n, "rate": round(passed / n, 3) if n else None,
            "interval": [round(lo, 3), round(hi, 3)], "all_passed": n > 0 and passed == n}


def percentile(values: list[float], q: float) -> float | None:
    """The q-th percentile by the nearest rank: no interpolation between two real waits."""
    if not values:
        return None
    s = sorted(values)
    k = max(0, math.ceil(q / 100 * len(s)) - 1)
    return s[k]


def median(values: list[float]) -> float | None:
    return statistics.median(values) if values else None
