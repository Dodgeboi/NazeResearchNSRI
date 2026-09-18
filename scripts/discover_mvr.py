#!/usr/bin/env python3
"""Evaluate Marginal-Value Restoration (MVR) vs. the baseline restore order.

MVR changes ONLY the sequence in which isolated nodes are restored — from the
engine's static criticality order to a greedy that maximizes marginal weighted
service availability. Everything else (network, attack, detection, isolation,
restore rate) is identical, matched trial-by-trial, so any difference is
attributable to recovery sequencing alone.

Run under a posture that actually contains and recovers (fast detection +
rapid isolation), because recovery order only matters when recovery happens.

Usage:
    python scripts/discover_mvr.py                # full run
    python scripts/discover_mvr.py --trials 20    # smoke test
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from grrc.config import Config
from grrc.defenses import effective_settings, get_portfolio
from grrc.mvr import MVRSimulation
from grrc.network_generator import generate_network
from grrc.propagation import RansomwareSimulation
from grrc.simulation import choose_entry
from grrc.utilities import trial_rng

SIM_SEED_OFFSET = 800_000_000


def run_grid(cfg, *, facilities, profiles, portfolio_name, trials,
             entry_points):
    port = get_portfolio(portfolio_name)
    rows = []
    for facility in facilities:
        for profile in profiles:
            prof = cfg.profiles[profile]
            eff = effective_settings(prof, port)
            for k in range(trials):
                net_rng = trial_rng(cfg.seed, k)
                net = generate_network(
                    cfg, facility, profile, net_rng,
                    segmentation=eff.segmentation,
                    patch_coverage=eff.patch_coverage,
                    backup_strategy=eff.backup_strategy,
                    identity_controls=eff.identity_controls)
                entry_point = entry_points[k % len(entry_points)]
                entry = choose_entry(net, entry_point, net_rng)
                for policy, cls in (("criticality", RansomwareSimulation),
                                    ("mvr", MVRSimulation)):
                    sim = cls(cfg, net, eff, trial_rng(cfg.seed,
                                                       SIM_SEED_OFFSET + k))
                    m = sim.run(entry)
                    rows.append({
                        "facility": facility, "profile": profile, "trial": k,
                        "policy": policy, "entry_point": entry_point,
                        "weighted_service_hours_lost":
                            m["weighted_service_hours_lost"],
                        "recovery_step": m["recovery_step"],
                        "pct_services_restored": m["pct_services_restored"],
                        "total_compromised": m["total_compromised"],
                    })
    return pd.DataFrame(rows)


def _boot_ci(diff, n_boot=5000, seed=99):
    rng = np.random.default_rng(seed)
    d = diff[~np.isnan(diff)]
    if d.size == 0:
        return float("nan"), float("nan"), float("nan")
    idx = rng.integers(0, d.size, size=(n_boot, d.size))
    means = d[idx].mean(axis=1)
    return (float(d.mean()), float(np.percentile(means, 2.5)),
            float(np.percentile(means, 97.5)))


def summarize(df):
    metric = "weighted_service_hours_lost"
    out = []
    for (fac, prof), cell in df.groupby(["facility", "profile"]):
        wide = cell.pivot_table(index="trial", columns="policy",
                                values=metric).dropna()
        base = wide["criticality"].values
        mvr = wide["mvr"].values
        d, lo, hi = _boot_ci(mvr - base)
        rel = 100.0 * d / base.mean() if base.mean() else float("nan")
        out.append({
            "facility": fac, "profile": prof, "n": len(wide),
            "mean_criticality": base.mean(), "mean_mvr": mvr.mean(),
            "mvr_minus_base": d, "ci_lo": lo, "ci_hi": hi,
            "pct_change": rel, "mvr_better_sig": bool(hi < 0),
        })
    return pd.DataFrame(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--trials", type=int, default=200)
    ap.add_argument("--portfolio", default="seg_plus_detection",
                    help="posture that contains+recovers (needs isolation)")
    ap.add_argument("--out", default="outputs/mvr")
    args = ap.parse_args()

    cfg = Config(); cfg.validate()
    facilities = ["small_clinic", "regional_hospital", "large_hospital"]
    profiles = ["resource_constrained", "intermediate_capacity",
                "high_capacity"]
    entry_points = cfg.experiment.entry_points
    out_dir = Path(args.out); out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Running {len(facilities)}x{len(profiles)} cells, {args.trials} "
          f"matched trials x 2 policies = "
          f"{len(facilities)*len(profiles)*args.trials*2} sims "
          f"(portfolio={args.portfolio}) ...")
    df = run_grid(cfg, facilities=facilities, profiles=profiles,
                  portfolio_name=args.portfolio, trials=args.trials,
                  entry_points=entry_points)
    df.to_csv(out_dir / "mvr_raw.csv", index=False)
    summary = summarize(df)
    summary.to_csv(out_dir / "mvr_summary.csv", index=False)

    pd.set_option("display.width", 140)
    show = summary.copy()
    for c in ("mean_criticality", "mean_mvr", "mvr_minus_base", "ci_lo",
              "ci_hi", "pct_change"):
        show[c] = show[c].round(2)
    print("\n=== weighted service-hours lost: criticality vs MVR "
          "(matched pairs) ===")
    print(show.to_string(index=False))
    n_sig = int(summary["mvr_better_sig"].sum())
    pooled = df.pivot_table(index=["facility", "profile", "trial"],
                            columns="policy",
                            values="weighted_service_hours_lost").dropna()
    pd_, plo, phi = _boot_ci(pooled["mvr"].values - pooled["criticality"].values)
    print(f"\nMVR significantly better (95% CI < 0) in {n_sig}/{len(summary)} "
          f"cells.")
    print(f"Pooled paired mean change: {pd_:.2f} weighted service-hours "
          f"[{plo:.2f}, {phi:.2f}] "
          f"({100*pd_/pooled['criticality'].mean():.1f}% vs baseline).")
    print(f"outputs in {out_dir}/")


if __name__ == "__main__":
    main()
