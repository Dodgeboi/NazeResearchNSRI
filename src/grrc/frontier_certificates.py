"""Exact necessary/possible efficiency for a finite Cartesian objective box.

Every objective is minimized. The interval product allows objective values
to vary independently across candidates and dimensions. Bounds can describe
a conservative envelope of a smaller, correlated specification set.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class FrontierCertificate:
    guaranteed: np.ndarray
    possible: np.ndarray
    possible_dominator: np.ndarray
    necessary_dominator: np.ndarray


def certify_frontier(lower: np.ndarray, upper: np.ndarray) -> FrontierCertificate:
    lower, upper = np.asarray(lower, dtype=float), np.asarray(upper, dtype=float)
    if lower.ndim != 2 or lower.shape != upper.shape or min(lower.shape) < 1:
        raise ValueError("matching nonempty candidate-by-objective matrices required")
    if not np.isfinite(lower).all() or not np.isfinite(upper).all():
        raise ValueError("bounds must be finite")
    if (lower > upper).any():
        raise ValueError("lower bound exceeds upper bound")
    n = len(lower)
    possible_dominator = np.full(n, -1, dtype=int)
    necessary_dominator = np.full(n, -1, dtype=int)
    for x in range(n):
        # Adverse configuration for x: x at upper, every competitor at lower.
        can_dominate = (lower <= upper[x]).all(axis=1) & (lower < upper[x]).any(axis=1)
        can_dominate[x] = False
        witness = np.flatnonzero(can_dominate)
        if len(witness):
            possible_dominator[x] = witness[0]
        # Favorable configuration for x: x at lower, every competitor at upper.
        must_dominate = (upper <= lower[x]).all(axis=1) & (upper < lower[x]).any(axis=1)
        must_dominate[x] = False
        witness = np.flatnonzero(must_dominate)
        if len(witness):
            necessary_dominator[x] = witness[0]
    return FrontierCertificate(possible_dominator < 0, necessary_dominator < 0,
                               possible_dominator, necessary_dominator)


def two_objective_frontier(values: np.ndarray) -> np.ndarray:
    """Independent sorting oracle for two objectives, retaining exact ties.

This uses lexicographic sorting and a running minimum, not pairwise corner
comparisons. Equal first-objective groups are processed together.
"""
    values = np.asarray(values, dtype=float)
    if values.ndim != 2 or values.shape[1] != 2 or not np.isfinite(values).all():
        raise ValueError("finite two-objective matrix required")
    efficient = np.zeros(len(values), dtype=bool)
    order = np.lexsort((values[:, 1], values[:, 0]))
    best = np.inf
    start = 0
    while start < len(order):
        stop = start + 1
        while stop < len(order) and values[order[stop], 0] == values[order[start], 0]:
            stop += 1
        group = order[start:stop]
        minimum = values[group, 1].min()
        if minimum < best:
            efficient[group[values[group, 1] == minimum]] = True
        best = min(best, minimum)
        start = stop
    return efficient
