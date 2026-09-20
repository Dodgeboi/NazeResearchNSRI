"""Validate an ATT&CK-based clinical-impact model against the real CIPHER harm corpus.

To our knowledge this is the first calibration of a predicted per-clinical-service
impact profile against a coded patient-harm corpus. The predicted profiles are
built without CIPHER (CIPHER is held out as external ground truth) to avoid
training-on-test: a ``uniform`` ATT&CK null, and the model's own ``assumed``
degradation (Neprash-anchored, not CIPHER). The comparison uses a total-variation
distance, an exact Monte-Carlo multinomial goodness-of-fit test, and a
partial-identification-robust "reconciling gamma" -- the minimum bounded
underreporting that would make the model consistent with the observed shares.

These are standard tools (TV distance, multinomial GoF, Manski-style bounds); the
contribution is the validation itself, honestly scoped for a convenience sample.
Pure functions, no I/O.
"""
from __future__ import annotations

import numpy as np
from scipy.stats import chisquare

from grrc.cipher_bounds import (high_severity_counts, partial_identification_bounds,
                                CLINICAL_SERVICES, HIGH_SEVERITY)


def predicted_profiles(model):
    """CIPHER-independent predicted profiles over the four clinical services.

    Returns ``{"uniform": array, "assumed": array}`` in CLINICAL_SERVICES order,
    each summing to one. ``uniform`` is the ATT&CK null; ``assumed`` normalises the
    model's Neprash-anchored per-service degradation (not derived from CIPHER).
    """
    n = len(model.services)
    uniform = np.full(n, 1.0 / n)
    deg = model.degradation.mean(axis=1)  # midpoint of each service's degradation interval
    if deg.sum() <= 0:
        raise ValueError("degradation midpoints must be positive")
    return {"uniform": uniform, "assumed": deg / deg.sum()}


def observed_profile(df, tau: int = HIGH_SEVERITY):
    """CIPHER observed high-severity counts and normalised profile over the services.

    Returns ``(counts_array, profile_array, other, total)`` in CLINICAL_SERVICES
    order; ``profile`` is conditioned on the four modelled services (residual
    excluded but returned as ``other``).
    """
    counts, other, total = high_severity_counts(df, tau)
    arr = np.array([counts[s] for s in CLINICAL_SERVICES], float)
    if arr.sum() <= 0:
        raise ValueError("no high-severity records among the modelled services")
    return arr, arr / arr.sum(), other, total


def total_variation(p, q):
    """Total-variation distance between two probability vectors."""
    p, q = np.asarray(p, float), np.asarray(q, float)
    if p.shape != q.shape or (p < 0).any() or (q < 0).any():
        raise ValueError("p and q must be non-negative and the same shape")
    if abs(p.sum() - 1) > 1e-6 or abs(q.sum() - 1) > 1e-6:
        raise ValueError("p and q must each sum to one")
    return 0.5 * float(np.abs(p - q).sum())


def multinomial_gof(counts, profile, draws: int = 20000, seed: int = 20260920):
    """Exact Monte-Carlo multinomial goodness-of-fit p-value plus the chi-square one.

    H0: ``counts`` are drawn from ``profile`` (a distribution over the same cells).
    The statistic is Pearson's chi-square; the p-value is the fraction of
    ``draws`` multinomial samples (at the observed total) with a statistic at least
    as large, so it is valid for small counts where the asymptotic chi-square is not.
    Returns ``(mc_pvalue, chi2_pvalue, statistic)``.
    """
    counts = np.asarray(counts, float)
    profile = np.asarray(profile, float)
    n = counts.sum()
    if counts.ndim != 1 or (counts < 0).any() or n <= 0:
        raise ValueError("counts must be a non-negative vector with positive total")
    if profile.shape != counts.shape or (profile < 0).any() or abs(profile.sum() - 1) > 1e-6:
        raise ValueError("profile must be a distribution over the same cells")
    expected = n * profile
    if (expected <= 0).any():
        raise ValueError("profile must put positive mass on every observed cell")

    def stat(obs):
        return float(((obs - expected) ** 2 / expected).sum())

    observed_stat = stat(counts)
    rng = np.random.default_rng(seed)
    sims = rng.multinomial(int(round(n)), profile, size=draws).astype(float)
    sim_stats = ((sims - expected) ** 2 / expected).sum(axis=1)
    mc_p = float((sim_stats >= observed_stat - 1e-12).mean())
    chi2_p = float(chisquare(counts, expected).pvalue)
    return mc_p, chi2_p, observed_stat


def reconciling_gamma(counts, total, profile, grid=None):
    """Minimum bounded-underreporting gamma reconciling the profile with CIPHER shares.

    ``counts`` are the observed high-severity counts per service, ``total`` the
    overall high-severity total (including the unmodelled residual), ``profile`` the
    predicted distribution over services conditioned on the four services. For each
    gamma the observed *unconditional* share of each service lies in a
    partial-identification interval; we renormalise the predicted (conditional)
    profile onto the observed conditional mass and ask whether it fits within the
    conditional envelope. Returns the smallest gamma on ``grid`` at which every
    predicted service share lies inside its interval, or ``inf`` if none does.
    """
    counts = {s: float(c) for s, c in zip(CLINICAL_SERVICES, counts)}
    conditional_total = sum(counts.values())
    if conditional_total <= 0 or total <= 0:
        raise ValueError("counts and total must be positive")
    profile = np.asarray(profile, float)
    if grid is None:
        grid = np.concatenate([[0.0], np.linspace(0.05, 5.0, 100)])
    for gamma in grid:
        bounds = partial_identification_bounds(counts, conditional_total, float(gamma))
        ok = True
        for i, s in enumerate(CLINICAL_SERVICES):
            lo, hi = bounds[s]
            if not (lo - 1e-9 <= profile[i] <= hi + 1e-9):
                ok = False
                break
        if ok:
            return float(gamma)
    return float("inf")
