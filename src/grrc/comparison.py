"""Established concentration bounds and retrospective conditional subsets.

Pair matrices use [rival, candidate]. These functions do not change the model.
"""
from __future__ import annotations

import numpy as np
from scipy.stats import t


def paired_moments(a, b):
    """Mean and unbiased sample variance of every paired a_i - b_j."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    if (a.ndim != 2 or a.shape != b.shape or len(a) < 2
            or not np.isfinite([a, b]).all()):
        raise ValueError("aligned finite matrices with at least two rows required")
    ac, bc = a - a.mean(0), b - b.mean(0)
    variance = ((ac * ac).sum(0)[:, None] + (bc * bc).sum(0)[None, :]
                - 2 * ac.T @ bc) / (len(a) - 1)
    return a.mean(0)[:, None] - b.mean(0)[None, :], np.maximum(variance, 0)


def comparison_margins(a, b, groups, *, observation_bound, family_size, alpha=.05):
    """Three separately allocated one-sided simultaneous margin families.

    a and b are bounded in [0, observation_bound], hence their difference
    has range width 2 * observation_bound. Empirical Bernstein uses Theorem
    11 of Maurer and Pontil (2009), including its finite-sample range term.
    The t family is approximate; zero estimated variance uses Hoeffding.
    """
    a, b = np.asarray(a, float), np.asarray(b, float)
    mean, pooled = paired_moments(a, b)
    if (not np.isfinite(observation_bound) or observation_bound <= 0
            or (a < 0).any() or (b < 0).any()
            or (a > observation_bound).any() or (b > observation_bound).any()
            or not isinstance(family_size, (int, np.integer)) or family_size < 1
            or not 0 < alpha < 1):
        raise ValueError("valid bounded observations and error allocation required")
    groups = [np.asarray(g) for g in groups]
    if (not groups or any(g.ndim != 1 or len(g) < 2 or g.dtype.kind not in "iu"
                         for g in groups)
            or not np.array_equal(np.sort(np.concatenate(groups)), np.arange(len(a)))):
        raise ValueError("strata must partition all observations, with at least two each")
    n, width = len(a), 2 * observation_bound
    h = np.full(mean.shape, width * np.sqrt(np.log(family_size / alpha) / (2 * n)))
    logterm = np.log(2 * family_size / alpha)
    e = np.sqrt(2 * pooled * logterm / n) + 7 * width * logterm / (3 * (n - 1))
    components = np.array([(len(g) / n)**2 * paired_moments(a[g], b[g])[1] / len(g)
                           for g in groups])
    variance = components.sum(0)
    denominator = sum(c*c / (len(g)-1) for c, g in zip(components, groups))
    degrees = np.divide(variance**2, denominator, out=np.full_like(variance, np.inf),
                        where=denominator > 0)
    # isf avoids cancellation in 1 - alpha/K for large contrast families.
    approx = t.isf(alpha / family_size, degrees) * np.sqrt(variance)
    approx = np.where(variance > 0, approx, h)
    return mean, {"hoeffding": h, "empirical_bernstein": e, "paired_t_approx": approx}


def conditional_indices(parameter, groups, high=False):
    """Equal-sized empirical thirds within entry strata, preserving pairing."""
    parameter = np.asarray(parameter, float)
    if parameter.ndim != 1 or not np.isfinite(parameter).all():
        raise ValueError("finite scenario-aligned coefficient required")
    groups = [np.asarray(g) for g in groups]
    if (not groups or any(g.ndim != 1 or len(g) < 6 or g.dtype.kind not in "iu" for g in groups)
            or not np.array_equal(np.sort(np.concatenate(groups)), np.arange(len(parameter)))):
        raise ValueError("strata must partition observations, with at least six each")
    selected = []
    for g in groups:
        order = g[np.argsort(parameter[g], kind="stable")]
        count = len(g) // 3
        selected.append(order[-count:] if high else order[:count])
    return np.concatenate(selected)
