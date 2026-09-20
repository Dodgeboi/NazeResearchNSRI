"""Selection-aware partial-identification bounds from the CIPHER harm corpus.

CIPHER (Straw, Tully, Dameff; CC-BY) codes patient-harm records from real
hospital-ransomware incident reports. It is a convenience sample of *reported*
harms, so a naive share is biased. This module computes, among high-severity
records, each clinical service's share of harm and a partial-identification
interval on that share under bounded per-domain underreporting -- an honest
envelope, not a point estimate. The result feeds the clinical-impact certificate
in :mod:`grrc.hospital_attack_model` as a real-data-derived degradation interval.

It is a pure-array/table module: no plotting, and reading the CSV is its only I/O.
Partial identification is Manski's; the contribution is applying it to a coded
cyber-incident harm corpus and grounding the certificate's weakest input in real
data. Nothing here estimates incidence or a causal effect.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from grrc.enums import Service

# Technical domain -> modelled clinical service (repo's coverage mapping). Domains
# absent here (Hospital Infrastructure, Booking, Admin, Communications, Operating
# Rooms, Telemetry, "All") are the explicit unmodelled residual.
DOMAIN_SERVICE = {
    "Health Records": Service.EHR,
    "Laboratory Systems": Service.LABORATORY,
    "ePrescribing": Service.PHARMACY,
    "Imaging": Service.IMAGING,
}
CLINICAL_SERVICES = (Service.EHR, Service.LABORATORY, Service.PHARMACY, Service.IMAGING)
HIGH_SEVERITY = 7  # impact score >= tau counts as high severity


def load_corpus(path: str | Path) -> pd.DataFrame:
    """Load and lightly clean the CIPHER records (coerce score, fix the coded typo)."""
    df = pd.read_csv(path)
    required = {"Technical Domain", "Clinical Impact Score", "Time Point"}
    if not required <= set(df.columns):
        raise ValueError("not a CIPHER corpus: missing expected columns")
    df = df.copy()
    df["Clinical Impact Score"] = pd.to_numeric(df["Clinical Impact Score"], errors="coerce")
    df["Time Point"] = df["Time Point"].astype(str).str.strip().replace({"Firsy Day": "First Day"})
    df["Technical Domain"] = df["Technical Domain"].astype(str).str.strip()
    return df


def high_severity_counts(df: pd.DataFrame, tau: int = HIGH_SEVERITY):
    """High-severity counts per clinical service, plus the unmodelled residual and total."""
    if not 1 <= tau <= 10:
        raise ValueError("tau must be an impact score in [1, 10]")
    high = df[df["Clinical Impact Score"] >= tau]
    counts = {s: 0 for s in CLINICAL_SERVICES}
    other = 0
    for domain, n in high["Technical Domain"].value_counts().items():
        svc = DOMAIN_SERVICE.get(domain)
        if svc is not None:
            counts[svc] += int(n)
        else:
            other += int(n)
    total = sum(counts.values()) + other
    if total == 0:
        raise ValueError("no high-severity records at this threshold")
    return counts, other, total


def partial_identification_bounds(counts, total, gamma):
    """Per-service share interval under bounded per-domain underreporting.

    ``counts`` maps each clinical service to its observed high-severity count;
    ``total`` is the observed high-severity total across all domains (including the
    unmodelled residual). Under the assumption that any domain's true count is at
    most ``(1 + gamma)`` times its observed count, the true share of service ``s``
    lies in ``[lo, hi]`` with the closed forms below. At ``gamma = 0`` both equal the
    observed share; the interval widens monotonically in ``gamma`` and stays in
    ``[0, 1]``. Returns ``{service: (lo, hi)}``.
    """
    if gamma < 0:
        raise ValueError("gamma must be non-negative")
    if total <= 0:
        raise ValueError("total must be positive")
    bounds = {}
    for svc, n in counts.items():
        n = float(n)
        rest = total - n
        if n < 0 or rest < 0:
            raise ValueError("counts must be non-negative and not exceed the total")
        hi = n * (1 + gamma) / (n * (1 + gamma) + rest) if (n * (1 + gamma) + rest) > 0 else 0.0
        lo = n / (n + (1 + gamma) * rest) if (n + (1 + gamma) * rest) > 0 else 0.0
        bounds[svc] = (lo, hi)
    return bounds


def degradation_bounds(df, gamma, tau: int = HIGH_SEVERITY):
    """Degradation intervals aligned to the certificate's clinical-service order.

    Returns an array ``[service, 2]`` of ``(low, high)`` degradation intervals, one
    row per service in ``CLINICAL_SERVICES`` order, ready for
    ``grrc.hospital_attack_model.certify_clinical``.
    """
    import numpy as np
    counts, _other, total = high_severity_counts(df, tau)
    bounds = partial_identification_bounds(counts, total, gamma)
    return np.array([bounds[s] for s in CLINICAL_SERVICES], float)


def time_profile(df):
    """Fraction of records at each harm-onset time point (observed, not bounded)."""
    order = ["First Hour", "First Day", "First Week", "Week 2", "First Month"]
    counts = df["Time Point"].value_counts()
    total = int(counts.reindex(order).fillna(0).sum())
    return {t: (float(counts.get(t, 0)) / total if total else 0.0) for t in order}
