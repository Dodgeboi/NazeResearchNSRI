#!/usr/bin/env python3
"""Does the study's defense benefit survive a service-targeting attacker?

The main study measures defenses against the base (untargeted, memoryless)
attacker. This script re-runs the key named portfolios against BOTH the base
attacker and an adaptive attacker that steers lateral movement toward high
downstream-clinical-value nodes, on identical networks/entries/seeds, and asks
whether the headline "full defense cuts weighted service-hours ~98%" holds.

Usage:
    python scripts/discover_adaptive_attacker.py              # full
    python scripts/discover_adaptive_attacker.py --trials 20  # smoke
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from grrc.attacker import AdaptiveAttackerSimulation
from grrc.config import Config
from grrc.defenses import effective_settings, get_portfolio
from grrc.network_generator import generate_network
from grrc.propagation import RansomwareSimulation
from grrc.simulation import choose_entry
from grrc.utilities import trial_rng

SIM_SEED_OFFSET = 950_000_000
PORTFOLIOS = ["baseline_flat", "least_privilege", "patch_90",
              "fast_detection", "isolated_backups", "full_defense"]
ATTACKERS = ("naive", "adaptive")


def run_grid(cfg, *, facility, profile, trials, entry_points, focus):
    prof = cfg.profiles[profile]
    rows = []
    for pname in PORTFOLIOS:
        port = get_portfolio(pname)
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
            for attacker in ATTACKERS:
                rng = trial_rng(cfg.seed, SIM_SEED_OFFSET + k)
                if attacker == "adaptive":
                    sim = AdaptiveAttackerSimulation(cfg, net, eff, rng,
                                                     focus=focus)
                else:
                    sim = RansomwareSimulation(cfg, net, eff, rng)
                m = sim.run(entry)
                rows.append({
                    "portfolio": pname, "attacker": attacker, "trial": k,
                    "weighted_service_hours_lost":
                        m["weighted_service_hours_lost"],
                    "catastrophic": m["catastrophic"],
                    "identity_compromised": m["identity_compromised"],
                    "total_compromised": m["total_compromised"],
                })
    return pd.DataFrame(rows)


def _boot_ci(x, n_boot=5000, seed=3):
    rng = np.random.default_rng(seed)
    if x.size == 0:
        return float("nan"), float("nan"), float("nan")
    idx = rng.integers(0, x.size, size=(n_boot, x.size))
    m = x[idx].mean(axis=1)
    return float(x.mean()), float(np.percentile(m, 2.5)), float(np.percentile(m, 97.5))


def summarize(df):
    metric = "weighted_service_hours_lost"
    rows = []
    for (pname, atk), cell in df.groupby(["portfolio", "attacker"]):
        mean, lo, hi = _boot_ci(cell[metric].values)
        rows.append({"portfolio": pname, "attacker": atk, "mean_hours": mean,
                     "lo": lo, "hi": hi,
                     "p_catastrophic": cell["catastrophic"].mean(),
                     "p_identity": cell["identity_compromised"].mean()})
    s = pd.DataFrame(rows)
    # Reduction of full_defense vs baseline_flat, per attacker.
    red = {}
    for atk in ATTACKERS:
        base = s[(s.portfolio == "baseline_flat") & (s.attacker == atk)][
            "mean_hours"].values[0]
        full = s[(s.portfolio == "full_defense") & (s.attacker == atk)][
            "mean_hours"].values[0]
        red[atk] = (base, full, 100.0 * (base - full) / base if base else float("nan"))
    return s, red


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--trials", type=int, default=200)
    ap.add_argument("--facility", default="regional_hospital")
    ap.add_argument("--profile", default="intermediate_capacity")
    ap.add_argument("--focus", type=float, default=3.0)
    ap.add_argument("--out", default="outputs/attacker")
    args = ap.parse_args()

    cfg = Config(); cfg.validate()
    entry_points = cfg.experiment.entry_points
    out_dir = Path(args.out); out_dir.mkdir(parents=True, exist_ok=True)

    total = len(PORTFOLIOS) * args.trials * len(ATTACKERS)
    print(f"Running {len(PORTFOLIOS)} portfolios x {args.trials} matched "
          f"trials x 2 attackers = {total} sims (focus={args.focus}) ...")
    df = run_grid(cfg, facility=args.facility, profile=args.profile,
                  trials=args.trials, entry_points=entry_points,
                  focus=args.focus)
    df.to_csv(out_dir / "attacker_raw.csv", index=False)
    s, red = summarize(df)
    s.to_csv(out_dir / "attacker_summary.csv", index=False)

    pd.set_option("display.width", 130)
    show = s.copy()
    for c in ("mean_hours", "lo", "hi", "p_catastrophic", "p_identity"):
        show[c] = show[c].round(2)
    print("\n=== mean weighted service-hours lost by portfolio x attacker ===")
    print(show.to_string(index=False))
    print("\n=== defense-in-depth reduction (full_defense vs baseline_flat) ===")
    for atk in ATTACKERS:
        base, full, pct = red[atk]
        print(f"  {atk:9s}: baseline={base:7.1f}  full={full:7.1f}  "
              f"reduction={pct:5.1f}%")
    # Headline: how much the reported resilience erodes under targeting.
    print(f"\nThe study reports ~98% against the naive attacker; here the "
          f"naive reduction is {red['naive'][2]:.1f}% and the adaptive-attacker "
          f"reduction is {red['adaptive'][2]:.1f}%.")
    print(f"outputs in {out_dir}/")


if __name__ == "__main__":
    main()
