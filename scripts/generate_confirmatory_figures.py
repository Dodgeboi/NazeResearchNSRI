#!/usr/bin/env python3
"""Publication figures for the full-space confirmatory study.

Four figures, each earning its place by carrying an argument the prose cannot
make as compactly:

1. ``confirmatory_frontier`` — the cost/disruption trade-off per profile,
   with Monte Carlo error bars and full-space frontier membership marked.
2. ``full_space_vs_finalist`` — the methodological headline: how many
   candidates look efficient only because their dominator was never
   evaluated.
3. ``clinical_outage_bimodality`` — why the choice of *k* is not
   load-bearing, and why that is a model artifact rather than a reassurance.
4. ``external_validation_scorecard`` — what the frozen benchmarks say,
   including everything the model cannot address.

Design notes. Small multiples by profile, so identity is carried by panel
position and title rather than by color alone; the categorical hues are
redundant reinforcement. The three hues are slots 1-3 of a palette validated
for all-pairs colour-vision separation (worst CVD delta-E 9.2, worst
normal-vision 24.0 on a light surface). One y-axis per panel, never two.
Marks are thin, grids recessive, and labels selective.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D

ROOT = Path(__file__).resolve().parents[1]
CONFIRM = ROOT / "data" / "multiobjective" / "confirmatory"
DISCOVERY = ROOT / "data" / "multiobjective" / "discovery"
OUTPUT = ROOT / "results" / "figures"

PROFILE_ORDER = ["resource_constrained", "intermediate_capacity",
                 "high_capacity"]
PROFILE_LABELS = {
    "resource_constrained": "Resource-constrained",
    "intermediate_capacity": "Intermediate-capacity",
    "high_capacity": "High-capacity",
}
# Slots 1-3 of the validated categorical order (blue, orange, aqua).
SERIES = {
    "resource_constrained": "#2a78d6",
    "intermediate_capacity": "#eb6834",
    "high_capacity": "#1baf7a",
}
INK = "#0b0b0b"
INK_SECONDARY = "#52514e"
INK_MUTED = "#8a8985"
GRID = "#e3e3e0"
SURFACE = "#fcfcfb"


def style_axes(ax: plt.Axes) -> None:
    """Recessive grid and axes; the data carries the emphasis."""
    ax.set_facecolor(SURFACE)
    ax.grid(True, color=GRID, linewidth=0.6, zorder=0)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
        ax.spines[side].set_linewidth(0.8)
    ax.tick_params(colors=INK_SECONDARY, labelsize=8, length=3, width=0.8)


def save(fig: plt.Figure, stem: str) -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    fig.patch.set_facecolor(SURFACE)
    fig.savefig(OUTPUT / f"{stem}.png", dpi=240, bbox_inches="tight",
                facecolor=SURFACE)
    fig.savefig(OUTPUT / f"{stem}.pdf", bbox_inches="tight",
                facecolor=SURFACE)
    plt.close(fig)
    print(f"wrote {stem}.pdf / .png")


# ---------------------------------------------------------------------------

def frontier(summary: pd.DataFrame, errors: pd.DataFrame,
             comparison: pd.DataFrame, cfg_budgets: dict) -> None:
    """Cost against mean disruption, with the frontier and its error bars."""
    data = summary.merge(errors, on=["profile", "portfolio"]).merge(
        comparison[["profile", "portfolio", "pareto_full_space"]],
        on=["profile", "portfolio"])

    fig, axes = plt.subplots(1, 3, figsize=(11.4, 3.7))
    for ax, profile in zip(axes, PROFILE_ORDER):
        style_axes(ax)
        group = data[data["profile"] == profile]
        if group.empty:
            continue
        colour = SERIES[profile]
        efficient = group["pareto_full_space"] == 1

        ax.errorbar(
            group.loc[~efficient, "implementation_cost_points"],
            group.loc[~efficient, "mean_hours_lost"],
            yerr=group.loc[~efficient, "mean_hours_lost_se"],
            fmt="o", markersize=3.2, linewidth=0, elinewidth=0.6,
            color=INK_MUTED, alpha=0.45, zorder=2, capsize=0)

        front = group[efficient].sort_values("implementation_cost_points")
        ax.plot(front["implementation_cost_points"], front["mean_hours_lost"],
                color=colour, linewidth=2.0, zorder=3, solid_capstyle="round")
        ax.errorbar(
            front["implementation_cost_points"], front["mean_hours_lost"],
            yerr=front["mean_hours_lost_se"],
            fmt="o", markersize=5.0, linewidth=0, elinewidth=0.9,
            color=colour, markeredgecolor=SURFACE, markeredgewidth=1.2,
            zorder=4, capsize=0)

        budget = cfg_budgets.get(profile)
        if budget is not None:
            ax.axvline(budget, color=INK_SECONDARY, linewidth=1.0,
                       linestyle=(0, (4, 3)), zorder=1)
            ax.annotate("declared budget", xy=(budget, ax.get_ylim()[1]),
                        xytext=(3, -8), textcoords="offset points",
                        fontsize=7, color=INK_SECONDARY,
                        va="top", ha="left", rotation=90)

        ax.set_title(f"{PROFILE_LABELS[profile]}\n"
                     f"{len(group)} candidates, {int(efficient.sum())} "
                     "non-dominated",
                     fontsize=9.5, color=INK, loc="left", pad=8)
        ax.set_xlabel("Implementation cost (normalized points)",
                      fontsize=8.5, color=INK_SECONDARY)
    axes[0].set_ylabel("Mean weighted service-hours lost",
                       fontsize=8.5, color=INK_SECONDARY)

    handles = [
        Line2D([], [], color=INK_MUTED, marker="o", markersize=4,
               linewidth=0, alpha=0.6, label="Dominated candidate"),
        Line2D([], [], color=SERIES["resource_constrained"], marker="o",
               markersize=5.5, linewidth=2.0,
               label="Full-space Pareto frontier"),
        Line2D([], [], color=INK_SECONDARY, linewidth=1.0,
               linestyle=(0, (4, 3)), label="Declared profile budget"),
    ]
    fig.legend(handles=handles, loc="lower center", ncol=3, frameon=False,
               fontsize=8.5, bbox_to_anchor=(0.5, -0.10),
               labelcolor=INK_SECONDARY)
    fig.tight_layout()
    save(fig, "confirmatory_frontier")


def full_space_vs_finalist(comparison: pd.DataFrame) -> None:
    """The methodological headline, as a grouped bar per profile."""
    rows = []
    for profile in PROFILE_ORDER:
        group = comparison[comparison["profile"] == profile]
        if group.empty:
            continue
        rows.append({
            "profile": profile,
            "evaluated": len(group),
            "labelled_finalist": int(group["is_frozen_finalist"].sum()),
            "full_space_frontier": int(group["pareto_full_space"].sum()),
            "finalist_only_frontier": int(group["pareto_finalist_only"].sum()),
            "artifacts": int(group["finalist_only_artifact"].sum()),
        })
    frame = pd.DataFrame(rows)

    fig, axes = plt.subplots(1, 3, figsize=(11.4, 3.5))
    categories = ["Evaluated\ncandidates", "Labelled\nfinalists",
                  "Frontier within\nfinalists only", "Frontier over\nfull space"]
    keys = ["evaluated", "labelled_finalist", "finalist_only_frontier",
            "full_space_frontier"]
    for ax, (_, row) in zip(axes, frame.iterrows()):
        style_axes(ax)
        colour = SERIES[row["profile"]]
        values = [row[key] for key in keys]
        positions = np.arange(len(values))
        # A 2px surface gap between adjacent fills.
        ax.bar(positions, values, width=0.68, color=colour,
               edgecolor=SURFACE, linewidth=2.0, zorder=3)
        for position, value in zip(positions, values):
            ax.annotate(f"{value:,}", xy=(position, value),
                        xytext=(0, 3), textcoords="offset points",
                        ha="center", fontsize=8.5, color=INK)
        ax.set_xticks(positions)
        ax.set_xticklabels(categories, fontsize=7.5, color=INK_SECONDARY)
        ax.set_ylim(0, max(values) * 1.22)
        title = f"{PROFILE_LABELS[row['profile']]}"
        if row["artifacts"]:
            title += (f"\n{row['artifacts']} finalist-only artifact"
                      f"{'s' if row['artifacts'] != 1 else ''}")
        else:
            title += "\nno finalist-only artifact"
        ax.set_title(title, fontsize=9.5, color=INK, loc="left", pad=8)
    axes[0].set_ylabel("Candidates", fontsize=8.5, color=INK_SECONDARY)
    fig.tight_layout()
    save(fig, "full_space_vs_finalist")


def bimodality(raw_path: Path, threshold_steps: int) -> None:
    """Why k is not load-bearing — and why that is an artifact."""
    from grrc.endpoints import max_streak_column
    from grrc.enums import CLINICAL_SERVICES

    columns = [max_streak_column(s) for s in CLINICAL_SERVICES] + ["profile"]
    raw = pd.read_csv(raw_path, usecols=columns)
    qualifying = sum(
        (raw[max_streak_column(s)] > threshold_steps).astype(int)
        for s in CLINICAL_SERVICES)

    fig, ax = plt.subplots(figsize=(6.4, 3.4))
    style_axes(ax)
    counts = [int((qualifying == k).sum()) for k in range(5)]
    total = sum(counts)
    positions = np.arange(5)
    # One series, one colour: the categories are ordered counts, and the
    # height already encodes magnitude.
    ax.bar(positions, counts, width=0.7, color=SERIES["resource_constrained"],
           edgecolor=SURFACE, linewidth=2.0, zorder=3)
    for position, value in zip(positions, counts):
        ax.annotate(f"{value:,}\n{value / total:.1%}", xy=(position, value),
                    xytext=(0, 4), textcoords="offset points", ha="center",
                    fontsize=8, color=INK)
    ax.set_xticks(positions)
    ax.set_xticklabels(["0", "1", "2", "3", "4"], fontsize=9,
                       color=INK_SECONDARY)
    ax.set_xlabel("Clinical services with an outage exceeding the threshold",
                  fontsize=8.5, color=INK_SECONDARY)
    ax.set_ylabel("Trials", fontsize=8.5, color=INK_SECONDARY)
    ax.set_ylim(0, max(counts) * 1.28)
    middle = total - counts[0] - counts[4]
    ax.set_title(
        "Clinical outage is near-binary within the model\n"
        f"only {middle:,} of {total:,} trials ({middle / total:.1%}) fall "
        "between none and all four",
        fontsize=9.5, color=INK, loc="left", pad=8)
    fig.tight_layout()
    save(fig, "clinical_outage_bimodality")


def validation_scorecard(report: dict) -> None:
    """What the frozen benchmarks say, including what cannot be answered."""
    order = ["pass", "consistent", "fail", "not_scored", "not_addressable"]
    label = {
        "pass": "Scored: passes",
        "consistent": "Scored: consistent",
        "fail": "Scored or comparable: fails",
        "not_scored": "Not scoreable (construct mismatch)",
        "not_addressable": "Not addressable (no such output)",
    }
    # Status-like meaning, so status ink rather than categorical series hues.
    colour = {
        "pass": "#008300", "consistent": "#008300", "fail": "#e34948",
        "not_scored": INK_MUTED, "not_addressable": INK_MUTED,
    }

    verdicts: list[tuple[str, str]] = []
    for entry in report["benchmarks"]:
        verdict = entry["verdict"]
        if verdict == "scored":
            verdict = entry.get("scoring", {}).get("computed_verdict", "fail")
        verdicts.append((entry["id"], verdict))

    counts = {key: sum(1 for _, v in verdicts if v == key) for key in order}
    counts = {k: v for k, v in counts.items() if v}

    fig, ax = plt.subplots(figsize=(7.2, 2.6))
    style_axes(ax)
    ax.grid(False)
    left = 0.0
    for key, value in counts.items():
        ax.barh([0], [value], left=left, height=0.5, color=colour[key],
                edgecolor=SURFACE, linewidth=2.0, zorder=3)
        ax.annotate(f"{label[key]}\n{value}", xy=(left + value / 2, 0),
                    xytext=(0, -30), textcoords="offset points",
                    ha="center", va="top", fontsize=8, color=INK_SECONDARY)
        left += value
    ax.set_xlim(0, left)
    ax.set_ylim(-1.4, 0.6)
    ax.set_yticks([])
    ax.set_xticks(range(0, int(left) + 1))
    ax.set_xlabel("Frozen external benchmarks", fontsize=8.5,
                  color=INK_SECONDARY)
    ax.set_title(
        f"Of {len(verdicts)} frozen benchmarks, "
        f"{counts.get('fail', 0) + counts.get('consistent', 0) + counts.get('pass', 0)}"
        " could be scored or directly compared\n"
        "the rest have no counterpart output: one facility, 72 hours, "
        "binary service availability",
        fontsize=9.5, color=INK, loc="left", pad=8)
    fig.tight_layout()
    save(fig, "external_validation_scorecard")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config",
                        default="configs/multiobjective_portfolio.yaml")
    parser.add_argument("--stage-dir", default=str(CONFIRM))
    args = parser.parse_args()

    from grrc.config import load_config
    cfg = load_config(args.config)
    stage = Path(args.stage_dir)

    summary = pd.read_csv(stage / "portfolio_objective_summary.csv")
    errors = pd.read_csv(stage / "portfolio_monte_carlo_error.csv")
    comparison_path = stage / "portfolio_full_space_vs_finalist.csv"
    budgets = {name: profile.budget
               for name, profile in cfg.profiles.items()}

    if comparison_path.exists():
        comparison = pd.read_csv(comparison_path)
        frontier(summary, errors, comparison, budgets)
        full_space_vs_finalist(comparison)
    else:
        print(f"skipping frontier figures: {comparison_path} not found")

    raw = stage / "multiobjective_confirmatory_results.csv"
    if not raw.exists():
        raw = DISCOVERY / "discovery_results.csv"
    bimodality(raw, cfg.simulation.sustained_outage_service_steps)

    validation = stage / "external_validation.json"
    if validation.exists():
        validation_scorecard(
            json.loads(validation.read_text(encoding="utf-8")))
    else:
        print(f"skipping scorecard: {validation} not found")


if __name__ == "__main__":
    main()
