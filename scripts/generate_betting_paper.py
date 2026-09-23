"""Generate the betting-bound comparison's manuscript values and figure.

Reads only the committed betting-bounds tables (after verifying their manifest)
and emits generated macros, a four-family comparison table, and one figure. The
three frozen families are recomputed inside the betting analysis on the same
contrasts, so this table is self-contained.
"""
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from grrc.provenance import verify_manifest

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/betting_bounds"
PROFILES = ["resource_constrained", "intermediate_capacity", "high_capacity"]
LABELS = ["Resource-constrained", "Intermediate", "High-capacity"]
METHODS = [("hoeffding", "Hoeffding"), ("empirical_bernstein", "Empirical Bernstein"),
           ("betting", "Betting"), ("paired_t_approx", "Paired $t$ (approx.)")]


def content():
    verify_manifest(DATA / "betting_bounds_manifest.json")
    margins = pd.read_csv(DATA / "bound_margins.csv")
    baseline = pd.read_csv(DATA / "bound_retention.csv")
    contrasts = pd.read_csv(DATA / "baseline_comparisons.csv")
    loss = margins[margins.objective == "mean_loss"]
    values = {}
    # Headline high-capacity best-versus-baseline margins, one macro per family.
    high = contrasts[contrasts.profile == "high_capacity"]
    for method, prefix in [("hoeffding", "BettingHoeffdingHigh"),
                           ("empirical_bernstein", "BettingBernsteinHigh"),
                           ("betting", "BettingHigh"), ("paired_t_approx", "BettingApproxHigh")]:
        g = high[high.method == method]
        best = g.loc[g.mean_benefit.idxmax()]
        values[prefix + "Margin"] = f"{best.margin:.2f}"
    # Smallest and largest betting mean-loss margin across the three profiles.
    betting = loss[loss.method == "betting"]
    values["BettingMinMargin"] = f"{betting.minimum.min():.2f}"
    values["BettingMaxMinMargin"] = f"{betting.minimum.max():.2f}"
    values["BettingBernsteinFloor"] = f"{loss[loss.method == 'empirical_bernstein'].minimum.min():.2f}"
    # Purchased portfolios each screen certifies at nominal and half-radius prices.
    for radius, suffix in [(0.0, "Nominal"), (0.5, "Half")]:
        rows = baseline.query("method == 'betting' and radius == @radius")
        values["BettingPurchased" + suffix] = str(int(rows.purchased_retained.sum()))
    for method, prefix in [("empirical_bernstein", "BettingBernsteinPurchased"),
                           ("paired_t_approx", "BettingApproxPurchased")]:
        rows = baseline.query("method == @method and radius == 0.0")
        values[prefix + "Nominal"] = str(int(rows.purchased_retained.sum()))
    values["BettingResourcePurchased"] = str(int(baseline.query(
        "method == 'betting' and radius == 0.0 and profile == 'resource_constrained'"
    ).purchased_retained.iloc[0]))
    generated = {"betting_numbers.tex": "% Generated; do not edit. Finite-sample, within-model, retrospective.\n"
                 + "".join("\\newcommand{\\" + key + "}{" + value + "}\n"
                           for key, value in sorted(values.items()))}

    rows = []
    for profile, label in zip(PROFILES, LABELS):
        for method, method_label in METHODS:
            contrast = contrasts[(contrasts.profile == profile) & (contrasts.method == method)]
            best = contrast.loc[contrast.mean_benefit.idxmax()]
            retain = baseline[(baseline.profile == profile) & (baseline.method == method)]
            rows.append([label, method_label, f"{best.margin:.2f}",
                         str(int((contrast.lower_benefit > 0).sum())),
                         str(int(retain.loc[retain.radius == 0.0, "purchased_retained"].iloc[0])),
                         str(int(retain.loc[retain.radius == 0.5, "purchased_retained"].iloc[0]))])
    generated["table_betting_rows.tex"] = "% Generated from the recorded betting comparison.\n" + "".join(
        " & ".join(row) + " \\\\\n" for row in rows)
    return generated, {"betting_margins": loss}


def figures(tables, folder):
    paths = []

    def save(fig, name):
        for suffix in ("pdf", "png"):
            path = folder / (name + "." + suffix)
            fig.savefig(path, dpi=200, bbox_inches="tight", metadata={"Creator": "Matplotlib"})
            paths.append(path)
        plt.close(fig)

    loss = tables["betting_margins"]
    order = ["hoeffding", "empirical_bernstein", "betting", "paired_t_approx"]
    names = ["Hoeffding", "Emp. Bernstein", "Betting", "Paired t"]
    colors = ["#9aa7ad", "#00738a", "#b85824", "#c9c15a"]
    fig, ax = plt.subplots(figsize=(7.05, 2.9))
    width = 0.2
    x = np.arange(len(PROFILES))
    for k, (method, color) in enumerate(zip(order, colors)):
        heights = [loss[(loss.profile == p) & (loss.method == method)].minimum.iloc[0] for p in PROFILES]
        ax.bar(x + (k - 1.5) * width, heights, width, color=color, label=names[k])
    ax.set(xticks=x, ylabel="Smallest mean-loss margin\n(weighted hours)")
    ax.set_xticklabels(LABELS)
    ax.legend(fontsize=7, frameon=False, ncol=4, loc="upper center", bbox_to_anchor=(0.5, 1.16))
    ax.grid(axis="y", alpha=0.2)
    save(fig, "betting_comparison")
    return paths
