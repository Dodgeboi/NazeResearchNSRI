#!/usr/bin/env python3
"""Adversary-robust defense selection.

The main study selects a budget-constrained defense portfolio by minimizing
expected disruption **against the base (untargeted) attacker**. But the
adversary-robustness experiment (scripts/discover_adaptive_attacker.py) showed
that a value-targeting attacker erodes those defenses unevenly. So the natural
question is a *selection* question, not a new control:

    Is the portfolio the study would recommend (best vs the naive attacker)
    still the best choice against a targeting attacker? If not, selecting
    against the targeting attacker yields a different, more robust defense at
    the same budget.

This is *adversary-robust defense selection*: evaluate every affordable
portfolio against the targeting attacker and pick the min-disruption one,
rather than picking against the naive attacker. It is a selection procedure
(not a new defensive primitive), and it directly operationalizes the
robustness finding.

For each budget we report:
  * naive_pick   — portfolio the study's criterion chooses (min damage vs naive)
  * robust_pick  — portfolio chosen against the adaptive attacker
  * the regret of deploying naive_pick when the real attacker is adaptive
    (its adaptive-damage minus robust_pick's adaptive-damage).

Usage:
    python scripts/discover_robust_defense.py               # full
    python scripts/discover_robust_defense.py --trials 30   # smoke
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from grrc.attacker import AdaptiveAttackerSimulation
from grrc.config import Config
from grrc.defenses import (effective_settings, enumerate_portfolios,
                           portfolio_cost)
from grrc.config import load_defense_costs
from grrc.network_generator import generate_network
from grrc.propagation import RansomwareSimulation
from grrc.simulation import choose_entry
from grrc.utilities import resolve_path, trial_rng

SIM_SEED_OFFSET = 970_000_000


def evaluate(cfg, *, facility, profile, trials, entry_points, focus, costs):
    """Mean weighted damage per (portfolio, attacker), plus each portfolio's
    cost. Portfolios are the deduplicated optimizer lattice for this profile."""
    prof = cfg.profiles[profile]
    # Deduplicate portfolios by their resolved effective settings (same as the
    # study's optimizer), keyed by the cost + effective tuple.
    seen = {}
    for p in enumerate_portfolios():
        eff = effective_settings(prof, p)
        key = (eff.segmentation.value, round(eff.patch_coverage, 3),
               eff.detection_delay, round(eff.isolation_success, 3),
               eff.isolate_same_step, eff.backup_strategy,
               eff.identity_controls)
        if key not in seen:
            seen[key] = (p, eff, portfolio_cost(p, prof, costs))
    rows = []
    for key, (p, eff, cost) in seen.items():
        for k in range(trials):
            net_rng = trial_rng(cfg.seed, k)
            net = generate_network(
                cfg, facility, profile, net_rng,
                segmentation=eff.segmentation, patch_coverage=eff.patch_coverage,
                backup_strategy=eff.backup_strategy,
                identity_controls=eff.identity_controls)
            entry_point = entry_points[k % len(entry_points)]
            entry = choose_entry(net, entry_point, net_rng)
            for attacker in ("naive", "adaptive"):
                rng = trial_rng(cfg.seed, SIM_SEED_OFFSET + k)
                if attacker == "adaptive":
                    sim = AdaptiveAttackerSimulation(cfg, net, eff, rng,
                                                     focus=focus)
                else:
                    sim = RansomwareSimulation(cfg, net, eff, rng)
                m = sim.run(entry)
                rows.append({"portfolio": p.name, "cost": cost,
                             "attacker": attacker,
                             "hours": m["weighted_service_hours_lost"],
                             "catastrophic": m["catastrophic"]})
    return pd.DataFrame(rows)


def select(df, budgets):
    """For each budget, the naive-optimal and adaptive-optimal (robust) picks,
    and the regret of the naive pick under the adaptive attacker."""
    agg = df.groupby(["portfolio", "cost", "attacker"]).agg(
        hours=("hours", "mean"), cat=("catastrophic", "mean")).reset_index()
    wide = agg.pivot_table(index=["portfolio", "cost"], columns="attacker",
                           values=["hours", "cat"]).reset_index()
    wide.columns = ["portfolio", "cost", "cat_adaptive", "cat_naive",
                    "hours_adaptive", "hours_naive"]
    out = []
    for b in budgets:
        aff = wide[wide.cost <= b]
        if aff.empty:
            continue
        naive_pick = aff.loc[aff.hours_naive.idxmin()]
        robust_pick = aff.loc[aff.hours_adaptive.idxmin()]
        out.append({
            "budget": b,
            "naive_pick": naive_pick.portfolio,
            "naive_pick_cost": naive_pick.cost,
            "naive_pick_hours_vs_adaptive": naive_pick.hours_adaptive,
            "naive_pick_cat_vs_adaptive": naive_pick.cat_adaptive,
            "robust_pick": robust_pick.portfolio,
            "robust_pick_cost": robust_pick.cost,
            "robust_pick_hours_vs_adaptive": robust_pick.hours_adaptive,
            "robust_pick_cat_vs_adaptive": robust_pick.cat_adaptive,
            "regret_hours": naive_pick.hours_adaptive - robust_pick.hours_adaptive,
            "picks_differ": naive_pick.portfolio != robust_pick.portfolio,
        })
    return pd.DataFrame(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--trials", type=int, default=120)
    ap.add_argument("--facility", default="regional_hospital")
    ap.add_argument("--profile", default="intermediate_capacity")
    ap.add_argument("--focus", type=float, default=3.0)
    ap.add_argument("--budgets", type=int, nargs="+", default=[5, 10, 15])
    ap.add_argument("--out", default="outputs/robust")
    args = ap.parse_args()

    cfg = Config(); cfg.validate()
    costs = load_defense_costs(resolve_path("configs/defense_costs.yaml"))
    entry_points = cfg.experiment.entry_points
    out_dir = Path(args.out); out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Evaluating deduplicated portfolio lattice x {args.trials} trials "
          f"x 2 attackers (focus={args.focus}) ...")
    df = evaluate(cfg, facility=args.facility, profile=args.profile,
                  trials=args.trials, entry_points=entry_points,
                  focus=args.focus, costs=costs)
    df.to_csv(out_dir / "robust_raw.csv", index=False)
    sel = select(df, args.budgets)
    sel.to_csv(out_dir / "robust_selection.csv", index=False)

    pd.set_option("display.width", 160)
    for _, r in sel.iterrows():
        print(f"\n--- budget {r.budget} ---")
        print(f"  study's pick (best vs naive): {r.naive_pick} "
              f"(cost {r.naive_pick_cost:.0f})")
        print(f"    -> vs adaptive attacker: {r.naive_pick_hours_vs_adaptive:.1f} "
              f"hours, P(catastrophic)={r.naive_pick_cat_vs_adaptive:.2f}")
        print(f"  robust pick (best vs adaptive): {r.robust_pick} "
              f"(cost {r.robust_pick_cost:.0f})")
        print(f"    -> vs adaptive attacker: {r.robust_pick_hours_vs_adaptive:.1f} "
              f"hours, P(catastrophic)={r.robust_pick_cat_vs_adaptive:.2f}")
        print(f"  picks differ: {r.picks_differ}; regret of study's pick: "
              f"{r.regret_hours:.1f} weighted service-hours")
    ndiff = int(sel.picks_differ.sum())
    print(f"\nStudy's pick != robust pick in {ndiff}/{len(sel)} budgets.")
    print(f"outputs in {out_dir}/")


if __name__ == "__main__":
    main()
