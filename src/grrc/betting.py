"""Finite-sample confidence bounds by betting (Waudby-Smith and Ramdas, 2023).

A one-sided lower confidence bound on a bounded mean built from a betting
"capital process" and a mixture of e-values. The bound is finite-sample valid
and distribution free; unlike the paired t approximation it is not asymptotic,
and unlike Hoeffding it adapts to the observed spread through the betting
fractions.

Pair matrices use [rival, candidate], matching :mod:`grrc.comparison`. These
functions do not change the model.

Validity for the balanced design. Paired differences from distinct scenarios
are independent but, across the five entry categories, not identically
distributed. For any fixed betting fraction ``lam >= 0`` and observations
rescaled to ``[0, 1]``,

    prod_t (1 + lam (y_t - m)) <= exp(lam * sum_t (y_t - m)),

so its expectation under the hypothesis that the average mean equals ``m`` is at
most ``exp(lam * sum_t (mu_t - m)) = 1`` even when the ``mu_t`` differ. Each
fixed-fraction product is therefore a nonnegative e-value for the average mean,
an average over a fixed grid of fractions is again an e-value, and Markov's
inequality turns ``{m : K_n(m) < 1/alpha}`` into a level ``1 - alpha``
confidence set. This bounds the same average mean that Hoeffding and empirical
Bernstein bound, without an identical-distribution assumption, so all n paired
observations are pooled. The grid is fixed and predictable; only that keeps the
e-value guarantee, so no data-driven per-step fraction is used.
"""
from __future__ import annotations

import numpy as np

from grrc.comparison import paired_moments

# Fixed grid of betting fractions. Any positive grid strictly below one keeps
# every capital factor 1 + lam (y - m) positive for rescaled y and m in [0, 1]
# and preserves the e-value guarantee; the geometric spread lets the mixture
# adapt to low- and high-variance contrasts. Fixed for reproducibility.
LAMBDA_GRID = np.geomspace(1e-3, 0.9, 15)
# Bisection steps in the rescaled mean; 2 ** -30 is far below reported precision.
BISECTION_STEPS = 30


def _mixture_log_capital(y, m, grid):
    """Log of the grid-mixture capital at rescaled mean ``m`` (reduces over axis 0)."""
    components = np.stack([np.log1p(lam * (y - m)).sum(0) for lam in grid])
    peak = components.max(0)
    return peak + np.log(np.exp(components - peak).mean(0))


def betting_lower_bound(d, *, observation_bound, alpha, grid=LAMBDA_GRID):
    """One-sided lower confidence bound on the mean of independent bounded differences.

    ``d`` holds paired differences in ``[-observation_bound, observation_bound]``;
    they need not be identically distributed. Returns the bound in original units.
    """
    d = np.asarray(d, float)
    bound = float(observation_bound)
    grid = np.asarray(grid, float)
    if not np.isfinite(bound) or bound <= 0:
        raise ValueError("observation bound must be finite and positive")
    if not 0 < alpha < 1:
        raise ValueError("alpha must lie strictly in (0, 1)")
    if grid.ndim != 1 or len(grid) < 1 or (grid <= 0).any() or (grid >= 1).any():
        raise ValueError("betting fractions must lie strictly in (0, 1)")
    if d.ndim != 1 or len(d) < 2 or not np.isfinite(d).all() or (np.abs(d) > bound).any():
        raise ValueError("finite paired differences within the observation bound required")
    y = (d + bound) / (2 * bound)
    threshold = np.log(1 / alpha)
    lo, hi = 0.0, 1.0
    for _ in range(BISECTION_STEPS):
        mid = (lo + hi) / 2
        if _mixture_log_capital(y, mid, grid) >= threshold:
            lo = mid
        else:
            hi = mid
    return 2 * bound * lo - bound


def _lower_matrix(a, b, bound, alpha, grid):
    """Vectorized lower-bound matrix in original units, [rival, candidate].

    Rivals are processed in chunks to bound peak memory on wide candidate banks.
    """
    a, b = np.asarray(a, float), np.asarray(b, float)
    n, k = a.shape
    threshold = np.log(1 / alpha)
    lower = np.empty((k, k))
    step = max(1, 4_000_000 // (n * k))  # cap the working array near four million cells
    for start in range(0, k, step):
        rivals = a[:, start:start + step]                        # [n, c]
        # y[t, i, j] rescales the paired difference rivals[t, i] - b[t, j].
        y = (rivals[:, :, None] - b[:, None, :] + bound) / (2 * bound)
        lo = np.zeros(y.shape[1:])
        hi = np.ones(y.shape[1:])
        for _ in range(BISECTION_STEPS):
            mid = (lo + hi) / 2
            above = _mixture_log_capital(y, mid[None], grid) >= threshold
            lo = np.where(above, mid, lo)
            hi = np.where(above, hi, mid)
        lower[start:start + step] = 2 * bound * lo - bound
    return lower


def betting_margins(a, b, *, observation_bound, family_size, alpha=.05, grid=LAMBDA_GRID):
    """Simultaneous one-sided betting margins for every paired contrast.

    ``a`` and ``b`` are aligned scenario-by-candidate matrices bounded in
    ``[0, observation_bound]``; every ordered pair ``a_i - b_j`` is a contrast.
    The returned margin matrix is ``mean - lower``, where ``lower`` is a level
    ``1 - alpha / family_size`` lower confidence bound on the mean difference, so
    the family of one-sided bounds holds simultaneously at ``alpha`` by a union
    bound. The bound is finite-sample valid; its width relative to the other
    families is an empirical outcome, not an assumption.
    """
    a, b = np.asarray(a, float), np.asarray(b, float)
    grid = np.asarray(grid, float)
    mean, _ = paired_moments(a, b)
    if (not np.isfinite(observation_bound) or observation_bound <= 0
            or (a < 0).any() or (b < 0).any()
            or (a > observation_bound).any() or (b > observation_bound).any()
            or not isinstance(family_size, (int, np.integer)) or family_size < 1
            or not 0 < alpha < 1
            or grid.ndim != 1 or len(grid) < 1 or (grid <= 0).any() or (grid >= 1).any()):
        raise ValueError("valid bounded observations and error allocation required")
    lower = _lower_matrix(a, b, float(observation_bound), alpha / family_size, grid)
    return mean, mean - lower
