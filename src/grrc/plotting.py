"""Publication-quality figures (matplotlib only).

Design rules applied throughout (from the project's viz style guide):
  * ordered categories (capacity profiles) use an ordinal single-hue blue
    ramp (light -> dark = lower -> higher capacity), validated palette;
  * the heatmap uses a one-hue sequential blue ramp with in-cell labels;
  * bars start at zero; no dual axes; recessive grid; direct labels where
    they help; legends whenever >= 2 series;
  * every figure exports PNG (300 dpi) + PDF + its underlying data as CSV
    so all plotted numbers are traceable.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap

from .config import Config
from .enums import Zone
from .statistics import bootstrap_ci
from .utilities import (ensure_dirs, resolve_path, setup_logging, trial_rng,
                        write_csv)

# --- validated palette (reference instance, light mode) -------------------
INK = "#0b0b0b"
INK_SECONDARY = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
BASELINE = "#c3c2b7"
SURFACE = "#ffffff"

#: Ordinal ramp for the three capacity profiles (light->dark = low->high).
PROFILE_COLORS = {
    "resource_constrained": "#86b6ef",
    "intermediate_capacity": "#2a78d6",
    "high_capacity": "#104281",
}
PROFILE_LABELS = {
    "resource_constrained": "Resource-constrained",
    "intermediate_capacity": "Intermediate-capacity",
    "high_capacity": "High-capacity",
}
FACILITY_LABELS = {
    "small_clinic": "Small clinic",
    "regional_hospital": "Regional hospital",
    "large_hospital": "Large hospital",
}
ACCENT = "#2a78d6"

#: Sequential blue ramp (validated reference steps 100 -> 700).
SEQ_BLUES = LinearSegmentedColormap.from_list("grrc_blues", [
    "#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf",
    "#1c5cab", "#104281", "#0d366b"])

#: Categorical slots (fixed order) for the zone diagram; workstations are
#: rendered neutral gray so clinical/sensitive zones stand out. Every zone
#: cluster is also direct-labeled, so identity never rides on color alone.
ZONE_COLORS = {
    Zone.WORKSTATION: "#b5b3ac",
    Zone.EHR: "#2a78d6",
    Zone.LAB: "#1baf7a",
    Zone.PHARMACY: "#eda100",
    Zone.IMAGING: "#008300",
    Zone.MEDICAL_DEVICE: "#e87ba4",
    Zone.ADMIN: "#898781",
    Zone.IDENTITY: "#4a3aa7",
    Zone.BACKUP: "#eb6834",
    Zone.INTERNET_FACING: "#e34948",
}
ZONE_LABELS = {
    Zone.WORKSTATION: "Workstations",
    Zone.EHR: "EHR",
    Zone.LAB: "Laboratory",
    Zone.PHARMACY: "Pharmacy",
    Zone.IMAGING: "Imaging",
    Zone.MEDICAL_DEVICE: "Medical devices",
    Zone.ADMIN: "Administration",
    Zone.IDENTITY: "Identity/Auth",
    Zone.BACKUP: "Backup",
    Zone.INTERNET_FACING: "Internet-facing",
}

PORTFOLIO_LABELS = {
    "baseline_flat": "Flat baseline",
    "profile_baseline": "Profile as-is posture",
    "basic_segmentation": "Basic segmentation",
    "least_privilege": "Least-privilege seg.",
    "patch_90": "Patch 90%",
    "fast_detection": "Fast detect + isolate",
    "isolated_backups": "Isolated backups",
    "identity_controls": "Identity controls",
    "seg_plus_patch": "Seg. + patch 90%",
    "seg_plus_detection": "Seg. + detection",
    "detection_plus_backups": "Detection + backups",
    "patch_plus_least_privilege": "Patch + least-priv.",
    "seg_detect_backup": "Seg. + detect + backup",
    "full_defense": "Full defense",
}


def apply_style() -> None:
    plt.rcParams.update({
        "figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
        "savefig.facecolor": SURFACE,
        "font.family": "sans-serif", "font.size": 10,
        "axes.edgecolor": BASELINE, "axes.labelcolor": INK,
        "axes.titlecolor": INK, "axes.titlesize": 11,
        "axes.titleweight": "bold",
        "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6,
        "axes.axisbelow": True,
        "axes.spines.top": False, "axes.spines.right": False,
        "xtick.color": MUTED, "ytick.color": MUTED,
        "xtick.labelcolor": INK_SECONDARY,
        "ytick.labelcolor": INK_SECONDARY,
        "legend.frameon": False, "legend.fontsize": 9,
        "figure.dpi": 110,
    })


def _save(fig, figures_dir: Path, tables_dir: Path, name: str,
          data: pd.DataFrame, caption: str,
          captions: list[str]) -> None:
    fig.savefig(figures_dir / f"{name}.png", dpi=300, bbox_inches="tight")
    fig.savefig(figures_dir / f"{name}.pdf", bbox_inches="tight")
    plt.close(fig)
    write_csv(data, tables_dir / f"{name}_data.csv")
    captions.append(f"**{name}** — {caption}\n")


def _ci_of(grp: pd.Series, seed: int) -> tuple[float, float, float]:
    vals = grp.to_numpy(dtype=float)
    lo, hi = bootstrap_ci(vals, seed=seed)
    return float(vals.mean()), lo, hi


# ---------------------------------------------------------------------------
# Figure 1 — example network architecture
# ---------------------------------------------------------------------------

def fig1_network(cfg: Config, figures_dir: Path, tables_dir: Path,
                 captions: list[str]) -> None:
    from .defenses import get_portfolio, effective_settings
    from .network_generator import generate_network

    eff = effective_settings(cfg.profiles["intermediate_capacity"],
                             get_portfolio("basic_segmentation"))
    rng = trial_rng(cfg.seed, 12345)
    net = generate_network(
        cfg, "regional_hospital", "intermediate_capacity", rng,
        segmentation=eff.segmentation, patch_coverage=eff.patch_coverage,
        backup_strategy=eff.backup_strategy)

    lay_rng = np.random.default_rng(7)
    zone_order = list(Zone)
    centers = {}
    for i, z in enumerate(zone_order):
        angle = 2 * np.pi * i / len(zone_order) - np.pi / 2
        centers[z] = np.array([np.cos(angle), np.sin(angle)]) * 1.5
    pos = np.zeros((net.n_nodes, 2))
    for z in zone_order:
        nodes = net.nodes_in_zone(z)
        spread = 0.16 + 0.05 * np.sqrt(nodes.size)
        pos[nodes] = centers[z] + lay_rng.normal(0, spread / 2.2,
                                                 size=(nodes.size, 2))

    fig, ax = plt.subplots(figsize=(8.2, 7.6))
    ax.set_axis_off()
    # subsample edges so the diagram stays readable
    keep = lay_rng.random(net.n_edges) < min(1.0, 900 / max(1, net.n_edges))
    for eid in np.flatnonzero(keep):
        s, d = int(net.edge_src[eid]), int(net.edge_dst[eid])
        cross = bool(net.edge_cross_boundary[eid])
        ax.plot([pos[s, 0], pos[d, 0]], [pos[s, 1], pos[d, 1]],
                color=INK_SECONDARY if cross else GRID,
                linewidth=0.45 if cross else 0.3,
                alpha=0.35 if cross else 0.5, zorder=1)
    for z in zone_order:
        nodes = net.nodes_in_zone(z)
        core = [n for n in nodes if net.node_type[n].endswith("_core")]
        ax.scatter(pos[nodes, 0], pos[nodes, 1], s=16,
                   color=ZONE_COLORS[z], edgecolors=SURFACE,
                   linewidths=0.4, zorder=3)
        if core:
            ax.scatter(pos[core, 0], pos[core, 1], s=70, marker="*",
                       color=ZONE_COLORS[z], edgecolors=INK,
                       linewidths=0.6, zorder=4)
        lx, ly = centers[z] * 1.42
        ax.text(lx, ly, f"{ZONE_LABELS[z]}\n(n={nodes.size})",
                ha="center", va="center", fontsize=8.5, color=INK,
                bbox=dict(boxstyle="round,pad=0.25", facecolor=SURFACE,
                          edgecolor=ZONE_COLORS[z], linewidth=1.1))
    ax.scatter([], [], s=70, marker="*", color=MUTED, edgecolors=INK,
               linewidths=0.6, label="Service core node")
    ax.plot([], [], color=INK_SECONDARY, linewidth=1.0,
            label="Cross-zone (boundary) link")
    ax.plot([], [], color=GRID, linewidth=1.0, label="Intra-zone link")
    ax.legend(loc="lower center", bbox_to_anchor=(0.5, -0.06), ncol=3)
    ax.set_title("Figure 1. Example synthetic hospital network "
                 f"(basic segmentation, {net.n_nodes} nodes)")
    ax.set_xlim(-2.35, 2.35)
    ax.set_ylim(-2.25, 2.25)

    data = pd.DataFrame({
        "zone": [ZONE_LABELS[z] for z in zone_order],
        "n_nodes": [int(net.nodes_in_zone(z).size) for z in zone_order],
    })
    _save(fig, figures_dir, tables_dir, "fig1_network_architecture", data,
          "One randomly generated regional-hospital topology (basic "
          "segmentation, intermediate-capacity profile). Nodes cluster by "
          "zone; stars mark service core nodes; darker lines cross "
          "segmentation boundaries. Synthetic model — not a real hospital. "
          "Edges subsampled for readability.", captions)


# ---------------------------------------------------------------------------
# Figure 2 — probability of critical-service disruption by defense strategy
# ---------------------------------------------------------------------------

def fig2_disruption(cfg: Config, main_df: pd.DataFrame, figures_dir: Path,
                    tables_dir: Path, captions: list[str]) -> None:
    df = main_df[main_df["facility"] == "regional_hospital"].copy()
    clinical_cols = ["ehr_downtime_steps", "laboratory_downtime_steps",
                     "pharmacy_downtime_steps", "imaging_downtime_steps"]
    df["clinical_disrupted"] = (df[clinical_cols] > 0).any(axis=1).astype(int)

    order = (df.groupby("portfolio")["clinical_disrupted"].mean()
             .sort_values(ascending=False).index.tolist())
    profiles = [p for p in PROFILE_COLORS if p in df["profile"].unique()]
    rows = []
    fig, ax = plt.subplots(figsize=(8.0, 6.4))
    y = np.arange(len(order), dtype=float)
    h = 0.8 / max(1, len(profiles))
    for i, prof in enumerate(profiles):
        sub = df[df["profile"] == prof]
        probs = [sub[sub["portfolio"] == p]["clinical_disrupted"].mean()
                 for p in order]
        ns = [int((sub["portfolio"] == p).sum()) for p in order]
        ax.barh(y + (i - (len(profiles) - 1) / 2) * h, probs, height=h * 0.9,
                color=PROFILE_COLORS[prof], label=PROFILE_LABELS[prof])
        rows += [{"portfolio": p, "profile": prof,
                  "p_clinical_disruption": v, "n_trials": n}
                 for p, v, n in zip(order, probs, ns)]
    ax.set_yticks(y)
    ax.set_yticklabels([PORTFOLIO_LABELS.get(p, p) for p in order])
    ax.invert_yaxis()
    ax.set_xlim(0, 1)
    ax.set_xlabel("P(at least one clinical service disrupted)")
    ax.set_title("Figure 2. Probability of critical-service disruption\n"
                 "by defense strategy (regional hospital)")
    ax.legend(loc="lower right")
    ax.grid(axis="x")
    ax.grid(False, axis="y")
    _save(fig, figures_dir, tables_dir, "fig2_disruption_by_strategy",
          pd.DataFrame(rows),
          "Share of Monte Carlo trials in which at least one clinical "
          "service (EHR, laboratory, pharmacy, imaging) experienced any "
          "downtime, by defense portfolio and capacity profile "
          "(regional hospital, all entry points pooled).", captions)


# ---------------------------------------------------------------------------
# Figure 3 — patch coverage x detection delay heat map
# ---------------------------------------------------------------------------

def fig3_heatmap(cfg: Config, sweep_summary: pd.DataFrame, figures_dir: Path,
                 tables_dir: Path, captions: list[str]) -> None:
    patches = sorted(sweep_summary["patch_coverage"].unique())
    delays = sorted(sweep_summary["detection_delay"].unique())
    grid = np.full((len(patches), len(delays)), np.nan)
    for _, row in sweep_summary.iterrows():
        i = patches.index(row["patch_coverage"])
        j = delays.index(row["detection_delay"])
        grid[i, j] = row["catastrophic_prob"]

    fig, ax = plt.subplots(figsize=(7.0, 4.6))
    im = ax.imshow(grid, cmap=SEQ_BLUES, vmin=0, vmax=1, aspect="auto")
    ax.set_xticks(range(len(delays)))
    ax.set_xticklabels([f"{d}" for d in delays])
    ax.set_yticks(range(len(patches)))
    ax.set_yticklabels([f"{p:.0%}" for p in patches])
    ax.set_xlabel("Mean detection delay (steps; 1 step = 15 modeled min)")
    ax.set_ylabel("Target patch coverage")
    ax.set_title("Figure 3. Catastrophic-disruption probability:\n"
                 "patch coverage vs. detection delay")
    ax.grid(False)
    for i in range(len(patches)):
        for j in range(len(delays)):
            v = grid[i, j]
            if np.isnan(v):
                continue
            ax.text(j, i, f"{v:.2f}", ha="center", va="center", fontsize=9,
                    color=SURFACE if v > 0.55 else INK)
    cbar = fig.colorbar(im, ax=ax, shrink=0.9)
    cbar.set_label("P(catastrophic disruption)", color=INK_SECONDARY)
    cbar.outline.set_edgecolor(BASELINE)
    _save(fig, figures_dir, tables_dir, "fig3_patch_detection_heatmap",
          sweep_summary,
          "Probability that at least one clinical service stays down for "
          "more than 8 consecutive steps (2 modeled hours), across the "
          "patch-coverage x detection-delay grid (regional hospital, "
          "intermediate profile, flat architecture, entry points pooled). "
          "The patch axis is the CONFIGURED (target) coverage; legacy nodes "
          "receive half that probability, so the realized patched fraction "
          "is somewhat lower (see data_dictionary: realized_patch_fraction).",
          captions)


# ---------------------------------------------------------------------------
# Figure 4 — budget-resilience Pareto frontier
# ---------------------------------------------------------------------------

def fig4_pareto(cfg: Config, portfolio_summary: pd.DataFrame,
                pareto: pd.DataFrame, figures_dir: Path, tables_dir: Path,
                captions: list[str]) -> None:
    profiles = [p for p in PROFILE_COLORS
                if p in portfolio_summary["profile"].unique()]
    fig, axes = plt.subplots(1, len(profiles), figsize=(11.5, 4.0),
                             sharey=True)
    axes = np.atleast_1d(axes)
    for ax, prof in zip(axes, profiles):
        sub = portfolio_summary[portfolio_summary["profile"] == prof]
        front = pareto[pareto["profile"] == prof].sort_values("cost")
        ax.scatter(sub["base_cost"], sub["mean_hours_lost"], s=14,
                   color=MUTED, alpha=0.45, label="All candidate portfolios",
                   zorder=2)
        ax.plot(front["cost"], front["mean_hours_lost"], "-o",
                color=PROFILE_COLORS[prof], linewidth=2, markersize=5,
                label="Pareto frontier", zorder=3)
        for b in cfg.optimization.budgets:
            ax.axvline(b, color=BASELINE, linewidth=0.8, linestyle="--",
                       zorder=1)
            ax.text(b, ax.get_ylim()[1], f" B={b}", fontsize=8,
                    color=MUTED, va="top")
        ax.set_title(PROFILE_LABELS[prof], fontsize=10)
        ax.set_xlabel("Portfolio cost (normalized points)")
    axes[0].set_ylabel("Mean weighted service-hours lost")
    axes[0].legend(loc="upper right", fontsize=8)
    fig.suptitle("Figure 4. Cost vs. resilience: Pareto frontier of "
                 "defense portfolios (regional hospital)",
                 fontweight="bold", y=1.03)
    _save(fig, figures_dir, tables_dir, "fig4_pareto_frontier",
          pareto,
          "Each gray dot is one candidate defense portfolio evaluated by "
          "Monte Carlo simulation (the behaviorally-distinct portfolios "
          "reachable from each profile's baseline); the line joins "
          "cost-nondominated portfolios. Dashed lines mark the studied "
          "budget levels. Costs are normalized model points, not dollars.",
          captions)


# ---------------------------------------------------------------------------
# Figure 5 — facility-size comparison
# ---------------------------------------------------------------------------

def fig5_facility(cfg: Config, main_df: pd.DataFrame, figures_dir: Path,
                  tables_dir: Path, captions: list[str]) -> None:
    df = main_df[main_df["portfolio"] == "profile_baseline"]
    facilities = [f for f in FACILITY_LABELS if f in df["facility"].unique()]
    profiles = [p for p in PROFILE_COLORS if p in df["profile"].unique()]
    fig, ax = plt.subplots(figsize=(7.2, 4.4))
    x = np.arange(len(facilities), dtype=float)
    w = 0.8 / max(1, len(profiles))
    rows = []
    for i, prof in enumerate(profiles):
        means, los, his = [], [], []
        for fac in facilities:
            sub = df[(df["facility"] == fac) & (df["profile"] == prof)]
            m, lo, hi = _ci_of(sub["weighted_service_hours_lost"], cfg.seed)
            means.append(m)
            los.append(m - lo)
            his.append(hi - m)
            rows.append({"facility": fac, "profile": prof,
                         "mean_weighted_hours_lost": m,
                         "ci95_lo": lo, "ci95_hi": hi,
                         "n_trials": len(sub)})
        xi = x + (i - (len(profiles) - 1) / 2) * w
        ax.bar(xi, means, width=w * 0.9, color=PROFILE_COLORS[prof],
               label=PROFILE_LABELS[prof])
        ax.errorbar(xi, means, yerr=[los, his], fmt="none",
                    ecolor=INK_SECONDARY, elinewidth=1, capsize=3)
    ax.set_xticks(x)
    ax.set_xticklabels([FACILITY_LABELS[f] for f in facilities])
    ax.set_ylabel("Mean weighted service-hours lost")
    ax.set_title("Figure 5. Service loss by facility size and capacity\n"
                 "profile (as-is posture, 95% bootstrap CIs)")
    ax.legend()
    ax.grid(axis="y")
    ax.grid(False, axis="x")
    _save(fig, figures_dir, tables_dir, "fig5_facility_comparison",
          pd.DataFrame(rows),
          "Mean weighted service-hours lost under each profile's as-is "
          "defensive posture (portfolio 'profile_baseline'), by synthetic "
          "facility size; error bars are 95% bootstrap CIs of the mean, "
          "all entry points pooled.", captions)


# ---------------------------------------------------------------------------
# Figure 6 — backup compromise by backup strategy
# ---------------------------------------------------------------------------

def fig6_backup(cfg: Config, backup_df: pd.DataFrame, figures_dir: Path,
                tables_dir: Path, captions: list[str]) -> None:
    strategies = ["connected", "periodic", "isolated"]
    present = [s for s in strategies
               if s in backup_df["backup_strategy"].unique()]
    profiles = [p for p in PROFILE_COLORS
                if p in backup_df["profile"].unique()]
    fig, ax = plt.subplots(figsize=(6.8, 4.2))
    x = np.arange(len(present), dtype=float)
    w = 0.8 / max(1, len(profiles))
    rows = []
    for i, prof in enumerate(profiles):
        vals, ns = [], []
        for s in present:
            sub = backup_df[(backup_df["backup_strategy"] == s)
                            & (backup_df["profile"] == prof)]
            vals.append(sub["backup_compromised"].mean() if len(sub)
                        else np.nan)
            ns.append(len(sub))
            rows.append({"backup_strategy": s, "profile": prof,
                         "p_backup_compromised": vals[-1],
                         "n_trials": ns[-1]})
        xi = x + (i - (len(profiles) - 1) / 2) * w
        bars = ax.bar(xi, vals, width=w * 0.9, color=PROFILE_COLORS[prof],
                      label=PROFILE_LABELS[prof])
        for b, v in zip(bars, vals):
            if np.isfinite(v):
                ax.text(b.get_x() + b.get_width() / 2, v + 0.015,
                        f"{v:.2f}", ha="center", fontsize=8,
                        color=INK_SECONDARY)
    ax.set_xticks(x)
    ax.set_xticklabels([s.capitalize() for s in present])
    ax.set_ylim(0, 1.02)
    ax.set_xlabel("Backup connectivity strategy")
    ax.set_ylabel("P(backup system compromised)")
    ax.set_title("Backup-compromise probability by strategy")
    ax.legend()
    ax.grid(axis="y")
    ax.grid(False, axis="x")
    _save(fig, figures_dir, tables_dir, "fig6_backup_strategies",
          pd.DataFrame(rows),
          "Probability that any backup-zone node was compromised, from the "
          "CONTROLLED backup experiment: three portfolios identical except "
          "for backup connectivity (flat architecture, each profile's own "
          "baseline patch/detection), so only the backup strategy varies. "
          "Facilities pooled.", captions)


# ---------------------------------------------------------------------------
# Figure 7 — service-hours preserved per cost point
# ---------------------------------------------------------------------------

def fig7_efficiency(cfg: Config, comparisons: pd.DataFrame,
                    main_df: pd.DataFrame, figures_dir: Path,
                    tables_dir: Path, captions: list[str]) -> None:
    df = comparisons[comparisons["facility"] == "regional_hospital"].copy()
    costs = (main_df[main_df["facility"] == "regional_hospital"]
             .groupby(["profile", "portfolio"])["portfolio_cost"]
             .first().reset_index())
    df = df.merge(costs, on=["profile", "portfolio"], how="left")
    df = df[(df["portfolio_cost"] > 0) & df["portfolio_cost"].notna()]
    df["hours_preserved_per_point"] = (
        (df["baseline_mean_hours_lost"] - df["mean_hours_lost"])
        / df["portfolio_cost"])
    order = (df.groupby("portfolio")["hours_preserved_per_point"].mean()
             .sort_values().index.tolist())
    profiles = [p for p in PROFILE_COLORS if p in df["profile"].unique()]
    fig, ax = plt.subplots(figsize=(8.0, 6.0))
    y = np.arange(len(order), dtype=float)
    h = 0.8 / max(1, len(profiles))
    for i, prof in enumerate(profiles):
        sub = df[df["profile"] == prof].set_index("portfolio")
        vals = [sub["hours_preserved_per_point"].get(p, np.nan)
                for p in order]
        ax.barh(y + (i - (len(profiles) - 1) / 2) * h, vals, height=h * 0.9,
                color=PROFILE_COLORS[prof], label=PROFILE_LABELS[prof])
    ax.axvline(0, color=BASELINE, linewidth=1)
    ax.set_yticks(y)
    ax.set_yticklabels([PORTFOLIO_LABELS.get(p, p) for p in order])
    ax.set_xlabel("Weighted service-hours preserved per cost point\n"
                  "(vs. flat baseline; normalized cost points)")
    ax.set_title("Figure 7. Cost-effectiveness of defense portfolios\n"
                 "(regional hospital)")
    ax.legend(loc="lower right")
    ax.grid(axis="x")
    ax.grid(False, axis="y")
    keep_cols = ["facility", "profile", "portfolio", "portfolio_cost",
                 "baseline_mean_hours_lost", "mean_hours_lost",
                 "hours_preserved_per_point"]
    _save(fig, figures_dir, tables_dir, "fig7_cost_effectiveness",
          df[keep_cols],
          "Reduction in mean weighted service-hours lost relative to the "
          "flat baseline, divided by the portfolio's normalized cost "
          "(regional hospital). Costs are model points, not dollars; "
          "patch-upgrade costs depend on the profile's starting coverage.",
          captions)


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def generate_figures(cfg: Config) -> list[Path]:
    """Build all figures from raw + processed outputs of the current mode."""
    log = setup_logging(resolve_path(cfg.output.logs_dir), "grrc.plot")
    apply_style()
    figures_dir = resolve_path(cfg.output.figures_dir)
    tables_dir = resolve_path(cfg.output.tables_dir)
    ensure_dirs(figures_dir, tables_dir)
    raw_dir = resolve_path(cfg.output.raw_dir)
    proc_dir = resolve_path(cfg.output.processed_dir)
    mode = cfg.mode
    captions: list[str] = [
        "# Figure captions\n",
        f"Generated from `{mode}` mode outputs. All values are simulation "
        "outputs under documented model assumptions; none are real-world "
        "measurements.\n",
    ]

    main_df = pd.read_csv(raw_dir / f"{mode}_main_results.csv")
    fig1_network(cfg, figures_dir, tables_dir, captions)
    fig2_disruption(cfg, main_df, figures_dir, tables_dir, captions)

    sweep_path = proc_dir / f"{mode}_sweep_summary.csv"
    if sweep_path.exists():
        fig3_heatmap(cfg, pd.read_csv(sweep_path), figures_dir, tables_dir,
                     captions)
    else:
        log.warning("skipping Figure 3 (no %s)", sweep_path)

    psum_path = proc_dir / f"{mode}_portfolio_summary.csv"
    pareto_path = proc_dir / f"{mode}_pareto_frontier.csv"
    if psum_path.exists() and pareto_path.exists():
        fig4_pareto(cfg, pd.read_csv(psum_path), pd.read_csv(pareto_path),
                    figures_dir, tables_dir, captions)
    else:
        log.warning("skipping Figure 4 (run 'optimize' first)")

    fig5_facility(cfg, main_df, figures_dir, tables_dir, captions)
    backup_path = raw_dir / f"{mode}_backup_results.csv"
    if backup_path.exists():
        fig6_backup(cfg, pd.read_csv(backup_path), figures_dir, tables_dir,
                    captions)
    else:
        log.warning("skipping Figure 6 (no %s)", backup_path)

    comp_path = proc_dir / f"{mode}_baseline_comparisons.csv"
    if comp_path.exists():
        fig7_efficiency(cfg, pd.read_csv(comp_path), main_df, figures_dir,
                        tables_dir, captions)
    else:
        log.warning("skipping Figure 7 (run 'analyze' first)")

    (figures_dir / "captions.md").write_text("\n".join(captions))
    written = sorted(figures_dir.glob("fig*.png"))
    log.info("wrote %d figures to %s", len(written), figures_dir)
    return written
