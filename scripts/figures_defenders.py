"""Figures for the defender study, from data/agentic/processed/.

Print figures for an IEEE two-column paper. Palette: validated categorical
slots (1-2 for unshielded/shielded, 1-3 for the three profiles; the third
fails 3:1 contrast, so every series also carries its own marker shape and a
legend). Two measures on different scales get two panels sharing one row
axis — never a second y-axis.
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "agentic" / "processed"
OUT = ROOT / "docs" / "aidc26" / "figures"

UNSHIELDED = "#2a78d6"   # categorical slot 1
SHIELDED = "#eb6834"     # categorical slot 2
INK = "#0b0b0b"
MUTED = "#52514e"
GRID = "#d9d8d4"

ROWS = [  # (condition, label) top to bottom
    ("passive", "Passive"),
    ("zone_lockdown", "Zone lockdown (playbook)"),
    ("micro_lockdown_upper_bound", "Micro lockdown (upper bound)"),
    ("disconnect", "Disconnect (playbook)"),
    ("q_containment_today", "Q: containment reward"),
    ("q_soft_today", "Q: soft penalty"),
    ("q_clinical_today", "Q: clinical reward"),
    ("passive_replicas", "Passive (replica estate)"),
    ("islands", "Islands (playbook)"),
    ("q_containment_replicas", "Q: containment (replicas)"),
    ("q_soft_replicas", "Q: soft (replicas)"),
    ("q_clinical_replicas", "Q: clinical (replicas)"),
]

plt.rcParams.update({
    "font.family": "serif", "font.size": 7.5, "axes.titlesize": 8,
    "axes.labelsize": 7.5, "xtick.labelsize": 7, "ytick.labelsize": 7,
    "axes.edgecolor": MUTED, "axes.labelcolor": INK, "xtick.color": MUTED,
    "ytick.color": MUTED, "axes.linewidth": 0.6, "pdf.fonttype": 42,
})


def _style(ax):
    ax.grid(axis="x", color=GRID, linewidth=0.5)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)


def containment_vs_clinical(summ: pd.DataFrame) -> None:
    pooled = summ[summ.profile == "pooled"].set_index("condition")
    fig, (left, right) = plt.subplots(1, 2, figsize=(7.16, 3.1), sharey=True)
    ys = list(range(len(ROWS)))[::-1]
    for (cond, _), y in zip(ROWS, ys):
        plain = pooled.loc[cond]
        shielded = (pooled.loc[f"{cond}_shielded"]
                    if f"{cond}_shielded" in pooled.index else None)
        for ax, col, scale in ((left, "spread", 100), (right, "hours", 1)):
            x0 = plain[col] * scale
            if shielded is not None:
                x1 = shielded[col] * scale
                ax.plot([x0, x1], [y, y], color=GRID, linewidth=1.2,
                        zorder=1)
                ax.scatter([x1], [y], marker="s", s=22, color=SHIELDED,
                           edgecolor="white", linewidth=0.8, zorder=3)
            ax.scatter([x0], [y], marker="o", s=24, color=UNSHIELDED,
                       edgecolor="white", linewidth=0.8, zorder=2)
    left.set_yticks(ys, [label for _, label in ROWS])
    left.axhline(4.5, color=GRID, linewidth=0.6, linestyle=(0, (2, 2)))
    right.axhline(4.5, color=GRID, linewidth=0.6, linestyle=(0, (2, 2)))
    left.set_xlabel("Nodes ever compromised (%)\nlower is better")
    right.set_xlabel("Weighted clinical service-hours lost\nlower is better")
    left.set_title("What autonomous-defence benchmarks score", loc="left",
                   color=INK)
    right.set_title("What the hospital loses", loc="left", color=INK)
    for ax in (left, right):
        _style(ax)
    handles = [
        plt.Line2D([], [], marker="o", linestyle="", color=UNSHIELDED,
                   markersize=5, label="Unshielded"),
        plt.Line2D([], [], marker="s", linestyle="", color=SHIELDED,
                   markersize=5, label="With dependency-closure shield")]
    fig.tight_layout(rect=(0, 0.06, 1, 1))
    # Below the panels: inside either one it would sit on data points.
    fig.legend(handles=handles, loc="lower center", ncol=2, frameon=False,
               fontsize=7, labelcolor=INK, bbox_to_anchor=(0.5, 0.0))
    _save(fig, "containment_vs_clinical")


PROFILE_STYLE = [  # categorical slots 1-3, validated all-pairs; + shape
    ("high_capacity", "High capacity", "#2a78d6", "o"),
    ("intermediate_capacity", "Intermediate", "#eb6834", "s"),
    ("resource_constrained", "Resource-constrained", "#1baf7a", "^"),
]


def shield_effect(con: pd.DataFrame) -> None:
    """Paired effect of the shield on clinical hours, per profile."""
    rows = con[(con.family == "shield_effect") & (con.profile != "pooled")]
    order = [c for c, _ in ROWS if c in set(rows.reference)]
    labels = dict(ROWS)
    fig, ax = plt.subplots(figsize=(3.5, 3.3))
    for y, cond in enumerate(order[::-1]):
        for k, (profile, plabel, color, marker) in enumerate(PROFILE_STYLE):
            r = rows[(rows.reference == cond) & (rows.profile == profile)]
            if r.empty:
                continue
            r = r.iloc[0]
            yy = y + (1 - k) * 0.24
            ax.hlines(yy, r.d_weighted_service_hours_lost_lo,
                      r.d_weighted_service_hours_lost_hi, color=color,
                      linewidth=1.1)
            ax.scatter([r.d_weighted_service_hours_lost], [yy], s=16,
                       marker=marker, color=color, edgecolor="white",
                       linewidth=0.6, zorder=3,
                       label=plabel if y == 0 else None)
    ax.axvline(0, color=MUTED, linewidth=0.7)
    ax.set_yticks(range(len(order)), [labels[c] for c in order[::-1]])
    ax.set_xlabel("Shielded − unshielded, weighted service-hours lost\n"
                  "(paired; 95% bootstrap interval; left of 0 = shield helps)")
    _style(ax)
    ax.legend(loc="upper center", bbox_to_anchor=(0.45, 1.13), ncol=3,
              frameon=False, fontsize=6.5, handletextpad=0.2,
              columnspacing=0.8, labelcolor=INK)
    fig.tight_layout()
    _save(fig, "shield_effect")


def rank_slope(ranks: dict) -> None:
    labels = dict(ROWS)
    a, b = ranks["order_by_containment"], ranks["order_by_clinical"]
    fig, ax = plt.subplots(figsize=(3.5, 3.0))
    highlight = {"disconnect", "q_containment_today"}
    for cond in a:
        y0, y1 = a.index(cond), b.index(cond)
        hot = cond in highlight
        ax.plot([0, 1], [y0, y1], color=SHIELDED if hot else GRID,
                linewidth=1.6 if hot else 1.0, marker="o", markersize=3.5,
                zorder=3 if hot else 1)
        ax.text(-0.04, y0, labels.get(cond, cond), ha="right", va="center",
                fontsize=6.5, color=INK if hot else MUTED)
        ax.text(1.04, y1, labels.get(cond, cond), ha="left", va="center",
                fontsize=6.5, color=INK if hot else MUTED)
    ax.set_xlim(-1.2, 2.2)
    ax.invert_yaxis()
    ax.set_xticks([0, 1], ["Rank by\ncontainment", "Rank by\nclinical hours"])
    ax.set_yticks([])
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    fig.tight_layout()
    _save(fig, "rank_slope")


def _save(fig, name: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / f"{name}.pdf", bbox_inches="tight")
    fig.savefig(OUT / f"{name}.png", dpi=220, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    summ = pd.read_csv(PROC / "defender_summary.csv")
    con = pd.read_csv(PROC / "paired_contrasts.csv")
    ranks = json.loads((PROC / "rank_reversal.json").read_text("utf-8"))
    containment_vs_clinical(summ)
    shield_effect(con)
    rank_slope(ranks)
    print(f"wrote figures to {OUT}")


if __name__ == "__main__":
    main()
