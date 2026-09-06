"""Shared-price retention and a conservative simultaneous sampling screen.

These are applications of linear support functions and Hoeffding's inequality,
not new optimization or concentration theorems. Arrays use [rival, candidate].
"""
from __future__ import annotations

import numpy as np

from .defenses import (BACKUP_ORDER, SEGMENTATION_ORDER, PATCH_LADDER,
    _ladder_index, boosted_patch_coverage, upgrade_only)
from .enums import BackupStrategy, SegmentationLevel

TARIFF_KEYS = (
    "basic_segmentation", "least_privilege_segmentation", "patch_level_upgrade",
    "detection_improvement", "rapid_isolation", "periodic_backups",
    "protected_backups", "identity_controls",
)
ORDERED_PAIRS = ((0, 1), (5, 6))


def portfolio_features(portfolio, profile) -> np.ndarray:
    """Integer coefficients in the original upgrade-only price function."""
    a = np.zeros(8)
    for baseline, target, ladder, positions in [
        (SegmentationLevel(profile.base_segmentation), portfolio.segmentation,
         SEGMENTATION_ORDER, (0, 1)),
        (BackupStrategy(profile.backup_strategy), portfolio.backup_override,
         BACKUP_ORDER, (5, 6)),
    ]:
        final = upgrade_only(ladder, baseline, target)
        for level, j in zip(ladder[1:], positions):
            a[j] = int(final == level) - int(baseline == level)
    target = portfolio.patch_coverage_override
    if target is None:
        target = boosted_patch_coverage(profile.patch_coverage,
                                       portfolio.patch_boost_levels)
    a[2] = max(0, _ladder_index(PATCH_LADDER, target)
                  - _ladder_index(PATCH_LADDER, profile.patch_coverage))
    a[3:5] = portfolio.detection_improvement, portfolio.rapid_isolation
    a[7] = portfolio.identity_controls
    return a


def ordered_rectangle_vertices(lower, upper, minimum_gap=0) -> np.ndarray:
    """Vertices of a two-dimensional box intersected with x + gap <= y."""
    lower, upper = np.asarray(lower, float), np.asarray(upper, float)
    if (lower.shape != (2,) or upper.shape != (2,)
            or not np.isfinite([lower, upper]).all() or (lower > upper).any()
            or not np.isfinite(minimum_gap) or minimum_gap < 0):
        raise ValueError("finite ordered two-dimensional bounds required")
    lower = lower - [0, minimum_gap]
    upper = upper - [0, minimum_gap]
    vertices = [(x, y) for x in (lower[0], upper[0])
                for y in (lower[1], upper[1]) if x <= y]
    left, right = max(lower), min(upper)
    if left <= right:
        vertices.extend([(left, left), (right, right)])
    if not vertices:
        raise ValueError("empty ordered rectangle")
    return np.unique(vertices, axis=0) + [0, minimum_gap]


def minimum_tariff_difference(coefficients, nominal, radius, preserve_gaps=False) -> np.ndarray:
    """Exact linear minimum over a box with two monotone price ladders."""
    a, t = np.asarray(coefficients, float), np.asarray(nominal, float)
    if (a.shape[-1:] != (8,) or t.shape != (8,)
            or not np.isfinite(a).all() or not np.isfinite(t).all()
            or (t <= 0).any() or not 0 <= radius < 1):
        raise ValueError("eight finite coefficients, positive tariffs, 0 <= radius < 1")
    if any(t[i] > t[j] for i, j in ORDERED_PAIRS):
        raise ValueError("nominal price ladders must be monotone")
    lower, upper = t * (1 - radius), t * (1 + radius)
    result = np.zeros(a.shape[:-1])
    for i, j in ORDERED_PAIRS:
        gap = (1-radius) * (t[j]-t[i]) if preserve_gaps else 0
        vertices = ordered_rectangle_vertices(lower[[i, j]], upper[[i, j]], gap)
        result += np.min(a[..., [i, j]] @ vertices.T, axis=-1)
    for j in (2, 3, 4, 7):
        result += a[..., j] * np.where(a[..., j] >= 0, lower[j], upper[j])
    return result


