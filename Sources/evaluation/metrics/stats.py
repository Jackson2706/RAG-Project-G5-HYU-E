"""Paired significance tests for the pre-registered comparisons (docs/aaes_spec.md "Metrics (P8)").

`paired_compare` works for any statistic of a list of per-case items (a mean, or macro-F1 of actions):
cases are resampled together (bootstrap CI of stat(a) - stat(b)) or swapped between the two systems
(permutation p-value).
"""

from __future__ import annotations

import random
from collections.abc import Callable


def paired_compare(a: list, b: list, stat: Callable[[list], float], resamples: int = 10_000, seed: int = 0) -> dict:
    """Paired comparison of two systems on the same cases.

    Returns {"diff", "ci_low", "ci_high", "p"}: bootstrap 95% CI and a two-sided swap-permutation p-value,
    (hits + 1) / (resamples + 1). Identical systems -> diff 0 and p 1.0. Twelve cases where a scores 1 and
    b scores 0 under the mean -> diff 1 and p about 2/4096 (only swapping all or none reaches |diff| = 1).
    """
    if len(a) != len(b):
        raise ValueError("paired_compare needs the same cases for both systems")
    n, rng = len(a), random.Random(seed)
    observed = stat(a) - stat(b)
    diffs = []
    for _ in range(resamples):
        idx = [rng.randrange(n) for _ in range(n)]
        diffs.append(stat([a[i] for i in idx]) - stat([b[i] for i in idx]))
    diffs.sort()
    hits = 0
    for _ in range(resamples):
        swap = [rng.random() < 0.5 for _ in range(n)]
        left = [y if s else x for x, y, s in zip(a, b, swap)]
        right = [x if s else y for x, y, s in zip(a, b, swap)]
        hits += abs(stat(left) - stat(right)) >= abs(observed) - 1e-12
    return {"diff": observed, "ci_low": diffs[int(0.025 * resamples)], "ci_high": diffs[int(0.975 * resamples) - 1],
            "p": (hits + 1) / (resamples + 1), "cases": n}  # fmt: skip


def mean(values: list) -> float:
    return sum(values) / len(values) if values else 0.0


def holm(pvalues: list[float]) -> list[float]:
    """Holm step-down adjustment, returned in input order. [0.04, 0.01, 0.03] -> [0.06, 0.03, 0.06]."""
    order = sorted(range(len(pvalues)), key=lambda i: pvalues[i])
    adjusted, running = [0.0] * len(pvalues), 0.0
    for rank, i in enumerate(order):
        running = max(running, min(1.0, (len(pvalues) - rank) * pvalues[i]))
        adjusted[i] = running
    return adjusted
