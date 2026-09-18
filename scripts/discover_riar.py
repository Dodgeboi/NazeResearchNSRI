#!/usr/bin/env python3
"""Re-Infection-Aware Recovery (RIAR) under recovery-during-active-spread.

The base engine restores only after full containment (the recovery-sequencing
literature's assumption). With ``concurrent_recovery`` on, restoration runs
while the intrusion is live, so restored nodes can be re-infected. This script
asks: under that realistic regime, does naive recovery churn, and does RIAR
(marginal-value order + immunize-on-restore) fix it?

Policies (matched networks / entries / RNG; only the policy differs):
    gated       base engine, recovery only after containment (reference)
    naive       concurrent recovery, criticality order, no hardening
    mvr         concurrent recovery, marginal-value order, no hardening
    riar        concurrent recovery, marginal-value order + immunize-on-restore

Run under a moderate posture (delay 6, isolation 0.7, flat) so the attack stays
active long enough for recovery to overlap spread.

Usage:
    python scripts/discover_riar.py                # full run
    python scripts/discover_riar.py --trials 20    # smoke test
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from grrc.config import Config
from grrc.defenses import EffectiveSettings
from grrc.enums import SegmentationLevel
from grrc.mvr import MVRSimulation
from grrc.network_generator import generate_network
from grrc.propagation import RansomwareSimulation
from grrc.riar import RIARSimulation
from grrc.simulation import choose_entry
from grrc.utilities import trial_rng

SIM_SEED_OFFSET = 900_000_000
POLICIES = ("gated", "naive", "mvr", "riar")


def _make_cfg(concurrent: bool) -> Config:
    cfg = Config()
    cfg.simulation.concurrent_recovery = concurrent
    cfg.validate()
    return cfg


def run_grid(*, facilities, profiles, detection_delay, isolation, trials,
             entry_points):
    cfg_gated = _make_cfg(False)
    cfg_conc = _make_cfg(True)
    rows = []
    for facility in facilities:
        for profile in profiles:
            prof = cfg_gated.profiles[profile]
            eff = EffectiveSettings(
                segmentation=SegmentationLevel.FLAT,
                patch_coverage=prof.patch_coverage,
                detection_delay=detection_delay, isolation_success=isolation,
                isolate_same_step=False, backup_strategy="connected",
                identity_controls=False)
            for k in range(trials):
                net_rng = trial_rng(cfg_gated.seed, k)
                net = generate_network(
                    cfg_gated, facility, profile, net_rng,
                    segmentation=SegmentationLevel.FLAT,
                    patch_coverage=prof.patch_coverage,
                    backup_strategy="connected", identity_controls=False)
                entry_point = entry_points[k % len(entry_points)]
                entry = choose_entry(net, entry_point, net_rng)
                for policy in POLICIES:
                    cfg = cfg_gated if policy == "gated" else cfg_conc
                    rng = trial_rng(cfg.seed, SIM_SEED_OFFSET + k)
                    if policy == "riar":
                        sim = RIARSimulation(cfg, net, eff, rng)
                    elif policy == "mvr":
                        sim = MVRSimulation(cfg, net, eff, rng)
                    else:  # gated, naive
                        sim = RansomwareSimulation(cfg, net, eff, rng)
                    m = sim.run(entry)
                    rows.append({
                        "facility": facility, "profile": profile, "trial": k,
                        "policy": policy,
                        "weighted_service_hours_lost":
                            m["weighted_service_hours_lost"],
                        "pct_services_restored": m["pct_services_restored"],
                        "reinfections": getattr(sim, "reinfections", 0),
                    })
    return pd.DataFrame(rows)


def _boot_ci(diff, n_boot=5000, seed=7):
    rng = np.random.default_rng(seed)
    d = diff[~np.isnan(diff)]
    if d.size == 0:
        return float("nan"), float("nan"), float("nan")
    idx = rng.integers(0, d.size, size=(n_boot, d.size))
    m = d[idx].mean(axis=1)
    return float(d.mean()), float(np.percentile(m, 2.5)), float(np.percentile(m, 97.5))


def summarize(df):
    metric = "weighted_service_hours_lost"
    out = []
    for (fac, prof), cell in df.groupby(["facility", "profile"]):
        wide = cell.pivot_table(index="trial", columns="policy",
                                values=metric).dropna()
        means = {p: wide[p].mean() for p in POLICIES}
        d_rn, lo_rn, hi_rn = _boot_ci(wide["riar"].values - wide["naive"].values)
        d_rm, lo_rm, hi_rm = _boot_ci(wide["riar"].values - wide["mvr"].values)
        reinf = df[(df.facility == fac) & (df.profile == prof)].groupby(
            "policy")["reinfections"].mean()
        out.append({
            "facility": fac, "profile": prof, "n": len(wide),
            **{f"h_{p}": means[p] for p in POLICIES},
            "riar_minus_naive": d_rn, "rn_lo": lo_rn, "rn_hi": hi_rn,
            "riar_minus_mvr": d_rm, "rm_lo": lo_rm, "rm_hi": hi_rm,
            "reinf_naive": float(reinf.get("naive", 0)),
            "reinf_riar": float(reinf.get("riar", 0)),
            "riar_beats_naive_sig": bool(hi_rn < 0),
        })
    return pd.DataFrame(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--trials", type=int, default=150)
    ap.add_argument("--delay", type=int, default=6)
    ap.add_argument("--isolation", type=float, default=0.7)
    ap.add_argument("--out", default="outputs/riar")
    args = ap.parse_args()

    facilities = ["small_clinic", "regional_hospital", "large_hospital"]
    profiles = ["resource_constrained", "intermediate_capacity",
                "high_capacity"]
    entry_points = [e for e in Config().experiment.entry_points]
    out_dir = Path(args.out); out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Running {len(facilities)}x{len(profiles)} cells, {args.trials} "
          f"matched trials x {len(POLICIES)} policies = "
          f"{len(facilities)*len(profiles)*args.trials*len(POLICIES)} sims "
          f"(delay={args.delay}, isolation={args.isolation}) ...")
    df = run_grid(facilities=facilities, profiles=profiles,
                  detection_delay=args.delay, isolation=args.isolation,
                  trials=args.trials, entry_points=entry_points)
    df.to_csv(out_dir / "riar_raw.csv", index=False)
    summary = summarize(df)
    summary.to_csv(out_dir / "riar_summary.csv", index=False)

    pd.set_option("display.width", 160); pd.set_option("display.max_columns", 30)
    show = summary.copy()
    for c in show.columns:
        if show[c].dtype == float:
            show[c] = show[c].round(2)
    print("\n=== weighted service-hours lost by policy (matched) ===")
    print(show[["facility", "profile", "n", "h_gated", "h_naive", "h_mvr",
                "h_riar", "riar_minus_naive", "rn_lo", "rn_hi",
                "reinf_naive", "reinf_riar",
                "riar_beats_naive_sig"]].to_string(index=False))
    n_sig = int(summary["riar_beats_naive_sig"].sum())
    pooled = df.pivot_table(index=["facility", "profile", "trial"],
                            columns="policy",
                            values="weighted_service_hours_lost").dropna()
    d, lo, hi = _boot_ci(pooled["riar"].values - pooled["naive"].values)
    print(f"\nRIAR beats naive concurrent recovery (95% CI < 0) in "
          f"{n_sig}/{len(summary)} cells.")
    print(f"Pooled RIAR - naive: {d:.2f} weighted service-hours [{lo:.2f}, "
          f"{hi:.2f}] ({100*d/pooled['naive'].mean():.1f}% vs naive).")
    print(f"Mean re-infections: naive={df[df.policy=='naive'].reinfections.mean():.1f}, "
          f"riar={df[df.policy=='riar'].reinfections.mean():.1f}")
    print(f"outputs in {out_dir}/")


if __name__ == "__main__":
    main()
