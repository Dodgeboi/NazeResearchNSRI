"""Generate the final comparison's manuscript values and explanatory figures."""
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch
import numpy as np
import pandas as pd
import yaml

from grrc.provenance import verify_manifest

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/final_comparison"
PROFILES = ["resource_constrained", "intermediate_capacity", "high_capacity"]
LABELS = ["Resource-constrained", "Intermediate", "High-capacity"]
PARAMETERS = [
    ("simulation_base_spread_rate", "Traversal rate"),
    ("simulation_patch_effectiveness", "Exploit patch effect"),
    ("simulation_patch_effectiveness_vendor", "Vendor patch effect"),
    ("simulation_identity_breach_multiplier", "Identity breach multiplier"),
    ("simulation_identity_control_coverage", "Identity coverage"),
    ("simulation_identity_control_effectiveness", "Identity effect"),
    ("simulation_rapid_isolation_success", "Isolation success"),
    ("simulation_restore_rate_fraction", "Restoration throughput"),
    ("simulation_false_positive_rate", "False-positive rate"),
    ("network_backup_isolation_lapse", "Backup isolation lapse"),
]
METHODS = [("hoeffding", "Hoeffding"), ("empirical_bernstein", "Empirical Bernstein"),
           ("paired_t_approx", "Paired $t$ (approx.)")]


def content():
    verify_manifest(DATA / "comparison_manifest.json")
    tables = {p.stem: pd.read_csv(p) for p in DATA.glob("*.csv")}
    regime, baseline, retained = [tables[k] for k in ["coefficient_regimes", "baseline_comparisons", "bound_retention"]]
    values, generated = {}, {}
    high = baseline[(baseline.profile == "high_capacity")]
    for method, prefix in [("hoeffding", "ComparisonHoeffding"),
        ("empirical_bernstein", "ComparisonBernstein"), ("paired_t_approx", "ComparisonT")]:
        g = high[high.method == method]
        best = g.loc[g.mean_benefit.idxmax()]
        values[prefix + "HighMargin"] = f"{best.margin:.2f}"
        values[prefix + "HighLower"] = f"{best.lower_benefit:.2f}"
    for radius, suffix in [(0, "Nominal"), (.5, "Half")]:
        values["ComparisonTPurchased" + suffix] = str(int(retained.query(
            "method == 'paired_t_approx' and radius == @radius").purchased_retained.sum()))
    values["CoefficientRegimes"] = str(len(regime))
    values["CoefficientBelowReference"] = str(int((regime.jaccard < regime.matched_jaccard_q025).sum()))
    r = regime.query("profile == 'resource_constrained' and parameter == 'simulation_patch_effectiveness' and side == 'high'").iloc[0]
    values["CoefficientPatchRemoved"] = str(int(r.removed))
    values["CoefficientPatchReference"] = str(int(r.original_frontier))
    spread = regime.query("profile == 'resource_constrained' and parameter == 'simulation_base_spread_rate' and side == 'high'").iloc[0]
    if spread.matched_fraction_at_most_regime_jaccard != 0:
        raise AssertionError("revise the statement that high traversal lies below every reference draw")
    for p, prefix in zip(PROFILES, ["Resource", "Intermediate", "High"]):
        r = regime[regime.profile == p]
        values["Coefficient"+prefix+"Min"] = f"{r.jaccard.min():.3f}"
        values["Coefficient"+prefix+"Max"] = f"{r.jaccard.max():.3f}"
    generated["comparison_numbers.tex"] = "% Generated; do not edit.\n" + "".join(
        "\\newcommand{\\"+key+"}{"+value+"}\n" for key, value in sorted(values.items()))

    def table(name, rows):
        generated[name + ".tex"] = "% Generated from the recorded final comparison.\n" + "".join(
            " & ".join(row) + " \\\\\n" for row in rows)

    rows = []
    for p, label in zip(PROFILES, LABELS):
        for method, method_label in METHODS:
            b = baseline[(baseline.profile == p) & (baseline.method == method)]
            best = b.loc[b.mean_benefit.idxmax()]
            r = retained[(retained.profile == p) & (retained.method == method)]
            rows.append([label, method_label, f"{best.margin:.2f}", str(int((b.lower_benefit > 0).sum())),
                str(int(r.loc[r.radius == 0, "purchased_retained"].iloc[0])),
                str(int(r.loc[r.radius == .5, "purchased_retained"].iloc[0]))])
    table("table_bound_comparison_rows", rows)
    rows = []
    for p, label in zip(PROFILES, LABELS):
        r = regime[regime.profile == p]
        rows.append([label, f"{r.jaccard.min():.3f}--{r.jaccard.max():.3f}",
            f"{r.iloc[0].matched_jaccard_q025:.3f}--{r.iloc[0].matched_jaccard_q975:.3f}",
            str(int((r.jaccard < r.matched_jaccard_q025).sum()))])
    table("table_coefficient_summary_rows", rows)
    config = yaml.safe_load((ROOT / "configs/multiobjective_portfolio.yaml").read_text(encoding="utf-8"))
    rows = []
    for parameter, label in PARAMETERS:
        section, field = parameter.split("_", 1)
        low, upper = config["parameter_uncertainty"][section][field]
        row = [label, f"{low:g}--{upper:g}"]
        for p in PROFILES:
            r = regime[(regime.profile == p) & (regime.parameter == parameter)].set_index("side")
            row.append(" / ".join(f"{r.loc[side, 'jaccard']:.3f}" for side in ["low", "high"]))
        rows.append(row)
    table("table_all_coefficients_rows", rows)
    return generated, {"comparison_regimes": regime, "comparison_subsets": tables["matched_subsets"]}


