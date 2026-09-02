#!/usr/bin/env python3
"""Generate publication figures for the paired multi-objective holdout."""

from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DISCOVERY = ROOT / "data" / "multiobjective" / "processed"
HOLDOUT = ROOT / "data" / "multiobjective" / "holdout_processed"
OUTPUT = ROOT / "results" / "figures"
PROFILE_ORDER = [
    "resource_constrained", "intermediate_capacity", "high_capacity"]
PROFILE_LABELS = {
    "resource_constrained": "Resource-constrained",
    "intermediate_capacity": "Intermediate-capacity",
    "high_capacity": "High-capacity",
}
COLORS = {
    "resource_constrained": "#B05A3C",
    "intermediate_capacity": "#D98E32",
    "high_capacity": "#0B6E75",
}


def _save(fig: plt.Figure, stem: str) -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUTPUT / f"{stem}.png", dpi=240, bbox_inches="tight")
    fig.savefig(OUTPUT / f"{stem}.pdf", bbox_inches="tight")
    plt.close(fig)


def frontier_tradeoffs() -> None:
    frontier = pd.read_csv(HOLDOUT / "portfolio_pareto_frontier.csv")
    stability = pd.read_csv(HOLDOUT / "portfolio_pareto_stability.csv")
    data = frontier.merge(stability, on=["profile", "portfolio"])
    fig, axes = plt.subplots(1, 3, figsize=(12.2, 4.1), sharey=False)
    for ax, profile in zip(axes, PROFILE_ORDER):
        group = data[data["profile"] == profile]
        stable = group["pareto_inclusion_probability"] >= 0.8
        scatter = ax.scatter(
            group["implementation_cost_points"],
            group["mean_hours_lost"],
            c=group["catastrophic_probability"],
            cmap="magma_r", vmin=0, vmax=1,
            s=30 + 90 * group["pareto_inclusion_probability"],
            edgecolors=np.where(stable, "black", "#9CA3AF"),
            linewidths=np.where(stable, 0.8, 0.4), alpha=0.9)
        efficient = group[group["pareto_efficient"] == 1].sort_values(
            "implementation_cost_points")
        ax.plot(efficient["implementation_cost_points"],
                efficient["mean_hours_lost"], color=COLORS[profile],
                linewidth=1.2, alpha=0.65, zorder=0)
        ax.axvline({"resource_constrained": 5,
                    "intermediate_capacity": 10,
                    "high_capacity": 15}[profile],
                   linestyle="--", color="#4B5563", linewidth=1)
        ax.set_title(PROFILE_LABELS[profile])
        ax.set_xlabel("Implementation cost (normalized points)")
        ax.set_ylabel("Mean weighted service-hours lost")
        ax.grid(alpha=0.18)
    colorbar = fig.colorbar(scatter, ax=axes, fraction=0.025, pad=0.03)
    colorbar.set_label("Modeled sustained-outage probability")
    fig.suptitle(
        "Held-out trade-offs: no portfolio minimizes every objective",
        fontsize=14, fontweight="bold")
    fig.text(0.5, -0.02,
             "Dashed lines are declared profile budgets; point size is "
             "bootstrap Pareto-inclusion probability.",
             ha="center", fontsize=9)
    _save(fig, "multiobjective_holdout_frontier")


def benchmark_comparison() -> None:
    data = pd.read_csv(HOLDOUT / "portfolio_benchmark_comparison.csv")
    strategy_order = [
        "flat_reference", "budget_efficiency_heuristic",
        "layered_heuristic", "maximum_control_stack"]
    labels = {
        "flat_reference": "Flat reference",
        "budget_efficiency_heuristic": "Budget-efficiency heuristic",
        "layered_heuristic": "Layered heuristic",
        "maximum_control_stack": "Maximum-control stack",
    }
    fig, axes = plt.subplots(1, 3, figsize=(12.2, 4.7), sharey=False)
    for ax, profile in zip(axes, PROFILE_ORDER):
        group = (data[data["profile"] == profile]
                 .set_index("benchmark_strategy").loc[strategy_order]
                 .reset_index())
        y = np.arange(len(group))
        colors = np.where(group["within_profile_budget"] == 1,
                          COLORS[profile], "#B8B8B8")
        ax.barh(y, group["mean_hours_lost"], color=colors, alpha=0.88)
        ax.scatter(group["tail_hours_lost_cvar90"], y,
                   marker="D", color="#1F2937", s=25,
                   label="CVaR90 tail" if profile == PROFILE_ORDER[0] else None)
        ax.set_yticks(y, [labels[name] for name in strategy_order], fontsize=8)
        ax.invert_yaxis()
        ax.set_title(PROFILE_LABELS[profile])
        ax.set_xlabel("Weighted service-hours lost")
        ax.grid(axis="x", alpha=0.18)
    axes[0].legend(frameon=False, fontsize=8, loc="lower right")
    fig.suptitle(
        "Held-out benchmark performance and tail disruption",
        fontsize=14, fontweight="bold")
    fig.text(0.5, -0.02,
             "Gray bars exceed the profile's declared normalized budget; "
             "diamonds show conditional mean loss in the worst 10% of trials.",
             ha="center", fontsize=9)
    fig.tight_layout(rect=(0, 0.03, 1, 0.94))
    _save(fig, "multiobjective_holdout_benchmarks")


def discovery_holdout_survival() -> None:
    discovery = pd.read_csv(DISCOVERY / "portfolio_pareto_frontier.csv")
    holdout = pd.read_csv(HOLDOUT / "portfolio_pareto_frontier.csv")
    joined = holdout[["profile", "portfolio", "pareto_efficient"]].merge(
        discovery[["profile", "portfolio", "pareto_efficient"]],
        on=["profile", "portfolio"], suffixes=("_holdout", "_discovery"))
    discovery_front = joined[joined["pareto_efficient_discovery"] == 1]
    summary = (discovery_front.groupby("profile")
               ["pareto_efficient_holdout"]
               .agg(n_discovery_frontier="size", n_survived="sum")
               .reindex(PROFILE_ORDER).reset_index())
    summary["survival_fraction"] = (
        summary["n_survived"] / summary["n_discovery_frontier"])
    fig, ax = plt.subplots(figsize=(7.4, 4.5))
    bars = ax.bar(
        [PROFILE_LABELS[p] for p in summary["profile"]],
        100 * summary["survival_fraction"],
        color=[COLORS[p] for p in summary["profile"]])
    for bar, (_, row) in zip(bars, summary.iterrows()):
        ax.text(bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 2,
                f"{int(row.n_survived)}/{int(row.n_discovery_frontier)}",
                ha="center", fontsize=10)
    ax.set_ylim(0, 108)
    ax.set_ylabel("Discovery-frontier candidates surviving holdout (%)")
    ax.set_title("Frontier survival on 150 fresh paired scenarios",
                 fontsize=13, fontweight="bold")
    ax.grid(axis="y", alpha=0.18)
    fig.tight_layout()
    _save(fig, "multiobjective_discovery_holdout_survival")


if __name__ == "__main__":
    plt.style.use("seaborn-v0_8-whitegrid")
    frontier_tradeoffs()
    benchmark_comparison()
    discovery_holdout_survival()
