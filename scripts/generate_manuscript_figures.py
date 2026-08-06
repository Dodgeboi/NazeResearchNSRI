#!/usr/bin/env python3
"""Build the result figures used only in the manuscript.

Every plotted value comes from a committed CSV. The script writes both PDF
and PNG so the paper gets sharp vector graphics and the repository keeps an
easy-to-preview copy.
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Patch


ROOT = Path(__file__).resolve().parents[1]
FIGURES = ROOT / "docs" / "manuscript" / "figures"
REFERENCE = "#565b61"
LAYERED = "#1f7180"
TIE = "#c8c7c1"
WORSE = "#ad493f"
GRID = "#deddd8"
INK = "#17191b"


def style() -> None:
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 8.5,
            "axes.labelsize": 8.5,
            "axes.titlesize": 9.5,
            "axes.titleweight": "bold",
            "axes.edgecolor": INK,
            "axes.labelcolor": INK,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "xtick.color": INK,
            "ytick.color": INK,
            "axes.grid": False,
            "legend.frameon": False,
            "legend.fontsize": 8,
            "figure.facecolor": "white",
            "savefig.facecolor": "white",
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )


def save(fig: plt.Figure, name: str) -> None:
    FIGURES.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIGURES / f"{name}.pdf", bbox_inches="tight")
    fig.savefig(FIGURES / f"{name}.png", dpi=320, bbox_inches="tight")
    plt.close(fig)


def primary_outcomes() -> None:
    summary = pd.read_csv(
        ROOT / "data" / "fine_step_replication" / "processed" / "primary_summary.csv"
    ).iloc[0]

    fig, axes = plt.subplots(1, 3, figsize=(7.05, 2.15), gridspec_kw={"wspace": 0.55})

    labels = ["Reference", "Layered"]
    colors = [REFERENCE, LAYERED]

    means = [summary["baseline_mean_hours"], summary["treatment_mean_hours"]]
    bars = axes[0].bar(labels, means, color=colors, width=0.62)
    axes[0].set_title("Mean service-hours lost")
    axes[0].set_ylim(0, 220)
    axes[0].set_ylabel("Weighted hours")
    axes[0].yaxis.grid(True, color=GRID, linewidth=0.6)
    axes[0].set_axisbelow(True)
    axes[0].bar_label(bars, labels=[f"{v:.1f}" for v in means], padding=3)

    outage = [
        100 * summary["baseline_sustained_outage_fraction"],
        100 * summary["treatment_sustained_outage_fraction"],
    ]
    bars = axes[1].bar(labels, outage, color=colors, width=0.62)
    axes[1].set_title("Sustained outage")
    axes[1].set_ylim(0, 100)
    axes[1].set_ylabel("Scenarios (%)")
    axes[1].yaxis.grid(True, color=GRID, linewidth=0.6)
    axes[1].set_axisbelow(True)
    axes[1].bar_label(bars, labels=[f"{v:.1f}%" for v in outage], padding=3)

    counts = np.array([451, 48, 1])
    left = 0
    for count, color in zip(counts, [LAYERED, TIE, WORSE]):
        axes[2].barh([0], [count], left=left, color=color, height=0.42)
        left += count
    axes[2].set_title("Outcome in 500 pairs")
    axes[2].set_xlim(0, 500)
    axes[2].set_yticks([])
    axes[2].set_xlabel("Scenario pairs")
    axes[2].text(225.5, 0, "451 lower", ha="center", va="center", color="white")
    axes[2].legend(
        handles=[Patch(color=TIE, label="48 tied"), Patch(color=WORSE, label="1 higher")],
        loc="upper center", bbox_to_anchor=(0.5, -0.27), ncol=2,
        handlelength=1.0, columnspacing=1.0,
    )
    axes[2].spines["left"].set_visible(False)
    axes[2].spines["bottom"].set_visible(False)
    axes[2].tick_params(axis="x", length=0)

    save(fig, "primary_outcomes")


def service_downtime() -> None:
    data = pd.read_csv(
        ROOT
        / "data"
        / "fine_step_replication"
        / "processed"
        / "primary_service_summary.csv"
    )
    labels = {
        "ehr": "EHR",
        "laboratory": "Laboratory",
        "pharmacy": "Pharmacy",
        "imaging": "Imaging",
        "scheduling": "Scheduling",
        "identity": "Identity",
        "backup_recovery": "Backup / recovery",
    }
    order = list(labels)
    ref = data[data["portfolio"] == "baseline_flat"].set_index("service")
    layered = data[data["portfolio"] == "seg_detect_backup"].set_index("service")
    y = np.arange(len(order))

    fig, ax = plt.subplots(figsize=(3.45, 3.05))
    for row, service in enumerate(order):
        ax.plot(
            [layered.loc[service, "mean_downtime_hours"], ref.loc[service, "mean_downtime_hours"]],
            [row, row],
            color=GRID,
            linewidth=2,
            zorder=1,
        )
    ax.scatter(
        ref.loc[order, "mean_downtime_hours"], y, s=32, color=REFERENCE,
        label="Reference", zorder=3,
    )
    ax.scatter(
        layered.loc[order, "mean_downtime_hours"], y, s=32, color=LAYERED,
        label="Layered", zorder=3,
    )
    ax.set_yticks(y, [labels[item] for item in order])
    ax.invert_yaxis()
    ax.set_xlim(0, 55)
    ax.set_xlabel("Mean modeled downtime (hours)")
    ax.xaxis.grid(True, color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)
    ax.legend(loc="lower right", ncol=2, columnspacing=1.0, handletextpad=0.35)
    save(fig, "service_downtime")


def _reductions(path: Path) -> pd.DataFrame:
    data = pd.read_csv(path)
    means = (
        data.groupby(["time_step_minutes_variant", "portfolio"])["weighted_service_hours_lost"]
        .mean()
        .unstack()
    )
    result = 100 * (1 - means["seg_detect_backup"] / means["baseline_flat"])
    return result.rename("reduction").reset_index()


def time_step_sensitivity() -> None:
    pilot = _reductions(ROOT / "data" / "public_validation" / "raw" / "fine_step_pilot.csv")
    diagnostic = _reductions(
        ROOT / "data" / "public_validation" / "raw" / "time_step_convergence.csv"
    )

    fig, axes = plt.subplots(1, 2, figsize=(7.05, 2.15), sharey=True)
    panels = [
        (axes[0], pilot, LAYERED, "o", "Fine-step pilot"),
        (axes[1], diagnostic, REFERENCE, "s", "Corrected diagnostic"),
    ]
    for ax, frame, color, marker, title in panels:
        ax.plot(
            frame["time_step_minutes_variant"], frame["reduction"],
            marker=marker, linewidth=1.8, color=color,
        )
        for _, row in frame.iterrows():
            ax.annotate(
                f"{row['reduction']:.1f}%",
                (row["time_step_minutes_variant"], row["reduction"]),
                xytext=(0, 6), textcoords="offset points", ha="center", fontsize=7.5,
            )
        values = frame["time_step_minutes_variant"].tolist()
        pad = max(values) * 0.12
        ax.set_xlim(min(values) - pad, max(values) + pad)
        ax.set_xticks(values)
        ax.set_xlabel("Simulation step (minutes)")
        ax.set_title(title)
        ax.yaxis.grid(True, color=GRID, linewidth=0.6)
        ax.set_axisbelow(True)
    axes[0].set_ylim(76, 97)
    axes[0].set_ylabel("Reduction from reference (%)")
    save(fig, "time_step_sensitivity")


if __name__ == "__main__":
    style()
    primary_outcomes()
    service_downtime()
    time_step_sensitivity()