def figures(tables, folder):
    paths = []

    def save(fig, name):
        for suffix in ["pdf", "png"]:
            path = folder / (name + "." + suffix)
            fig.savefig(path, dpi=220, bbox_inches="tight", metadata={"Creator": "Matplotlib"})
            paths.append(path)
        plt.close(fig)

    regime = tables["comparison_regimes"]
    fig, axes = plt.subplots(1, 3, figsize=(7.05, 3.65), sharey=True)
    for ax, p, label in zip(axes, PROFILES, LABELS):
        r = regime[regime.profile == p]
        q = r.iloc[0]
        ax.axvspan(q.matched_jaccard_q025, q.matched_jaccard_q975, color="#eeeeee")
        ax.axvline(q.matched_jaccard_median, color="#888888", ls=":", lw=1)
        for side, offset, color, marker in [("low", -.13, "#00738a", "o"), ("high", .13, "#b85824", "s")]:
            v = r[r.side == side].set_index("parameter").loc[[v[0] for v in PARAMETERS], "jaccard"]
            ax.scatter(v, np.arange(10)+offset, c=color, marker=marker, s=16, label=side.capitalize()+" third", zorder=3)
        ax.set(xlim=(.38, 1.025), xticks=[.4, .6, .8, 1], title=label, xlabel="Frontier Jaccard")
        ax.set_yticks(range(10), [v[1] for v in PARAMETERS], fontsize=7)
        ax.grid(axis="y", alpha=.15)
    axes[0].invert_yaxis()
    axes[0].legend(loc="lower left", bbox_to_anchor=(0, -.29), ncol=2, fontsize=7, frameon=False)
    fig.subplots_adjust(left=.255, right=.99, top=.90, bottom=.18, wspace=.14)
    save(fig, "coefficient_frontiers")

    fig, ax = plt.subplots(figsize=(7.05, 4.4))
    ax.set(xlim=(0, 10), ylim=(0, 6.5)); ax.axis("off")

    def box(x, y, w, h, label, fill="#eaf3f5", size=8):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.04,rounding_size=0.07",
                     linewidth=.7, edgecolor="#48747d", facecolor=fill))
        ax.text(x+w/2, y+h/2, label, ha="center", va="center", fontsize=size)

    def arrow(start, end, rad=0, color="#48646d", style="-"):
        ax.add_patch(FancyArrowPatch(start, end, arrowstyle="-|>", mutation_scale=9,
            lw=.9, color=color, linestyle=style, connectionstyle=f"arc3,rad={rad}"))

    ax.text(0, 6.23, "A. Network and control pathways", weight="bold", fontsize=9)
    box(.05, 4.58, 2.35, 1.3, "Entry categories\nWorkstation; internet-facing\nPrivileged system; device\nVendor connection", size=7.5)
    box(3.05, 4.58, 3.4, 1.3, "Ten network zones\nWorkstations; EHR; lab; pharmacy\nImaging; devices; administration\nIdentity; backup; internet-facing", size=7.5)
    box(7.1, 4.58, 2.8, 1.3, "Pathway-specific controls\nExploit: patching\nCredential: identity protection\nVendor: partial patch effect", size=7.5)
    arrow((2.43, 5.2), (3, 5.2)); arrow((7.07, 5.2), (6.5, 5.2))
    ax.text(5, 4.27, "Segmentation changes allowed connections; detection and isolation limit active spread.", ha="center", fontsize=7.5)
    ax.text(0, 3.88, "B. Node lifecycle and recovery", weight="bold", fontsize=9)
    coords = [(.05, 2.72, 1.8), (2.36, 2.72, 1.43), (4.23, 2.72, 1.3), (5.99, 2.72, 1.22), (7.65, 2.72, 1.15)]
    labels = ["Healthy /\nvulnerable", "Compromised", "Detected", "Isolated", "Restoring"]
    for (x, y, w), label in zip(coords, labels): box(x, y, w, .65, label, size=7.5)
    for first, second in zip(coords[:-1], coords[1:]): arrow((first[0]+first[2]+.03, 3.045), (second[0]-.03, 3.045))
    box(7.65, 1.47, 1.15, .62, "Restored", size=7.5)
    arrow((8.225, 2.68), (8.225, 2.13))
    arrow((7.61, 1.78), (3.0, 2.67), rad=-.18)
    ax.text(4.45, 1.52, "Reinfection remains possible", fontsize=7.5,
            bbox=dict(facecolor="white", edgecolor="none", pad=1))
    arrow((.95, 3.41), (6.58, 3.41), rad=-.12, style="--")
    ax.text(3.95, 3.67, "Temporary false-positive isolation", ha="center", fontsize=7,
            bbox=dict(facecolor="white", edgecolor="none", pad=1))
    ax.text(9.03, 2.63, "Backups\nand capacity\nset recovery\nthroughput", fontsize=7, va="top")
    ax.text(0, 1.05, "C. Service consequences and decisions", weight="bold", fontsize=9)
    box(.05, .06, 4.33, .67, "Seven service availability traces\nFour clinical services define the outage ladder", size=7.5)
    box(5.1, .06, 4.8, .67, "Four outcome objectives + shared cost and burden\nCompare the entire candidate frontier", size=7.5)
    arrow((4.43, .39), (5.05, .39))
    fig.subplots_adjust(left=.01, right=.99, top=.99, bottom=.01)
    save(fig, "model_pathways")
    return paths
