"""Evidence-anchored, ATT&CK-driven hospital clinical-impact model.

This is the "better synthetic hospital": instead of an abstract epidemic-spread
constant, its attack surface is the real MITRE ATT&CK kill chain
(:mod:`grrc.attack_graph`), and its damage is patient-facing clinical-service
outage, not a count of compromised hosts. It is still synthetic -- real hospital
maps and per-incident telemetry are not public -- but every parameter is an
interval anchored to a published figure (see study/EVIDENCE_ANCHORED_HOSPITAL.md),
never a point.

Composition. A control portfolio (a set of ATT&CK mitigations) reduces technique
success along the kill chain. ``impact_reachability`` is the probability the
adversary completes the chain to the ransomware impact tactic (product of
usage-weighted stage successes, with the impact stage taken over the impact
techniques that degrade clinical care). A clinical service then suffers a
sustained outage with a service-specific degradation probability given impact.
Every quantity is coordinatewise monotone in the model parameters, so the
control-adequacy certificate in :mod:`grrc.control_certificate` extends to
clinical outcomes by evaluating the interval corners.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from grrc.attack_graph import AttackGraph, RANSOMWARE_STAGES
from grrc.enums import CLINICAL_SERVICES, Service

# ATT&CK impact techniques that degrade clinical care, and the effect modelled.
IMPACT_TECHNIQUES = ("T1486", "T1490", "T1489", "T1485")

# Probability an impact-capable intrusion degrades each clinical service, as an
# interval anchored to Neprash 2022 (44% of attacks disrupt care) and
# McGlave/Neprash 2026 (17-26% volume drop). Service-specific, documented.
SERVICE_DEGRADATION = {
    Service.EHR: (0.30, 0.44),
    Service.LABORATORY: (0.20, 0.40),
    Service.PHARMACY: (0.20, 0.40),
    Service.IMAGING: (0.17, 0.35),
}


@dataclass(frozen=True)
class HospitalModel:
    """Precomputed structure for the clinical-impact certificate."""
    graph: AttackGraph
    stage_index: list          # the eleven non-impact stages (technique indices)
    impact_members: np.ndarray  # indices of the clinical-impact techniques
    services: tuple             # clinical services, fixed order
    degradation: np.ndarray     # [service, 2] (low, high) degradation intervals


def build_model(graph: AttackGraph) -> HospitalModel:
    stages = [s for s in RANSOMWARE_STAGES if s != "impact"]
    stage_index = [graph.stage_members[s] for s in stages]
    impact_pool = set(graph.stage_members["impact"].tolist())
    members = []
    for tid in IMPACT_TECHNIQUES:
        if tid in graph.techniques:
            idx = graph.techniques.index(tid)
            if idx in impact_pool:
                members.append(idx)
    if not members:
        raise ValueError("no clinical-impact techniques present in the graph")
    services = CLINICAL_SERVICES
    degradation = np.array([SERVICE_DEGRADATION[s] for s in services], float)
    return HospitalModel(graph=graph, stage_index=stage_index,
                         impact_members=np.array(sorted(members), int),
                         services=services, degradation=degradation)


def _residual(portfolios, base, effectiveness, graph):
    """Residual per-attempt success per (portfolio, technique)."""
    log_factor = graph.coverage * np.log1p(-effectiveness)[None, :]
    return base * np.exp(portfolios @ log_factor.T)


def impact_reachability(portfolios, base, effectiveness, model: HospitalModel):
    """Probability of completing the kill chain to the clinical-impact tactic."""
    portfolios = np.atleast_2d(np.asarray(portfolios, bool))
    effectiveness = np.asarray(effectiveness, float)
    if not 0 < base <= 1 or (effectiveness < 0).any() or (effectiveness >= 1).any():
        raise ValueError("base in (0,1] and effectiveness in [0,1) required")
    residual = _residual(portfolios, float(base), effectiveness, model.graph)
    reach = np.ones(residual.shape[0])
    for members in model.stage_index:
        w = model.graph.usage[members] + 1.0
        reach = reach * (residual[:, members] @ w) / w.sum()
    w = model.graph.usage[model.impact_members] + 1.0
    reach = reach * (residual[:, model.impact_members] @ w) / w.sum()
    return reach


def service_outage(portfolios, base, effectiveness, degradation, model: HospitalModel):
    """P(sustained outage) per (portfolio, clinical service)."""
    reach = impact_reachability(portfolios, base, effectiveness, model)[:, None]
    degradation = np.asarray(degradation, float)
    if degradation.shape != (len(model.services),) or (degradation < 0).any() or (degradation > 1).any():
        raise ValueError("degradation must be one probability per clinical service in [0,1]")
    return reach * degradation[None, :]


def certify_clinical(portfolios, base_bounds, eff_bounds, degradation_bounds, model, epsilon):
    """Necessary/possible clinical-outage certificate.

    Returns ``(worst, best, guaranteed, possible)`` where worst/best are
    [portfolio, service+1]: one column per clinical service plus a final
    union-bound column for "any clinical service" (sum of per-service outage
    probabilities, a distribution-free upper bound on P(>=1 outage)). A portfolio
    is guaranteed adequate when every worst-corner column is <= epsilon.
    Reachability, outage and the union bound are all monotone -- increasing in
    base and degradation, decreasing in effectiveness -- so the extremes sit at
    the interval corners.
    """
    eff_bounds = np.asarray(eff_bounds, float)
    deg_bounds = np.asarray(degradation_bounds, float)
    base_low, base_high = float(base_bounds[0]), float(base_bounds[1])
    if not 0 < base_low <= base_high <= 1 or (eff_bounds[:, 0] > eff_bounds[:, 1]).any():
        raise ValueError("degenerate base or effectiveness interval")
    if deg_bounds.shape != (len(model.services), 2) or (deg_bounds[:, 0] > deg_bounds[:, 1]).any():
        raise ValueError("degradation bounds must be [service, 2] and ordered")
    if not 0 < epsilon < 1:
        raise ValueError("epsilon must lie strictly in (0, 1)")

    def corner(base, eff, deg):
        per = service_outage(portfolios, base, eff, deg, model)
        return np.column_stack([per, per.sum(axis=1)])

    worst = corner(base_high, eff_bounds[:, 0], deg_bounds[:, 1])
    best = corner(base_low, eff_bounds[:, 1], deg_bounds[:, 0])
    if (best > worst + 1e-12).any():
        raise AssertionError("best corner must not exceed worst corner")
    guaranteed = (worst <= epsilon).all(axis=1)
    possible = (best <= epsilon).all(axis=1)
    return worst, best, guaranteed, possible
