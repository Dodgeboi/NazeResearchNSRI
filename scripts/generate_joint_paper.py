"""Generated manuscript values and figures for joint stability and coverage."""
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from grrc.provenance import verify_manifest

ROOT = Path(__file__).resolve().parents[1]
JOINT = ROOT/"data/joint_stability"
CIPHER = ROOT/"data/cipher/processed"
PROFILES = ["resource_constrained", "intermediate_capacity", "high_capacity"]
LABELS = ["Resource-constrained", "Intermediate", "High-capacity"]


def content():
    verify_manifest(JOINT/"joint_manifest.json")
    verify_manifest(CIPHER/"coverage_manifest.json")
    point = pd.read_csv(JOINT/"point_retention.csv")
    boot = pd.read_csv(JOINT/"bootstrap_summary.csv")
    population = pd.read_csv(JOINT/"population_retention.csv")
    c = pd.read_csv(CIPHER/"coverage_summary.csv").iloc[0]
    counts = pd.read_csv(CIPHER/"category_counts.csv")
    macros = {}
    for region, suffix in [("monotone", ""), ("positive_gaps", "Floored")]:
        mask = (point.price_region == region) & (point.radius == .5)
        macros["JointRetained"+suffix] = str(int(point.loc[mask, "guaranteed"].sum()))
        mask = (boot.price_region == region) & (boot.radius == .5)
        macros["JointFrequent"+suffix] = str(int(boot.loc[mask, "original_candidates_at_least_95pct"].sum()))
        mask = (population.price_region == region) & (population.radius == .5) & (population.alpha == .05)
        macros["JointPopulation"+suffix] = str(int(population.loc[mask, "guaranteed"].sum()))
    q = population.iloc[0]
    q95 = population[population.alpha == .05].iloc[0]
    macros.update(JointMeanFamily=f"{int(q.family_size):,}",
        JointLossBound=f"{q.loss_bound:.1f}", JointLossWidth=f"{q95.loss_difference_halfwidth:.1f}",
        JointBinaryWidth=f"{100*q95.binary_difference_halfwidth:.1f}",
        CipherRecords=str(int(c.records)), CipherReferences=str(int(c.reference_links)),
        CipherAbsent=str(int(c.absent_service_records)), CipherAbsentPercent=f"{100*c.absent_service_share:.1f}",
        CipherBeyond=str(int(c.beyond_horizon_records)), CipherBeyondPercent=f"{100*c.beyond_horizon_share:.1f}",
        CipherAbsentLOO=f"{100*c.absent_service_share_leave_one_reference_min:.1f}--{100*c.absent_service_share_leave_one_reference_max:.1f}",
        CipherBeyondLOO=f"{100*c.beyond_horizon_share_leave_one_reference_min:.1f}--{100*c.beyond_horizon_share_leave_one_reference_max:.1f}")
    generated = {"joint_numbers.tex": "% Generated; do not edit.\n" + "".join(
        "\\newcommand{\\"+k+"}{"+v+"}\n" for k, v in sorted(macros.items()))}
    def table(name, comment, rows):
        generated[name+".tex"] = "% "+comment+"\n" + "".join(
            " & ".join(row) + " \\\\\n" for row in rows)
    rows = []
    for profile, label in zip(PROFILES, LABELS):
        row = [label]
        for region in ["monotone", "positive_gaps"]:
            pp = point.query("profile == @profile and price_region == @region and radius == .5").iloc[0]
            bb = boot.query("profile == @profile and price_region == @region and radius == .5").iloc[0]
            row += [str(int(pp.guaranteed)), str(int(bb.original_candidates_at_least_95pct))]
        rows.append(row)
    table("table_joint_rows", "Radius 0.50. Point G and original certificates retained in at least 95% of resamples.", rows)
    rows = []
    for category, key in [("Represented service", "represented digital service"),
        ("Absent explicit service", "absent explicit service"), ("Unspecified", "unspecified")]:
        x = counts[(counts.subset == "all_records") & (counts.category == "coverage") & (counts.label == key)].iloc[0]
        rows.append([category, str(int(x.records)), str(int(x.reference_links)), f"{100*x.record_share:.1f}"])
    table("table_cipher_rows", "Coded records, not independent incidents. References overlap across rows.", rows)
    rows = []
    for radius in sorted(point.radius.unique()):
        row = [f"{100*radius:g}"]
        for region in ["monotone", "positive_gaps"]:
            pp = point.query("price_region == @region and radius == @radius").set_index("profile").loc[PROFILES]
            bb = boot.query("price_region == @region and radius == @radius").set_index("profile").loc[PROFILES]
            row += ["/".join(str(int(v)) for v in pp.guaranteed),
                    "/".join(str(int(v)) for v in bb.original_candidates_at_least_95pct)]
        rows.append(row)
    table("table_joint_all_rows", "All planned radii, entries R/I/H.", rows)
    return generated, {"joint_point": point, "joint_boot": boot}


def figures(tables, folder):
    point, boot = tables["joint_point"], tables["joint_boot"]
    fig, axes = plt.subplots(1, 2, figsize=(7.05, 2.65))
    colors = ["#00738a", "#b85824", "#694c91"]
    for profile, label, color in zip(PROFILES, LABELS, colors):
        for region, style, marker in [("monotone", "-", "o"), ("positive_gaps", "--", "s")]:
            p = point[(point.profile == profile) & (point.price_region == region)]
            b = boot[(boot.profile == profile) & (boot.price_region == region)]
            axes[0].plot(100*p.radius, p.guaranteed, style, marker=marker, ms=3,
                         color=color, label=label if region == "monotone" else None)
            axes[1].plot(100*b.radius, b.original_candidates_at_least_95pct,
                         style, marker=marker, ms=3, color=color)
    for ax in axes:
        ax.set(xlabel="Component tariff radius (%)", xticks=[0, 10, 25, 50, 75], ylim=(0, 45))
        ax.grid(axis="y", alpha=.18)
    axes[0].set(ylabel="Guaranteed portfolios", title="A. Original scenario bank")
    axes[1].set(ylabel="Original certificates retained", title="B. At least 95% of resamples")
    axes[0].legend(fontsize=7, frameon=False)
    axes[1].text(.02, .96, "Solid: monotone prices\nDashed: positive upgrade floors",
                 transform=axes[1].transAxes, va="top", fontsize=7)
    fig.tight_layout()
    paths = []
    for suffix in ["pdf", "png"]:
        path = folder/("joint_stability."+suffix)
        fig.savefig(path, dpi=220, bbox_inches="tight", metadata={"Creator": "Matplotlib"})
        paths.append(path)
    plt.close(fig)
    return paths
