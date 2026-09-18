#!/usr/bin/env python3
"""Evaluate Value-Gradient Reactive Isolation (VGRI) against baselines.

Four postures on IDENTICAL networks and random streams:
    open      never segment
    static    always segment (all cross-zone links, full operational cost)
    reactive  blunt reactive segmentation (all links on detection)
    vgri      targeted reactive segmentation (top-value links only, cheaper)

Sweeps detection speed x segmentation operational cost. Reports, per cell,
mean weighted service-hours lost per posture and matched-pair bootstrap CIs
for VGRI vs the best of the three baselines. Emits CSVs + a phase figure.

Usage:
    python scripts/discover_vgri.py               # full run
    python scripts/discover_vgri.py --trials 8    # smoke test
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from grrc.adaptive import AdaptiveSimulation
from grrc.config import Config
from grrc.defenses import EffectiveSettings
from grrc.enums import SegmentationLevel
from grrc.network_generator import generate_network
from grrc.simulation import choose_entry
from grrc.utilities import trial_rng
from grrc.vgri import RPESimulation, VGRISimulation

BASELINES = ("open", "static", "reactive")
POSTURES = BASELINES + ("vgri", "rpe")
SIM_SEED_OFFSET = 700_000_000
SEG_CLAMP = 0.25  # least-privilege cross-boundary modifier


def run_grid(cfg, *, facility, profile, detection_delays, cost_fracs,
             trials, entry_points, cut_fraction, trigger, hold):
    prof = cfg.profiles[profile]
    rows = []
    for delay in detection_delays:
        eff = EffectiveSettings(
            segmentation=SegmentationLevel.FLAT, patch_coverage=prof.patch_coverage,
            detection_delay=delay, isolation_success=prof.isolation_success,
            isolate_same_step=False, backup_strategy="connected",
            identity_controls=False)
        for k in range(trials):
            net_rng = trial_rng(cfg.seed, k)
            net = generate_network(
                cfg, facility, profile, net_rng,
                segmentation=SegmentationLevel.FLAT,
                patch_coverage=prof.patch_coverage,
                backup_strategy="connected", identity_controls=False)
            entry_point = entry_points[k % len(entry_points)]
            entry = choose_entry(net, entry_point, net_rng)
            for cost in cost_fracs:
                for posture in POSTURES:
                    sim_rng = trial_rng(cfg.seed, SIM_SEED_OFFSET + k)
                    if posture == "vgri":
                        sim = VGRISimulation(
                            cfg, net, eff, sim_rng, seg_clamp=SEG_CLAMP,
                            avail_cost_frac=cost, cut_fraction=cut_fraction,
                            trigger=trigger, hold=hold)
                    elif posture == "rpe":
                        sim = RPESimulation(
                            cfg, net, eff, sim_rng, seg_clamp=SEG_CLAMP,
                            avail_cost_frac=cost, trigger=trigger, hold=hold)
                    else:
                        sim = AdaptiveSimulation(
                            cfg, net, eff, sim_rng, posture=posture,
                            seg_clamp=SEG_CLAMP, avail_cost_frac=cost,
                            trigger=trigger, hold=hold)
                    m = sim.run(entry)
                    rows.append({
                        "trial": k, "detection_delay": delay,
                        "cost_frac": cost, "posture": posture,
                        "weighted_service_hours_lost":
                            m["weighted_service_hours_lost"],
                        "catastrophic": m["catastrophic"],
                        "total_compromised": m["total_compromised"],
                        "engaged_steps": sim.engaged_steps,
                    })
    return pd.DataFrame(rows)


def _boot_ci(diff, n_boot=2000, seed=12345):
    rng = np.random.default_rng(seed)
    if diff.size == 0:
        return float("nan"), float("nan"), float("nan")
    idx = rng.integers(0, diff.size, size=(n_boot, diff.size))
    means = diff[idx].mean(axis=1)
    return (float(diff.mean()), float(np.percentile(means, 2.5)),
            float(np.percentile(means, 97.5)))


def summarize(df):
    """Per (delay, cost) cell: mean hours lost per posture, the overall
    winner, and matched-pair bootstrap CIs for each TARGETED method (rpe, the
    headline candidate; vgri, the failed fractional variant) against the best
    of the three baseline postures. Pairing is valid: every posture shares the
    same network and random stream within a trial."""
    metric = "weighted_service_hours_lost"
    out = []
    for (delay, cost), cell in df.groupby(["detection_delay", "cost_frac"]):
        wide = cell.pivot_table(index="trial", columns="posture",
                                values=metric).dropna()
        means = {p: wide[p].mean() for p in POSTURES}
        best_base = np.minimum.reduce([wide[p].values for p in BASELINES])
        winner = min(means, key=means.get)
        row = {"detection_delay": delay, "cost_frac": cost, "n": len(wide),
               **{f"mean_{p}": means[p] for p in POSTURES}, "winner": winner}
        for method, pre in (("rpe", "rpe"), ("vgri", "vgri")):
            d, lo, hi = _boot_ci(wide[method].values - best_base)
            row[f"{pre}_minus_best_baseline"] = d
            row[f"{pre}_lo"] = lo
            row[f"{pre}_hi"] = hi
            row[f"{pre}_sig_best"] = bool(hi < 0)
        out.append(row)
    return pd.DataFrame(out)


def make_figure(summary, out_png):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import TwoSlopeNorm

    delays = sorted(summary["detection_delay"].unique())
    costs = sorted(summary["cost_frac"].unique())
    margin = np.full((len(costs), len(delays)), np.nan)
    winner = np.empty((len(costs), len(delays)), dtype=object)
    for _, r in summary.iterrows():
        i, j = costs.index(r["cost_frac"]), delays.index(r["detection_delay"])
        margin[i, j] = r["rpe_minus_best_baseline"]
        winner[i, j] = r["winner"]
    fig, ax = plt.subplots(figsize=(8.5, 5.5))
    vmax = float(np.nanmax(np.abs(margin))) or 1.0
    im = ax.imshow(margin, cmap="RdBu",
                   norm=TwoSlopeNorm(vmin=-vmax, vcenter=0, vmax=vmax),
                   aspect="auto", origin="lower")
    ax.set_xticks(range(len(delays))); ax.set_xticklabels(delays)
    ax.set_yticks(range(len(costs)))
    ax.set_yticklabels([f"{c:.0%}" for c in costs])
    ax.set_xlabel("Detection delay (steps; larger = slower)")
    ax.set_ylabel("Segmentation operational cost\n(fraction of clinical nodes)")
    ax.set_title("Reactive Protective Enclaving (RPE) vs. best baseline\n"
                 "(blue = RPE wins; label = overall winner in cell)")
    for i in range(len(costs)):
        for j in range(len(delays)):
            ax.text(j, i, str(winner[i, j])[:4], ha="center", va="center",
                    fontsize=8, color="black")
    cb = fig.colorbar(im, ax=ax)
    cb.set_label("mean service-hours lost: RPE − best baseline\n"
                 "(negative = RPE better)")
    fig.tight_layout()
    fig.savefig(out_png, dpi=150)
    fig.savefig(out_png.with_suffix(".pdf"))
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--trials", type=int, default=150)
    ap.add_argument("--facility", default="regional_hospital")
    ap.add_argument("--profile", default="intermediate_capacity")
    ap.add_argument("--cut-fraction", type=float, default=0.34)
    ap.add_argument("--trigger", type=int, default=1)
    ap.add_argument("--hold", type=int, default=6)
    ap.add_argument("--out", default="outputs/vgri")
    args = ap.parse_args()

    cfg = Config(); cfg.validate()
    detection_delays = [1, 2, 3, 6, 12, 24]
    cost_fracs = [0.0, 0.15, 0.30, 0.45]
    entry_points = cfg.experiment.entry_points
    out_dir = Path(args.out); out_dir.mkdir(parents=True, exist_ok=True)

    total = len(detection_delays) * len(cost_fracs) * args.trials * len(POSTURES)
    print(f"Running {len(detection_delays)}x{len(cost_fracs)} grid, "
          f"{args.trials} matched trials x {len(POSTURES)} postures = "
          f"{total} sims (cut_fraction={args.cut_fraction}) ...")
    df = run_grid(cfg, facility=args.facility, profile=args.profile,
                  detection_delays=detection_delays, cost_fracs=cost_fracs,
                  trials=args.trials, entry_points=entry_points,
                  cut_fraction=args.cut_fraction, trigger=args.trigger,
                  hold=args.hold)
    df.to_csv(out_dir / "vgri_raw.csv", index=False)
    summary = summarize(df)
    summary.to_csv(out_dir / "vgri_summary.csv", index=False)
    make_figure(summary, out_dir / "vgri_phase.png")

    pd.set_option("display.width", 140); pd.set_option("display.max_columns", 30)
    show = summary.copy()
    for c in show.columns:
        if show[c].dtype == float:
            show[c] = show[c].round(1)
    print("\n=== mean weighted service-hours lost by cell ===")
    print(show[["detection_delay", "cost_frac", "n", "mean_open",
                "mean_static", "mean_reactive", "mean_vgri", "mean_rpe",
                "rpe_minus_best_baseline", "rpe_lo", "rpe_hi", "winner",
                "rpe_sig_best"]].to_string(index=False))
    n_win = int((summary["winner"] == "rpe").sum())
    n_sig = int(summary["rpe_sig_best"].sum())
    n_vgri_sig = int(summary["vgri_sig_best"].sum())
    print(f"\nRPE is the outright winner in {n_win}/{len(summary)} cells; "
          f"beats ALL baselines with 95% CI clear of 0 in {n_sig} cells.")
    print(f"(For contrast, the fractional VGRI variant is sig-best in "
          f"{n_vgri_sig} cells.)")
    print(f"outputs in {out_dir}/")


if __name__ == "__main__":
    main()
