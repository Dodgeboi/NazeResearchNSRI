#!/usr/bin/env python3
"""Discover and characterize *reactive segmentation* as a defense policy.

Head-to-head, on IDENTICAL networks and random streams, of three
segmentation postures (open / static / reactive) across a grid of
detection speed x segmentation operational-cost. See grrc.adaptive for the
model. Emits a tidy per-trial CSV, a summary table, and a phase-diagram
figure showing where each posture wins on weighted service-hours lost.

Usage:
    python scripts/discover_adaptive_segmentation.py            # full run
    python scripts/discover_adaptive_segmentation.py --trials 8 # smoke test
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

POSTURES = ("open", "static", "reactive")
SIM_SEED_OFFSET = 700_000_000  # keep sim RNG stream disjoint from net RNG

# The reactive clamp equals the least-privilege cross-boundary modifier, so
# "engage segmentation" means "become a least-privilege network".
SEG_CLAMP = 0.25


def run_grid(cfg: Config, *, facility: str, profile: str,
             detection_delays: list[int], cost_fracs: list[float],
             trials: int, entry_points: list[str], trigger: int,
             hold: int) -> pd.DataFrame:
    prof = cfg.profiles[profile]
    rows: list[dict] = []
    for delay in detection_delays:
        eff = EffectiveSettings(
            segmentation=SegmentationLevel.FLAT,   # shared open topology
            patch_coverage=prof.patch_coverage,
            detection_delay=delay,
            isolation_success=prof.isolation_success,
            isolate_same_step=False,
            backup_strategy="connected",
            identity_controls=False,
        )
        for k in range(trials):
            # One network + entry per trial, shared by every posture/cost.
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
                    # Same seed for every posture => identical draws until the
                    # policy itself forces divergence. That isolates policy.
                    sim_rng = trial_rng(cfg.seed, SIM_SEED_OFFSET + k)
                    sim = AdaptiveSimulation(
                        cfg, net, eff, sim_rng, posture=posture,
                        seg_clamp=SEG_CLAMP, avail_cost_frac=cost,
                        trigger=trigger, hold=hold)
                    m = sim.run(entry)
                    rows.append({
                        "trial": k, "facility": facility, "profile": profile,
                        "detection_delay": delay, "cost_frac": cost,
                        "posture": posture, "entry_point": entry_point,
                        "n_nodes": net.n_nodes,
                        "weighted_service_hours_lost":
                            m["weighted_service_hours_lost"],
                        "catastrophic": m["catastrophic"],
                        "total_compromised": m["total_compromised"],
                        "engaged_steps": sim.engaged_steps,
                        "first_engage_step": sim.first_engage_step,
                    })
    return pd.DataFrame(rows)


def _boot_ci(diff: np.ndarray, n_boot: int = 2000,
             seed: int = 12345) -> tuple[float, float, float]:
    """Mean of a paired difference with a 95% bootstrap CI."""
    rng = np.random.default_rng(seed)
    if diff.size == 0:
        return float("nan"), float("nan"), float("nan")
    idx = rng.integers(0, diff.size, size=(n_boot, diff.size))
    means = diff[idx].mean(axis=1)
    return (float(diff.mean()),
            float(np.percentile(means, 2.5)),
            float(np.percentile(means, 97.5)))


def summarize(df: pd.DataFrame) -> pd.DataFrame:
    """Per (delay, cost) cell: mean hours lost per posture, the winner, and
    MATCHED-PAIR differences (reactive vs each static posture) with 95%
    bootstrap CIs. Pairing is valid because the three postures share the same
    network and random stream within a trial."""
    metric = "weighted_service_hours_lost"
    out: list[dict] = []
    for (delay, cost), cell in df.groupby(["detection_delay", "cost_frac"]):
        wide = cell.pivot_table(index="trial", columns="posture",
                                values=metric)
        wide = wide.dropna()
        o, s, r = wide["open"].values, wide["static"].values, \
            wide["reactive"].values
        means = {"open": o.mean(), "static": s.mean(), "reactive": r.mean()}
        best_static_name = "open" if means["open"] <= means["static"] \
            else "static"
        best_static = np.minimum(o, s)
        d_static, lo_s, hi_s = _boot_ci(r - s)
        d_open, lo_o, hi_o = _boot_ci(r - o)
        d_best, lo_b, hi_b = _boot_ci(r - best_static)
        winner = min(means, key=means.get)
        out.append({
            "detection_delay": delay, "cost_frac": cost, "n": len(wide),
            "open": means["open"], "static": means["static"],
            "reactive": means["reactive"],
            "best_static": best_static.mean(),
            "best_static_name": best_static_name, "winner": winner,
            "reactive_minus_static": d_static, "rms_lo": lo_s, "rms_hi": hi_s,
            "reactive_minus_open": d_open, "rmo_lo": lo_o, "rmo_hi": hi_o,
            "reactive_minus_best_static": d_best,
            "rmb_lo": lo_b, "rmb_hi": hi_b,
            # reactive significantly beats BOTH static postures if the upper
            # CI of its paired difference vs each is below 0.
            "reactive_sig_best": bool(hi_b < 0),
        })
    return pd.DataFrame(out)


def make_figure(summary: pd.DataFrame, out_png: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import TwoSlopeNorm

    delays = sorted(summary["detection_delay"].unique())
    costs = sorted(summary["cost_frac"].unique())
    # margin[i, j] = reactive - best_static  (negative => reactive wins)
    margin = np.full((len(costs), len(delays)), np.nan)
    winner = np.empty((len(costs), len(delays)), dtype=object)
    for _, r in summary.iterrows():
        i = costs.index(r["cost_frac"])
        j = delays.index(r["detection_delay"])
        margin[i, j] = r["reactive_minus_best_static"]
        winner[i, j] = r["winner"]

    fig, ax = plt.subplots(figsize=(8, 5.5))
    vmax = float(np.nanmax(np.abs(margin))) or 1.0
    norm = TwoSlopeNorm(vmin=-vmax, vcenter=0.0, vmax=vmax)
    im = ax.imshow(margin, cmap="RdBu", norm=norm, aspect="auto",
                   origin="lower")
    ax.set_xticks(range(len(delays)))
    ax.set_xticklabels(delays)
    ax.set_yticks(range(len(costs)))
    ax.set_yticklabels([f"{c:.0%}" for c in costs])
    ax.set_xlabel("Detection delay (steps; larger = slower to see the attack)")
    ax.set_ylabel("Segmentation operational cost\n(fraction of clinical nodes)")
    ax.set_title("Reactive segmentation vs. best static posture\n"
                 "(blue = reactive wins; red = a static posture wins)")
    for i in range(len(costs)):
        for j in range(len(delays)):
            ax.text(j, i, winner[i, j][:4], ha="center", va="center",
                    fontsize=8, color="black")
    cb = fig.colorbar(im, ax=ax)
    cb.set_label("mean weighted service-hours lost:\nreactive − best static "
                 "(negative = reactive better)")
    fig.tight_layout()
    fig.savefig(out_png, dpi=150)
    fig.savefig(out_png.with_suffix(".pdf"))
    plt.close(fig)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--trials", type=int, default=120,
                    help="matched networks per (delay,cost) cell")
    ap.add_argument("--facility", default="regional_hospital")
    ap.add_argument("--profile", default="intermediate_capacity")
    ap.add_argument("--trigger", type=int, default=1)
    ap.add_argument("--hold", type=int, default=6)
    ap.add_argument("--out", default="outputs/adaptive")
    args = ap.parse_args()

    cfg = Config()
    cfg.validate()
    detection_delays = [1, 2, 3, 6, 12, 24]
    cost_fracs = [0.0, 0.15, 0.30, 0.45]
    entry_points = cfg.experiment.entry_points

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Running {len(detection_delays)}x{len(cost_fracs)} grid, "
          f"{args.trials} matched trials x 3 postures = "
          f"{len(detection_delays)*len(cost_fracs)*args.trials*3} sims ...")
    df = run_grid(cfg, facility=args.facility, profile=args.profile,
                  detection_delays=detection_delays, cost_fracs=cost_fracs,
                  trials=args.trials, entry_points=entry_points,
                  trigger=args.trigger, hold=args.hold)
    raw_path = out_dir / "adaptive_segmentation_raw.csv"
    df.to_csv(raw_path, index=False)

    summary = summarize(df)
    sum_path = out_dir / "adaptive_segmentation_summary.csv"
    summary.to_csv(sum_path, index=False)

    make_figure(summary, out_dir / "adaptive_segmentation_phase.png")

    # -- console report ------------------------------------------------
    pd.set_option("display.width", 120)
    pd.set_option("display.max_columns", 20)
    show = summary.copy()
    for c in ("open", "static", "reactive", "best_static",
              "reactive_minus_best_static", "rmb_lo", "rmb_hi"):
        show[c] = show[c].round(1)
    print("\n=== mean weighted service-hours lost by cell "
          "(matched pairs, n per cell) ===")
    print(show[["detection_delay", "cost_frac", "n", "open", "static",
                "reactive", "reactive_minus_best_static", "rmb_lo", "rmb_hi",
                "winner", "reactive_sig_best"]].to_string(index=False))
    n_react = int((summary["winner"] == "reactive").sum())
    n_sig = int(summary["reactive_sig_best"].sum())
    print(f"\nreactive is the point-estimate winner in {n_react}/"
          f"{len(summary)} cells; it beats BOTH static postures with a "
          f"95% CI clear of 0 in {n_sig}/{len(summary)} cells.")
    print(f"raw:     {raw_path}")
    print(f"summary: {sum_path}")
    print(f"figure:  {out_dir/'adaptive_segmentation_phase.png'}")


if __name__ == "__main__":
    main()
