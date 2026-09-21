"""Score every reference defender across the regime sweep -> benchmark tables.

Pure library (no I/O): the script ``scripts/run_defense_range.py`` calls
:func:`run_sweep` and writes the CSVs + a provenance manifest. The primary metric is
**cost-to-certify**: the smallest portfolio a policy reaches that the range certifies
as catastrophic-adequate (``cat_guaranteed`` at the regime's ``k`` and ``epsilon``).
"""
from __future__ import annotations

import numpy as np

from grrc.range.environment import DefenseRange
from grrc.range import policies


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

        reg = dict(degradation_source=regime.degradation_source,
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


def _robustness(per_policy):
    rows = []
    for policy, entries in per_policy.items():
        total = len(entries)
        certified = [(r, c) for r, c in entries if c is not None]
        by_source = {}
        for r, c in certified:
            by_source.setdefault(r.degradation_source, []).append(c)
        rows.append(dict(
            policy=policy, regimes=total, certified=len(certified),
            certified_fraction=round(len(certified) / total, 4) if total else 0.0,
            mean_cost_when_certified=(round(float(np.mean([c for _, c in certified])), 3)
                                      if certified else -1),
            mean_cost_assumed=(round(float(np.mean(by_source["assumed"])), 3)
                               if by_source.get("assumed") else -1),
            mean_cost_cipher=(round(float(np.mean(by_source["cipher_gamma1"])), 3)
                              if by_source.get("cipher_gamma1") else -1)))
    return rows


def _sanity(leaderboard, gaps):
    # optimal never costs more than greedy (when both are known).
    for g in gaps:
        if g["optimal_size"] >= 0 and g["greedy_cost"] >= 0:
            assert g["optimal_size"] <= g["greedy_cost"], "optimal exceeds greedy"
    # greedy cost-to-certify is monotone (its acquisition order is regime-independent):
    # non-increasing as k rises (fixed degradation, epsilon), and non-decreasing as
    # epsilon tightens (fixed degradation, k). Skip uncertified (-1) entries.
    sources = {r["degradation_source"] for r in leaderboard}
    epsilons = sorted({r["epsilon"] for r in leaderboard}, reverse=True)   # loose -> tight
    ks = sorted({r["k"] for r in leaderboard})
    greedy = {(r["degradation_source"], r["epsilon"], r["k"]): r["cost_to_certify"]
              for r in leaderboard if r["policy"] == "greedy"}
    for src in sources:
        for eps in epsilons:
            costs = [greedy[(src, eps, k)] for k in ks if greedy[(src, eps, k)] >= 0]
            assert all(costs[i] >= costs[i + 1] for i in range(len(costs) - 1)), \
                "greedy cost must not rise as k rises"
        for k in ks:
            costs = [greedy[(src, eps, k)] for eps in epsilons if greedy[(src, eps, k)] >= 0]
            assert all(costs[i] <= costs[i + 1] for i in range(len(costs) - 1)), \
                "greedy cost must not fall as epsilon tightens"
