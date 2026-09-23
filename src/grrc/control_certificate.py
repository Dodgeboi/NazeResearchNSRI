"""Distribution-free control-adequacy certificate on the ATT&CK kill chain.

A defensive *control portfolio* is a set of ATT&CK mitigations. Given the real
technique/mitigation coverage from :mod:`grrc.attack_graph`, this module scores
how far a portfolio drives down the adversary's reachability to the ransomware
impact objective, and certifies adequacy under bounded uncertainty in the model
parameters.

Reachability model. Each technique has a residual per-attempt success
``base * prod_{m in portfolio, m mitigates t} (1 - eff_m)``. A stage's success is
the usage-weighted mean residual over its techniques (a "typical adversary": a
prevalent technique matters more than an obscure one, and partial coverage helps
proportionally, unlike a hard easiest-path max). The impact stage uses the
objective technique alone. Reachability ``R`` is the product of stage successes.

``R`` is coordinatewise monotone -- increasing in every ``base`` and decreasing in
every ``eff_m`` -- so, exactly as in :mod:`grrc.frontier_certificates`, its extremes
over an interval uncertainty set are attained at the box corners:
``worst`` (base high, effectiveness low) and ``best`` (base low, effectiveness high).
A portfolio is ``guaranteed`` adequate at level ``epsilon`` when even the worst
corner keeps ``R <= epsilon``, and only ``possible`` when merely the best corner does.
Interval widths on ``eff_m`` are inputs; where incident counts exist they can be
turned into finite-sample intervals with :mod:`grrc.betting`. Only the certificate's
validity given the intervals is asserted; which portfolios certify is reported.
"""
from __future__ import annotations

import numpy as np


def _validate(coverage, usage, stage_index, impact_index):
    coverage = np.asarray(coverage, bool)
    usage = np.asarray(usage, float)
    if coverage.ndim != 2 or usage.ndim != 1 or len(usage) != coverage.shape[0]:
        raise ValueError("coverage must be [technique, mitigation] with matching usage")
    if (usage < 0).any() or not np.isfinite(usage).all():
        raise ValueError("usage weights must be finite and non-negative")
    n_tech = coverage.shape[0]
    if not stage_index or any(len(s) == 0 for s in stage_index):
        raise ValueError("every stage must have at least one technique")
    flat = np.concatenate([np.asarray(s, int) for s in stage_index])
    if flat.min() < 0 or flat.max() >= n_tech:
        raise ValueError("stage indices out of range")
    if not 0 <= impact_index < n_tech:
        raise ValueError("impact index out of range")
    return coverage, usage


def reachability(portfolios, base, effectiveness, coverage, usage, stage_index, impact_index):
    """Reachability R for each portfolio at fixed base rate and effectiveness.

    ``portfolios`` is [P, mitigation] boolean; ``base`` a scalar in (0, 1];
    ``effectiveness`` a [mitigation] vector in [0, 1). ``stage_index`` is an
    ordered list of technique-index arrays (the non-impact stages come first; the
    impact stage, wherever it sits, contributes the objective technique alone).
    Returns a length-P vector of reachabilities.
    """
    coverage, usage = _validate(coverage, usage, stage_index, impact_index)
    portfolios = np.atleast_2d(np.asarray(portfolios, bool))
    effectiveness = np.asarray(effectiveness, float)
    base = float(base)
    if portfolios.shape[1] != coverage.shape[1] or effectiveness.shape != (coverage.shape[1],):
        raise ValueError("portfolio and effectiveness widths must match the mitigation count")
    if not 0 < base <= 1 or (effectiveness < 0).any() or (effectiveness >= 1).any():
        raise ValueError("base in (0,1] and effectiveness in [0,1) required")
    # log(1 - eff) per (technique, mitigation) present as a coverage edge.
    log_factor = coverage * np.log1p(-effectiveness)[None, :]        # [T, M]
    # Residual success per (portfolio, technique).
    residual = base * np.exp(portfolios @ log_factor.T)             # [P, T]
    stage_success = []
    for members in stage_index:
        w = usage[members] + 1.0                                    # Laplace weight
        stage_success.append((residual[:, members] @ w) / w.sum())
    impact_success = residual[:, impact_index]
    return np.prod(np.stack(stage_success, axis=1), axis=1) * impact_success


def certify_portfolios(portfolios, base_bounds, eff_bounds, coverage, usage,
                       stage_index, impact_index, epsilon):
    """Necessary/possible adequacy certificate at reachability level ``epsilon``.

    ``base_bounds`` is ``(low, high)``; ``eff_bounds`` is a [mitigation, 2] array of
    per-mitigation ``(low, high)`` effectiveness intervals. Returns
    ``(worst, best, guaranteed, possible)``: worst- and best-corner reachability
    per portfolio, and the boolean adequacy masks. ``guaranteed`` implies ``possible``.
    """
    eff_bounds = np.asarray(eff_bounds, float)
    base_low, base_high = float(base_bounds[0]), float(base_bounds[1])
    if eff_bounds.ndim != 2 or eff_bounds.shape[1] != 2:
        raise ValueError("eff_bounds must be [mitigation, 2]")
    if not 0 < base_low <= base_high <= 1 or (eff_bounds[:, 0] > eff_bounds[:, 1]).any():
        raise ValueError("degenerate base or effectiveness interval")
    if not 0 < epsilon < 1:
        raise ValueError("epsilon must lie strictly in (0, 1)")
    args = (coverage, usage, stage_index, impact_index)
    worst = reachability(portfolios, base_high, eff_bounds[:, 0], *args)
    best = reachability(portfolios, base_low, eff_bounds[:, 1], *args)
    if (best > worst + 1e-12).any():
        raise AssertionError("best corner must not exceed worst corner")
    return worst, best, worst <= epsilon, best <= epsilon


def greedy_frontier(base_bounds, eff_bounds, coverage, usage, stage_index, impact_index):
    """Order mitigations by greedy worst-case reachability reduction.

    Returns the list of mitigation indices in the order a defender would add them
    to shrink guaranteed reachability fastest, and the worst-case reachability
    after each addition (a cost-vs-guarantee frontier under unit costs).
    """
    n_mit = coverage.shape[1]
    chosen: list[int] = []
    remaining = set(range(n_mit))
    curve = []
    while remaining:
        candidates = np.array(sorted(remaining))
        trials = np.zeros((len(candidates), n_mit), bool)
        base = np.zeros(n_mit, bool)
        base[chosen] = True
        trials[:] = base
        trials[np.arange(len(candidates)), candidates] = True
        worst, _, _, _ = certify_portfolios(trials, base_bounds, eff_bounds, coverage,
                                             usage, stage_index, impact_index, 0.5)
        pick = int(candidates[int(np.argmin(worst))])
        chosen.append(pick)
        remaining.discard(pick)
        curve.append(float(worst[int(np.argmin(worst))]))
    return chosen, curve
