"""Numeric conventions shared across the Tier 1 feature groups (specs_features.md §1.4–1.6).

One implementation of each, so two feature groups cannot quietly disagree about what a ratio
does with a zero denominator, or about which standard deviation is meant.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

# §1.6 — floats are rounded at the point of return, never as an intermediate.
ROUNDING = 4


def ratio(numerator: int, denominator: int) -> float:
    """§1.4 — a share of a whole, `0.0` when the denominator is zero.

    Never `null`: a Tier 1 ratio answering `null` while its neighbour answers `0.0` for the
    same input is worse than either choice applied consistently. Tier 2/3 differ, and say so.
    """
    if not denominator:
        return 0.0
    return round(numerator / denominator, ROUNDING)


def mean(values: Sequence[float]) -> float:
    """§1.5 — arithmetic mean, `0.0` for an empty series."""
    if not values:
        return 0.0
    return round(sum(values) / len(values), ROUNDING)


def stdev(values: Sequence[float]) -> float:
    """§1.5 — population standard deviation (`ddof=0`), `0.0` below two values.

    Population rather than sample: the sentences of a document *are* the population being
    described, not a draw from a larger one, and `ddof=0` leaves a one-element series defined
    at `0.0` where the sample form would be undefined.

    The mean is computed unrounded here — §1.6 forbids rounding an intermediate.
    """
    if len(values) < 2:
        return 0.0
    mu = sum(values) / len(values)
    variance = sum((value - mu) ** 2 for value in values) / len(values)
    return round(math.sqrt(variance), ROUNDING)
