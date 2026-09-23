"""An adaptive (worst-case) adversary for the cyber range.

The certificate's default reachability models a *typical* adversary: each kill-chain
stage succeeds with the usage-weighted mean residual over its techniques. An
**adaptive** adversary instead best-responds to the current defense by routing
through the *easiest uncovered* technique each stage -- stage success is the ``max``
residual over the stage's techniques (and over the clinical-impact techniques). This
is the closed-form best response, so no iteration is needed: as the defender covers
the easiest path, the adversary's max simply shifts to the next-easiest.

Adaptive reachability dominates the typical one pointwise (a max is at least a mean),
so defending against it is at least as hard. It stays coordinatewise monotone --
adding a mitigation only lowers residuals, so the max only drops; it rises in the
base rate and falls in effectiveness -- so the interval-corner certificate is still
exact (worst corner: base high, effectiveness low). These functions mirror the corner
logic of :func:`grrc.control_certificate.certify_portfolios` and
:func:`grrc.hospital_attack_model.certify_catastrophic` but with ``max`` aggregation;
the audited certificate modules are left untouched. Pure, no I/O.
"""
from __future__ import annotations

import numpy as np

from grrc.joint_bounds import sharp_k_of_n_upper


def _residual(portfolios, base, eff, graph):
    portfolios = np.atleast_2d(np.asarray(portfolios, bool))
    eff = np.asarray(eff, float)
    if not 0 < base <= 1 or (eff < 0).any() or (eff >= 1).any():
        raise ValueError("base in (0,1] and effectiveness in [0,1) required")
    if portfolios.shape[1] != graph.coverage.shape[1] or eff.shape != (graph.coverage.shape[1],):
        raise ValueError("portfolio and effectiveness widths must match the mitigation count")
    log_factor = graph.coverage * np.log1p(-eff)[None, :]        # [T, M]
    return base * np.exp(portfolios @ log_factor.T)              # [P, T]


def adaptive_control_reachability(portfolios, base, eff, model):
    """Adaptive-adversary reachability to the impact objective T1486 (max per stage)."""
    res = _residual(portfolios, float(base), eff, model.graph)
    reach = np.ones(res.shape[0])
    for members in model.stage_index:                           # non-impact stages
        reach = reach * res[:, members].max(axis=1)
    return reach * res[:, model.graph.impact_index]             # objective technique alone


def adaptive_impact_reachability(portfolios, base, eff, model):
    """Adaptive-adversary reachability to the clinical-impact stage (max everywhere)."""
    res = _residual(portfolios, float(base), eff, model.graph)
    reach = np.ones(res.shape[0])
    for members in model.stage_index:
        reach = reach * res[:, members].max(axis=1)
    return reach * res[:, model.impact_members].max(axis=1)


def _corners(base_bounds, eff_bounds):
    eff_bounds = np.asarray(eff_bounds, float)
    base_low, base_high = float(base_bounds[0]), float(base_bounds[1])
    if eff_bounds.ndim != 2 or eff_bounds.shape[1] != 2:
        raise ValueError("eff_bounds must be [mitigation, 2]")
    if not 0 < base_low <= base_high <= 1 or (eff_bounds[:, 0] > eff_bounds[:, 1]).any():
        raise ValueError("degenerate base or effectiveness interval")
    return base_low, base_high, eff_bounds


def adaptive_certify_control(portfolios, base_bounds, eff_bounds, model, epsilon):
    """Necessary/possible control-adequacy certificate under the adaptive adversary."""
    base_low, base_high, eff_bounds = _corners(base_bounds, eff_bounds)
    if not 0 < epsilon < 1:
        raise ValueError("epsilon must lie strictly in (0, 1)")
    worst = adaptive_control_reachability(portfolios, base_high, eff_bounds[:, 0], model)
    best = adaptive_control_reachability(portfolios, base_low, eff_bounds[:, 1], model)
    if (best > worst + 1e-12).any():
        raise AssertionError("best corner must not exceed worst corner")
    return worst, best, worst <= epsilon, best <= epsilon


def adaptive_floor(model, base, eff):
    """The reachability floor: the minimum adaptive reachability over all portfolios.

    Adaptive reachability is monotone non-increasing in the portfolio (adding a
    mitigation only lowers residuals, so each stage's max only drops), so the *full*
    portfolio -- every mitigation deployed -- attains the global minimum. Returns
    ``(control_floor, clinical_floor)``: the floor for reachability to T1486 and for
    the clinical-impact stage. No portfolio can drive reachability below this, so a
    stage with a technique that has no mitigation floors it at the base rate.
    """
    full = np.ones(model.graph.n_mitigations, bool)[None, :]
    control = float(adaptive_control_reachability(full, base, eff, model)[0])
    clinical = float(adaptive_impact_reachability(full, base, eff, model)[0])
    return control, clinical


def stage_coverage_gaps(model, examples=3):
    """Per stage, the techniques MITRE lists no mitigation for -- the uncoverable frontier.

    Returns a list of dicts (one per non-impact stage plus the impact stage) with the
    stage name, its technique count, the count with zero mitigation coverage, and up to
    ``examples`` example uncoverable technique ids. A stage with any uncoverable
    technique cannot have its adaptive max residual reduced below the base rate by any
    portfolio, which is what sets the reachability floor.
    """
    from grrc.attack_graph import RANSOMWARE_STAGES
    graph = model.graph
    covered = graph.coverage.sum(axis=1)                    # mitigations per technique
    names = [s for s in RANSOMWARE_STAGES if s != "impact"]
    rows = []
    for name, members in zip(names, model.stage_index):
        members = np.asarray(members, int)
        gap = members[covered[members] == 0]
        rows.append(dict(stage=name, techniques=int(len(members)),
                         uncoverable=int(len(gap)),
                         examples="+".join(graph.techniques[t] for t in gap[:examples])))
    impact = np.asarray(model.impact_members, int)
    igap = impact[covered[impact] == 0]
    rows.append(dict(stage="impact", techniques=int(len(impact)),
                     uncoverable=int(len(igap)),
                     examples="+".join(graph.techniques[t] for t in igap[:examples])))
    return rows


def adaptive_certify_catastrophic(portfolios, base_bounds, eff_bounds, deg_bounds,
                                  model, k, epsilon):
    """Catastrophic k-of-n clinical certificate under the adaptive adversary."""
    base_low, base_high, eff_bounds = _corners(base_bounds, eff_bounds)
    deg_bounds = np.asarray(deg_bounds, float)
    n_services = len(model.services)
    if deg_bounds.shape != (n_services, 2) or (deg_bounds[:, 0] > deg_bounds[:, 1]).any():
        raise ValueError("degradation bounds must be [service, 2] and ordered")
    if not isinstance(k, (int, np.integer)) or not 1 <= k <= n_services:
        raise ValueError("k must be an integer in [1, number of clinical services]")
    if not 0 < epsilon < 1:
        raise ValueError("epsilon must lie strictly in (0, 1)")

    def corner(base, eff, deg):
        reach = adaptive_impact_reachability(portfolios, base, eff, model)      # [P]
        marg = reach[:, None] * deg[None, :]                                    # [P, service]
        return np.array([sharp_k_of_n_upper(row, k) for row in marg])

    worst = corner(base_high, eff_bounds[:, 0], deg_bounds[:, 1])
    best = corner(base_low, eff_bounds[:, 1], deg_bounds[:, 0])
    if (best > worst + 1e-9).any():
        raise AssertionError("best corner must not exceed worst corner")
    return worst, best, worst <= epsilon, best <= epsilon
