"""Score every reference defender across the regime sweep -> benchmark tables.

Pure library (no I/O): the script ``scripts/run_defense_range.py`` calls
:func:`run_sweep` and writes the CSVs + a provenance manifest. The primary metric is
**cost-to-certify**: the smallest portfolio a policy reaches that the range certifies
as catastrophic-adequate (``cat_guaranteed`` at the regime's ``k`` and ``epsilon``).
"""
from __future__ import annotations

import numpy as np

from grrc.range.environment import DefenseRange
from grrc.range import policies, adversary
from grrc.range.regimes import BASE_BOUNDS, effectiveness_bounds

# Effectiveness priors for the prior-independence check (mirrors analyze_control_certificate).
EFF_PRIORS = {"narrow": (0.35, 0.55), "default": (0.20, 0.70), "wide": (0.10, 0.85)}


def cost_to_certify(env, order):
    """Smallest prefix size of ``order`` that is catastrophic-guaranteed, else None.

    Returns 0 when the empty portfolio already certifies, so it agrees with the exact
    optimum's cardinality convention.
    """
    n = env.n_mitigations
    if env.score([])["cat_guaranteed"]:
        return 0
    masks = np.zeros((len(order), n), bool)
    running = np.zeros(n, bool)
    for i, m in enumerate(order):
        running = running.copy()
        running[m] = True
        masks[i] = running
    guaranteed = env.catastrophic_certify(masks)[2]
    hit = np.flatnonzero(guaranteed)
    return int(hit[0]) + 1 if hit.size else None


def _na(x):
    return -1 if x is None else int(x)


def run_sweep(model, regimes, seed=20260921):
    """Return {'leaderboard', 'optimality_gap', 'regime_robustness'} row lists."""
    leaderboard, gaps = [], []
    per_policy = {}                      # policy -> list of (regime, cost or None)

    for regime in regimes:
        env = DefenseRange(model, regime)
        n = env.n_mitigations
        orders = {"greedy": policies.greedy_order(env),
                  "coverage": policies.coverage_order(env),
                  "random": policies.random_order(env, seed)}
        costs = {name: cost_to_certify(env, order) for name, order in orders.items()}

        # Exact minimum, bounded by the greedy solution (optimum cannot exceed it).
        opt_idx, opt_size, opt_computed = policies.optimal_small(
            env, upper_bound=costs["greedy"])

        empty_score = env.score([])
        all_score = env.score(range(n))
        empty_certifies = empty_score["cat_guaranteed"]
        all_certifies = all_score["cat_guaranteed"]

        reg = dict(adversary=regime.adversary, degradation_source=regime.degradation_source,
                   epsilon=regime.epsilon, k=regime.k)
        for name in ("greedy", "coverage", "random"):
            c = costs[name]
            leaderboard.append(dict(**reg, policy=name, cost_to_certify=_na(c),
                                    certifies=bool(c is not None)))
            per_policy.setdefault(name, []).append((regime, c))
        leaderboard.append(dict(**reg, policy="optimal",
                                cost_to_certify=_na(opt_size),
                                certifies=bool(opt_size is not None)))
        per_policy.setdefault("optimal", []).append((regime, opt_size))
        leaderboard.append(dict(**reg, policy="empty",
                                cost_to_certify=(0 if empty_certifies else -1),
                                certifies=bool(empty_certifies)))
        leaderboard.append(dict(**reg, policy="all",
                                cost_to_certify=(n if all_certifies else -1),
                                certifies=bool(all_certifies)))

        gaps.append(dict(**reg, empty_cat_worst=empty_score["cat_worst"],
                         all_certifies=bool(all_certifies),
                         optimal_size=_na(opt_size), optimal_computed=bool(opt_computed),
                         greedy_cost=_na(costs["greedy"]),
                         coverage_cost=_na(costs["coverage"]),
                         random_cost=_na(costs["random"]),
                         greedy_gap=(_na(costs["greedy"]) - opt_size
                                     if opt_size is not None and costs["greedy"] is not None
                                     else -1)))

    _sanity(leaderboard, gaps)
    robustness = _robustness(per_policy)
    return dict(leaderboard=leaderboard, optimality_gap=gaps,
                regime_robustness=robustness)


