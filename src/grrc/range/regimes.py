"""Threat regimes for the defender cyber range -- the adaptive-evaluation axis.

A :class:`Regime` fixes everything the certificate needs to score a portfolio: the
base-rate and per-mitigation effectiveness interval bounds, the per-service
degradation interval bounds, the adequacy level ``epsilon``, and the catastrophic
threshold ``k``. :func:`default_regimes` builds the sweep the benchmark scores every
defender across -- assumed vs real (CIPHER-derived) degradation, an ``epsilon`` grid,
and ``k = 1..n`` -- so results report cross-regime robustness rather than one number.

The base rate, effectiveness prior and the one evidence-tightened control (MFA,
M1032) mirror ``scripts/analyze_control_certificate.py`` /
``analyze_catastrophic_certificate.py`` exactly, so this study is consistent with
the certificate papers it builds on. No new data; values are analyst-prior
intervals anchored to published figures, never incident measurements.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

BASE_BOUNDS = (0.5, 0.9)
DEFAULT_EFF = (0.20, 0.70)
# The single documented evidence-tightened interval: multi-factor authentication.
EVIDENCE_EFF = {"M1032": (0.85, 0.99)}
EPSILONS = (0.10, 0.05, 0.01)


def effectiveness_bounds(mitigations, prior=DEFAULT_EFF):
    """Per-mitigation ``(low, high)`` effectiveness intervals aligned to ``mitigations``.

    Every mitigation gets ``prior``; the evidence-tightened controls override it only
    when the default prior is in force (matching the certificate analyses).
    """
    bounds = np.tile(prior, (len(mitigations), 1)).astype(float)
    index = {m: i for i, m in enumerate(mitigations)}
    if tuple(prior) == DEFAULT_EFF:
        for mid, interval in EVIDENCE_EFF.items():
            if mid in index:
                bounds[index[mid]] = interval
    return bounds


ADVERSARIES = ("typical", "adaptive")


@dataclass(frozen=True)
class Regime:
    """One threat configuration the range scores defenders against."""
    label: str
    adversary: str               # "typical" (usage-weighted mean) | "adaptive" (max)
    degradation_source: str      # "assumed" | "cipher_gamma1"
    base_bounds: tuple
    eff_bounds: np.ndarray        # [mitigation, 2]
    deg_bounds: np.ndarray        # [service, 2]
    epsilon: float
    k: int


def default_regimes(model, cipher_df=None, epsilons=EPSILONS, ks=None,
                    adversaries=ADVERSARIES):
    """Build the adaptive sweep: {adversary} x {degradation source} x {epsilon} x {k}.

    ``model`` is a :class:`grrc.hospital_attack_model.HospitalModel`. The ``typical``
    adversary is the certificate's usage-weighted-mean reachability; the ``adaptive``
    one best-responds through the easiest uncovered technique (:mod:`grrc.range.adversary`).
    The assumed degradation is ``model.degradation``; the real one is CIPHER-derived at
    gamma=1 (only when ``cipher_df`` is given). ``ks`` defaults to ``1..n_services``.
    """
    eff = effectiveness_bounds(model.graph.mitigations)
    n_services = len(model.services)
    ks = tuple(range(1, n_services + 1)) if ks is None else tuple(ks)
    degradations = {"assumed": np.asarray(model.degradation, float)}
    if cipher_df is not None:
        from grrc.cipher_bounds import degradation_bounds
        degradations["cipher_gamma1"] = degradation_bounds(cipher_df, 1.0)
    regimes = []
    for adversary in adversaries:
        for source, deg in degradations.items():
            for eps in epsilons:
                for k in ks:
                    regimes.append(Regime(
                        label=f"{adversary}|{source}|eps={eps:.2f}|k={k}",
                        adversary=adversary, degradation_source=source,
                        base_bounds=BASE_BOUNDS, eff_bounds=eff,
                        deg_bounds=np.asarray(deg, float),
                        epsilon=float(eps), k=int(k)))
    return regimes