def tariff_pair_minima(features, costs, burdens, radius, preserve_gaps=False) -> np.ndarray:
    """Two independent price families, each shared across all candidates."""
    features = np.asarray(features, float)
    difference = features[:, None, :] - features[None, :, :]
    # Integer features and declared decimal radii make these decimal quantities.
    # Round only the price calculation to remove floating cancellation at ties.
    return np.round(np.stack([
        minimum_tariff_difference(difference, [t[k] for k in TARIFF_KEYS], radius,
                                 preserve_gaps)
        for t in (costs, burdens)], axis=-1), 12)


def guaranteed_with_shared_tariffs(lower, upper, tariff_minima) -> np.ndarray:
    """Universal retention with independent outcome boxes and shared tariffs.

    For a fixed rival, all coordinate minima can occur together: outcomes are
    independent box coordinates, and cost and burden are separate polytopes.
    This proves exact guaranteed retention, but NOT an exact possible set.
    """
    lower, upper = np.asarray(lower, float), np.asarray(upper, float)
    prices = np.asarray(tariff_minima, float)
    if (lower.ndim != 2 or lower.shape != upper.shape
            or prices.shape != (len(lower), len(lower), 2)
            or not np.isfinite([lower, upper]).all()
            or not np.isfinite(prices).all() or (lower > upper).any()):
        raise ValueError("aligned finite outcome bounds and pairwise prices required")
    differences = lower[:, None, :] - upper[None, :, :]
    weak = (differences <= 0).all(axis=-1) & (prices <= 0).all(axis=-1)
    strict = (differences < 0).any(axis=-1) | (prices < 0).any(axis=-1)
    possible_rival = weak & strict
    np.fill_diagonal(possible_rival, False)
    return ~possible_rival.any(axis=0)


def hoeffding_lower_differences(loss, outage_low, outage_high, nonrecovery,
                               *, loss_bound, family_size, alpha):
    """Simultaneous one-sided bounds for three paired mean differences.

    Fixed-stratum independent, nonidentically distributed draws are permitted.
    The family size must include every ordered comparison and all three means.
    Tail means are deliberately excluded because they are nonlinear statistics.
    """
    arrays = [np.asarray(a, float) for a in
              (loss, outage_low, outage_high, nonrecovery)]
    if (arrays[0].ndim != 2 or arrays[0].shape[0] < 1
            or any(a.shape != arrays[0].shape for a in arrays)
            or not all(np.isfinite(a).all() for a in arrays)
            or not np.isfinite(loss_bound) or loss_bound <= 0
            or not 0 < alpha < 1 or family_size < 1):
        raise ValueError("finite paired observations and valid bound parameters required")
    loss, low, high, non = arrays
    if ((loss < 0).any() or (loss > loss_bound + 1e-9).any()
            or any(((a < 0) | (a > 1)).any() for a in (low, high, non))
            or (low > high).any()):
        raise ValueError("observations violate declared bounded nested domains")
    means = np.stack([
        loss.mean(0)[:, None] - loss.mean(0)[None, :],
        low.mean(0)[:, None] - high.mean(0)[None, :],
        non.mean(0)[:, None] - non.mean(0)[None, :]], axis=-1)
    radius = 2 * np.array([loss_bound, 1, 1]) * np.sqrt(
        np.log(family_size / alpha) / (2 * loss.shape[0]))
    return means - radius, radius


def sufficient_population_retention(lower_differences, tariff_minima):
    """Require a strictly worse rival coordinate, allowing arbitrary tail loss.

    A tie in all screened coordinates cannot certify retention: the omitted
    tail coordinate might still let that rival dominate.
    """
    lower = np.asarray(lower_differences, float)
    prices = np.asarray(tariff_minima, float)
    if (lower.ndim != 3 or lower.shape[0] != lower.shape[1]
            or prices.shape != (*lower.shape[:2], 2)
            or not np.isfinite(lower).all() or not np.isfinite(prices).all()):
        raise ValueError("finite square pairwise lower bounds required")
    cannot_rule_out = (lower <= 0).all(axis=-1) & (prices <= 0).all(axis=-1)
    np.fill_diagonal(cannot_rule_out, False)
    return ~cannot_rule_out.any(axis=0)