def coverage_report(model, epsilons, ks, deg_bounds, base_bounds=BASE_BOUNDS):
    """The mechanism behind uncertifiability: coverage gaps, the reachability floor,
    and its prior-independence.

    Returns row lists for three tables:
    - ``coverage_gaps``: per stage, techniques with no ATT&CK mitigation (the floor's cause);
    - ``adaptive_floor``: the worst-corner minimum adaptive reachability (control and
      clinical) and, per ``k``, the minimum achievable catastrophic bound (full portfolio);
    - ``prior_robustness``: per effectiveness prior, how many adaptive ``(epsilon, k)``
      regimes remain uncertifiable -- structural gaps make this near-constant.
    """
    graph = model.graph
    full = np.ones(graph.n_mitigations, bool)[None, :]
    gaps = adversary.stage_coverage_gaps(model)

    eff = effectiveness_bounds(graph.mitigations)                 # default prior
    ctrl_floor, clin_floor = adversary.adaptive_floor(model, base_bounds[1], eff[:, 0])
    empty_ctrl = float(adversary.adaptive_control_reachability(
        np.zeros(graph.n_mitigations, bool), base_bounds[1], eff[:, 0], model)[0])
    assert 0 < ctrl_floor <= empty_ctrl + 1e-12, "floor must be the minimum reachability"
    floor_rows = []
    for k in ks:
        cat = float(adversary.adaptive_certify_catastrophic(
            full, base_bounds, eff, deg_bounds, model, k, 0.5)[0][0])
        floor_rows.append(dict(k=int(k), control_floor=ctrl_floor,
                               clinical_floor=clin_floor, catastrophic_floor=cat))

    prior_rows = []
    for name, prior in EFF_PRIORS.items():
        effp = effectiveness_bounds(graph.mitigations, prior)
        uncert = total = 0
        for eps in epsilons:
            for k in ks:
                total += 1
                cat = float(adversary.adaptive_certify_catastrophic(
                    full, base_bounds, effp, deg_bounds, model, k, 0.5)[0][0])
                uncert += int(cat > eps)
        prior_rows.append(dict(prior=name, eff_low=prior[0], eff_high=prior[1],
                               regimes=total, uncertifiable=uncert))
    return dict(coverage_gaps=gaps, adaptive_floor=floor_rows, prior_robustness=prior_rows)


def _robustness(per_policy):
    rows = []
    for policy, entries in per_policy.items():
        total = len(entries)
        certified = [(r, c) for r, c in entries if c is not None]

        def mean_where(pred):
            vals = [c for r, c in certified if pred(r)]
            return round(float(np.mean(vals)), 3) if vals else -1

        rows.append(dict(
            policy=policy, regimes=total, certified=len(certified),
            certified_fraction=round(len(certified) / total, 4) if total else 0.0,
            mean_cost_when_certified=mean_where(lambda r: True),
            mean_cost_typical=mean_where(lambda r: r.adversary == "typical"),
            mean_cost_adaptive=mean_where(lambda r: r.adversary == "adaptive"),
            mean_cost_assumed=mean_where(lambda r: r.degradation_source == "assumed"),
            mean_cost_cipher=mean_where(lambda r: r.degradation_source == "cipher_gamma1")))
    return rows


def _sanity(leaderboard, gaps):
    # optimal never costs more than greedy (when both are known).
    for g in gaps:
        if g["optimal_size"] >= 0 and g["greedy_cost"] >= 0:
            assert g["optimal_size"] <= g["greedy_cost"], "optimal exceeds greedy"
    # greedy cost-to-certify is monotone (its acquisition order is fixed per adversary):
    # non-increasing as k rises (fixed adversary, degradation, epsilon), and
    # non-decreasing as epsilon tightens. Skip uncertified (-1) entries.
    advs = {r["adversary"] for r in leaderboard}
    sources = {r["degradation_source"] for r in leaderboard}
    epsilons = sorted({r["epsilon"] for r in leaderboard}, reverse=True)   # loose -> tight
    ks = sorted({r["k"] for r in leaderboard})
    greedy = {(r["adversary"], r["degradation_source"], r["epsilon"], r["k"]): r["cost_to_certify"]
              for r in leaderboard if r["policy"] == "greedy"}
    for adv in advs:
        for src in sources:
            for eps in epsilons:
                costs = [greedy[(adv, src, eps, k)] for k in ks if greedy[(adv, src, eps, k)] >= 0]
                assert all(costs[i] >= costs[i + 1] for i in range(len(costs) - 1)), \
                    "greedy cost must not rise as k rises"
            for k in ks:
                costs = [greedy[(adv, src, eps, k)] for eps in epsilons
                         if greedy[(adv, src, eps, k)] >= 0]
                assert all(costs[i] <= costs[i + 1] for i in range(len(costs) - 1)), \
                    "greedy cost must not fall as epsilon tightens"
    # The adaptive adversary is at least as hard: for a fixed policy and regime, its
    # cost-to-certify is >= the typical adversary's (max reachability >= mean).
    if {"typical", "adaptive"} <= advs:
        by_key = {}
        for r in leaderboard:
            by_key.setdefault((r["policy"], r["degradation_source"], r["epsilon"], r["k"]),
                              {})[r["adversary"]] = r["cost_to_certify"]
        for (policy, _, _, _), d in by_key.items():
            t, a = d.get("typical", -1), d.get("adaptive", -1)
            if t >= 0 and a >= 0:
                assert a >= t, "adaptive cost must be >= typical cost"
