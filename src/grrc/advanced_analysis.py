"""Confirmatory statistics, robustness summaries, and publication figures."""

from __future__ import annotations

import json
import os
from pathlib import Path

os.environ.setdefault(
    "MPLCONFIGDIR",
    str(Path(__file__).resolve().parents[2] / "outputs" / ".matplotlib"),
)
os.environ.setdefault("MPLBACKEND", "Agg")

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

from .config import Config, load_defense_costs
from .defenses import enumerate_portfolios, portfolio_cost
from .optimization import summarize_portfolios
from .statistics import bootstrap_ci, wilson_ci
from .utilities import ensure_dirs, resolve_path, write_csv


def _paired_bootstrap(values: np.ndarray, seed: int = 20260718,
                      n_boot: int = 4000) -> tuple[float, float]:
    values = np.asarray(values, dtype=float)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(values), size=(n_boot, len(values)))
    means = values[idx].mean(axis=1)
    return float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def analyze_paired_main(main: pd.DataFrame, cfg: Config
                        ) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Summarize confirmatory cells and paired portfolio effects."""
    summaries: list[dict] = []
    for keys, grp in main.groupby(["facility", "profile", "portfolio"]):
        hours = grp["weighted_service_hours_lost"].to_numpy()
        lo, hi = bootstrap_ci(hours, n_boot=4000, seed=cfg.seed)
        events = int(grp["catastrophic"].sum())
        cat_lo, cat_hi = wilson_ci(events, len(grp))
        summaries.append({
            "facility": keys[0], "profile": keys[1], "portfolio": keys[2],
            "n": len(grp), "mean_hours_lost": float(hours.mean()),
            "median_hours_lost": float(np.median(hours)),
            "hours_ci95_lo": lo, "hours_ci95_hi": hi,
            "catastrophic_events": events,
            "catastrophic_prob": events / len(grp),
            "catastrophic_ci95_lo": cat_lo,
            "catastrophic_ci95_hi": cat_hi,
            "mean_pct_compromised": float(grp["pct_compromised"].mean()),
        })

    comparisons: list[dict] = []
    pair_keys = ["master_seed", "scenario_id", "entry_point"]
    for (facility, profile), cell in main.groupby(["facility", "profile"]):
        base = cell[cell["portfolio"] == "baseline_flat"]
        for portfolio, treatment in cell.groupby("portfolio"):
            if portfolio == "baseline_flat":
                continue
            merged = base.merge(treatment, on=pair_keys, suffixes=("_base", "_tx"))
            diff = (merged["weighted_service_hours_lost_tx"]
                    - merged["weighted_service_hours_lost_base"]).to_numpy()
            lo, hi = _paired_bootstrap(diff, seed=cfg.seed)
            base_mean = float(merged["weighted_service_hours_lost_base"].mean())
            tx_mean = float(merged["weighted_service_hours_lost_tx"].mean())
            base_cat = merged["catastrophic_base"].to_numpy(dtype=int)
            tx_cat = merged["catastrophic_tx"].to_numpy(dtype=int)
            risk_diff = tx_cat - base_cat
            rd_lo, rd_hi = _paired_bootstrap(risk_diff, seed=cfg.seed + 1)
            improved = int(((base_cat == 1) & (tx_cat == 0)).sum())
            worsened = int(((base_cat == 0) & (tx_cat == 1)).sum())
            discordant = improved + worsened
            mcnemar_p = (stats.binomtest(
                min(improved, worsened), discordant, 0.5,
                alternative="two-sided").pvalue if discordant else 1.0)
            comparisons.append({
                "facility": facility, "profile": profile,
                "portfolio": portfolio, "n_pairs": len(merged),
                "baseline_mean_hours": base_mean,
                "portfolio_mean_hours": tx_mean,
                "paired_mean_difference_hours": float(diff.mean()),
                "paired_difference_ci95_lo": lo,
                "paired_difference_ci95_hi": hi,
                "relative_reduction_hours": (
                    (base_mean - tx_mean) / base_mean if base_mean else np.nan),
                "paired_catastrophic_risk_difference": float(risk_diff.mean()),
                "risk_difference_ci95_lo": rd_lo,
                "risk_difference_ci95_hi": rd_hi,
                "catastrophic_pairs_improved": improved,
                "catastrophic_pairs_worsened": worsened,
                "mcnemar_exact_p": float(mcnemar_p),
            })

    primary = main[
        (main["facility"] == "regional_hospital")
        & (main["profile"] == "intermediate_capacity")
        & (main["portfolio"].isin(["baseline_flat", "full_defense"]))
    ]
    base = primary[primary["portfolio"] == "baseline_flat"]
    full = primary[primary["portfolio"] == "full_defense"]
    merged = base.merge(full, on=pair_keys, suffixes=("_base", "_full"))
    merged = merged.sort_values(["master_seed", "scenario_id"])
    convergence: list[dict] = []
    for n in [25, 50, 75, 100, 125, len(merged)]:
        if n > len(merged):
            continue
        diff = (merged.iloc[:n]["weighted_service_hours_lost_full"]
                - merged.iloc[:n]["weighted_service_hours_lost_base"]).to_numpy()
        lo, hi = _paired_bootstrap(diff, seed=cfg.seed + n, n_boot=2000)
        convergence.append({
            "n_pairs": n, "paired_mean_difference_hours": float(diff.mean()),
            "ci95_lo": lo, "ci95_hi": hi,
        })
    return (pd.DataFrame(summaries), pd.DataFrame(comparisons),
            pd.DataFrame(convergence).drop_duplicates("n_pairs"))


def _fit_logistic_clustered(sweep: pd.DataFrame) -> pd.DataFrame:
    """Logistic patch-delay interaction with scenario-clustered covariance."""
    df = sweep.copy()
    patch = df["patch_coverage"].to_numpy(float)
    log_delay = np.log(df["detection_delay"].to_numpy(float))
    patch_c = patch - patch.mean()
    delay_c = log_delay - log_delay.mean()
    entries = pd.get_dummies(df["entry_point"], drop_first=True, dtype=float)
    X = np.column_stack([
        np.ones(len(df)), patch_c, delay_c, patch_c * delay_c,
        entries.to_numpy(),
    ])
    names = ["intercept", "patch_centered", "log_delay_centered",
             "patch_x_log_delay"] + [f"entry_{c}" for c in entries.columns]
    y = df["catastrophic"].to_numpy(float)
    beta = np.zeros(X.shape[1])
    for _ in range(100):
        eta = np.clip(X @ beta, -30, 30)
        p = 1.0 / (1.0 + np.exp(-eta))
        w = np.maximum(p * (1 - p), 1e-8)
        h = X.T @ (X * w[:, None]) + np.eye(X.shape[1]) * 1e-8
        score = X.T @ (y - p)
        step = np.linalg.solve(h, score)
        beta += step
        if np.max(np.abs(step)) < 1e-9:
            break
    eta = np.clip(X @ beta, -30, 30)
    p = 1.0 / (1.0 + np.exp(-eta))
    w = np.maximum(p * (1 - p), 1e-8)
    bread = np.linalg.pinv(X.T @ (X * w[:, None]))
    scores = X * (y - p)[:, None]
    clusters = (df["master_seed"].astype(str) + ":"
                + df["scenario_id"].astype(str)).to_numpy()
    meat = np.zeros((X.shape[1], X.shape[1]))
    for cluster in np.unique(clusters):
        total = scores[clusters == cluster].sum(axis=0)
        meat += np.outer(total, total)
    cov = bread @ meat @ bread
    se = np.sqrt(np.maximum(np.diag(cov), 0))
    z = np.divide(beta, se, out=np.zeros_like(beta), where=se > 0)
    pvals = 2 * stats.norm.sf(np.abs(z))
    return pd.DataFrame({
        "term": names, "coefficient": beta, "cluster_robust_se": se,
        "ci95_lo": beta - 1.96 * se, "ci95_hi": beta + 1.96 * se,
        "z": z, "p_value": pvals,
        "n_trials": len(df), "n_scenario_clusters": len(np.unique(clusters)),
    })


def analyze_sweep(sweep: pd.DataFrame, cfg: Config
                  ) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows: list[dict] = []
    for (patch, delay), grp in sweep.groupby(
            ["patch_coverage", "detection_delay"]):
        hours = grp["weighted_service_hours_lost"].to_numpy()
        lo, hi = bootstrap_ci(hours, n_boot=4000, seed=cfg.seed)
        events = int(grp["catastrophic"].sum())
        cat_lo, cat_hi = wilson_ci(events, len(grp))
        rows.append({
            "patch_coverage": patch, "detection_delay": delay,
            "n": len(grp), "catastrophic_events": events,
            "catastrophic_prob": events / len(grp),
            "catastrophic_ci95_lo": cat_lo,
            "catastrophic_ci95_hi": cat_hi,
            "mean_hours_lost": float(hours.mean()),
            "hours_ci95_lo": lo, "hours_ci95_hi": hi,
        })
    return pd.DataFrame(rows), _fit_logistic_clustered(sweep)


def bootstrap_optimizer_uncertainty(raw: pd.DataFrame, cfg: Config,
                                    label: str, n_boot: int = 1000
                                    ) -> pd.DataFrame:
    """Bootstrap ranks, winners, and Pareto membership under each budget."""
    costs = load_defense_costs(resolve_path("configs/defense_costs.yaml"))
    summary = summarize_portfolios(raw, cfg, costs)
    rng = np.random.default_rng(20260718)
    rows: list[dict] = []
    for profile in sorted(summary["profile"].unique()):
        sub = summary[summary["profile"] == profile].reset_index(drop=True)
        names = sub["portfolio"].tolist()
        base_costs = sub["base_cost"].to_numpy(float)
        mean_boot = np.empty((len(names), n_boot))
        for i, name in enumerate(names):
            vals = raw[(raw["profile"] == profile)
                       & (raw["portfolio"] == name)][
                           "weighted_service_hours_lost"].to_numpy()
            idx = rng.integers(0, len(vals), size=(n_boot, len(vals)))
            mean_boot[i] = vals[idx].mean(axis=1)
        for budget in cfg.optimization.budgets:
            feasible = np.flatnonzero(base_costs <= budget)
            if feasible.size == 0:
                continue
            means = mean_boot[feasible]
            order = np.argsort(means, axis=0)
            ranks = np.empty_like(order)
            for b in range(n_boot):
                ranks[order[:, b], b] = np.arange(1, len(feasible) + 1)
            best = np.argmin(means, axis=0)
            pareto = np.zeros_like(means, dtype=bool)
            for b in range(n_boot):
                sorted_local = np.lexsort((means[:, b], base_costs[feasible]))
                current = np.inf
                for local in sorted_local:
                    if means[local, b] < current - 1e-12:
                        pareto[local, b] = True
                        current = means[local, b]
            for local, original in enumerate(feasible):
                rows.append({
                    "analysis_set": label, "profile": profile,
                    "budget": budget, "portfolio": names[original],
                    "base_cost": base_costs[original],
                    "probability_best": float((best == local).mean()),
                    "mean_rank": float(ranks[local].mean()),
                    "rank_ci95_lo": float(np.percentile(ranks[local], 2.5)),
                    "rank_ci95_hi": float(np.percentile(ranks[local], 97.5)),
                    "pareto_frequency": float(pareto[local].mean()),
                    "n_bootstrap": n_boot,
                })
    return pd.DataFrame(rows)


def independent_cost_uncertainty(raw: pd.DataFrame, cfg: Config,
                                 n_draws: int = 5000) -> pd.DataFrame:
    """Vary each control cost independently from 0.5x to 2x."""
    base_costs = load_defense_costs(resolve_path("configs/defense_costs.yaml"))
    cost_names = list(base_costs)
    rng = np.random.default_rng(20260718)
    multipliers = np.exp(rng.uniform(
        np.log(0.5), np.log(2.0), size=(n_draws, len(cost_names))))
    portfolio_map = {p.name: p for p in enumerate_portfolios()}
    summary = summarize_portfolios(raw, cfg, base_costs)
    rows: list[dict] = []
    for profile in cfg.optimization.profiles:
        sub = summary[summary["profile"] == profile].reset_index(drop=True)
        names = sub["portfolio"].tolist()
        means = sub["mean_hours_lost"].to_numpy(float)
        for budget in cfg.optimization.budgets:
            counts: dict[str, int] = {name: 0 for name in names}
            feasible_draws = 0
            for draw in multipliers:
                costs = {name: base_costs[name] * draw[i]
                         for i, name in enumerate(cost_names)}
                values = np.array([
                    portfolio_cost(portfolio_map[name], cfg.profiles[profile],
                                   costs) for name in names])
                feasible = np.flatnonzero(values <= budget)
                if feasible.size:
                    winner = feasible[np.argmin(means[feasible])]
                    counts[names[winner]] += 1
                    feasible_draws += 1
            for name, count in counts.items():
                if count:
                    rows.append({
                        "profile": profile, "budget": budget,
                        "portfolio": name,
                        "winner_frequency": count / feasible_draws,
                        "n_cost_draws": feasible_draws,
                        "cost_multiplier_range": "independent log-uniform 0.5x-2x",
                    })
    return pd.DataFrame(rows)


def analyze_sensitivity(raw: pd.DataFrame
                        ) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    summary = (raw.groupby(["setting_id", "portfolio"])
               .agg(mean_hours_lost=("weighted_service_hours_lost", "mean"),
                    catastrophic_prob=("catastrophic", "mean"))
               .reset_index())
    hours = summary.pivot(index="setting_id", columns="portfolio",
                          values="mean_hours_lost")
    cats = summary.pivot(index="setting_id", columns="portfolio",
                         values="catastrophic_prob")
    setting = pd.DataFrame(index=hours.index)
    setting["baseline_mean_hours"] = hours["baseline_flat"]
    setting["affordable_mean_hours"] = hours["seg_detect_backup"]
    setting["full_mean_hours"] = hours["full_defense"]
    setting["affordable_reduction"] = 1 - (
        setting["affordable_mean_hours"] / setting["baseline_mean_hours"])
    setting["full_reduction"] = 1 - (
        setting["full_mean_hours"] / setting["baseline_mean_hours"])
    setting["affordable_beats_baseline"] = (
        setting["affordable_mean_hours"] < setting["baseline_mean_hours"])
    setting["full_beats_baseline"] = (
        setting["full_mean_hours"] < setting["baseline_mean_hours"])
    setting["full_best"] = (
        setting[["baseline_mean_hours", "affordable_mean_hours",
                 "full_mean_hours"]].idxmin(axis=1) == "full_mean_hours")
    setting["baseline_catastrophic"] = cats["baseline_flat"]
    setting["affordable_catastrophic"] = cats["seg_detect_backup"]
    setting["full_catastrophic"] = cats["full_defense"]
    setting = setting.reset_index()

    param_cols = [c for c in raw.columns if c in {
        "base_spread_rate", "patch_effectiveness", "intra_zone_degree",
        "cross_zone_out_degree", "identity_breach_multiplier",
        "restore_rate_fraction", "service_functional_fraction",
        "false_positive_rate", "legacy_fraction", "isolation_success",
        "detection_delay_steps", "isolated_backup_traversal",
    }]
    params = raw.groupby("setting_id")[param_cols].first().reset_index()
    joined = params.merge(setting, on="setting_id")
    correlations: list[dict] = []
    for parameter in param_cols:
        for outcome in ["baseline_mean_hours", "affordable_reduction",
                        "full_reduction"]:
            rho, p = stats.spearmanr(joined[parameter], joined[outcome])
            correlations.append({
                "parameter": parameter, "outcome": outcome,
                "spearman_rho": float(rho), "p_value": float(p),
            })
    robustness = pd.DataFrame([{
        "n_parameter_settings": len(setting),
        "affordable_beats_baseline_fraction": float(
            setting["affordable_beats_baseline"].mean()),
        "full_beats_baseline_fraction": float(
            setting["full_beats_baseline"].mean()),
        "full_ranked_best_fraction": float(setting["full_best"].mean()),
        "median_affordable_reduction": float(
            setting["affordable_reduction"].median()),
        "affordable_reduction_p05": float(
            setting["affordable_reduction"].quantile(0.05)),
        "median_full_reduction": float(setting["full_reduction"].median()),
        "full_reduction_p05": float(setting["full_reduction"].quantile(0.05)),
    }])
    return setting, pd.DataFrame(correlations), robustness


def _simple_group_summary(raw: pd.DataFrame, groups: list[str]) -> pd.DataFrame:
    return (raw.groupby(groups + ["portfolio"])
            .agg(n=("trial_id", "size"),
                 mean_hours_lost=("weighted_service_hours_lost", "mean"),
                 median_hours_lost=("weighted_service_hours_lost", "median"),
                 catastrophic_prob=("catastrophic", "mean"),
                 backup_compromise_prob=("backup_compromised", "mean"),
                 recovery_prob=("recovered_within_horizon", "mean"))
            .reset_index())


def create_advanced_figures(main_comp: pd.DataFrame,
                            sensitivity_setting: pd.DataFrame,
                            optimizer_uncertainty: pd.DataFrame,
                            backup_summary: pd.DataFrame,
                            capacity_summary: pd.DataFrame,
                            out_dir: Path) -> list[Path]:
    ensure_dirs(out_dir)
    created: list[Path] = []
    plt.style.use("seaborn-v0_8-whitegrid")

    cell = main_comp[
        (main_comp["facility"] == "regional_hospital")
        & (main_comp["profile"] == "intermediate_capacity")].copy()
    order = cell.sort_values("paired_mean_difference_hours")
    fig, ax = plt.subplots(figsize=(8.2, 4.8))
    y = np.arange(len(order))
    ax.errorbar(order["paired_mean_difference_hours"], y,
                xerr=[order["paired_mean_difference_hours"]
                      - order["paired_difference_ci95_lo"],
                      order["paired_difference_ci95_hi"]
                      - order["paired_mean_difference_hours"]],
                fmt="o", color="#0B6E75", ecolor="#8AB8BA", capsize=3)
    ax.axvline(0, color="#6B7280", linewidth=1)
    ax.set_yticks(y, order["portfolio"].str.replace("_", " "))
    ax.set_xlabel("Paired change in weighted service-hours (defense - baseline)")
    ax.set_title("Confirmatory paired effects: intermediate regional hospital")
    fig.tight_layout()
    path = out_dir / "fig8_confirmatory_paired_effects.png"
    fig.savefig(path, dpi=220, bbox_inches="tight")
    plt.close(fig)
    created.append(path)

    fig, ax = plt.subplots(figsize=(7.6, 4.6))
    ax.hist(sensitivity_setting["affordable_reduction"] * 100, bins=18,
            alpha=0.75, label="Affordable layered portfolio", color="#D98E32")
    ax.hist(sensitivity_setting["full_reduction"] * 100, bins=18,
            alpha=0.65, label="Full defense", color="#0B6E75")
    ax.axvline(0, color="#6B7280", linewidth=1)
    ax.set_xlabel("Reduction from baseline across parameter settings (%)")
    ax.set_ylabel("Latin-hypercube settings")
    ax.set_title("Robustness across jointly varied model assumptions")
    ax.legend(frameon=False)
    fig.tight_layout()
    path = out_dir / "fig9_global_sensitivity.png"
    fig.savefig(path, dpi=220, bbox_inches="tight")
    plt.close(fig)
    created.append(path)

    opt = optimizer_uncertainty[
        (optimizer_uncertainty["analysis_set"] == "discovery")
        & (optimizer_uncertainty["profile"] == "intermediate_capacity")]
    top = (opt.sort_values(["budget", "probability_best"], ascending=[True, False])
           .groupby("budget").head(4))
    def short_portfolio(value: str) -> str:
        parts = value.split("|")
        mapped: list[str] = []
        for part in parts:
            if part.startswith("seg-"):
                seg = part.removeprefix("seg-")
                mapped.append({"flat": "Flat", "basic": "Basic",
                               "least_privilege": "LP"}.get(
                                   seg, seg))
            elif part.startswith("patch+"):
                mapped.append(part.replace("patch+", "Patch +"))
            elif part.startswith("det"):
                mapped.append(part.replace("det", "Detect "))
            elif part.startswith("iso"):
                mapped.append("Iso" if part == "iso1" else "No iso")
            elif part.startswith("bak-"):
                mapped.append(part.removeprefix("bak-").title())
            elif part == "idm1":
                mapped.append("Identity")
        return " | ".join(mapped)

    fig, axes = plt.subplots(3, 1, figsize=(9.2, 7.2), sharex=True)
    for ax, (budget, grp) in zip(axes, top.groupby("budget")):
        grp = grp.sort_values("probability_best")
        labels = [short_portfolio(v) for v in grp["portfolio"]]
        ax.barh(labels,
                grp["probability_best"] * 100, color="#4C78A8")
        ax.set_title(f"Budget {budget:g}")
        ax.set_xlim(0, 100)
        ax.tick_params(axis="y", labelsize=8)
    axes[-1].set_xlabel("Bootstrap probability of being best (%)")
    fig.suptitle("No single optimizer winner is certain at every budget",
                 fontsize=14)
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    path = out_dir / "fig10_optimizer_uncertainty.png"
    fig.savefig(path, dpi=220, bbox_inches="tight")
    plt.close(fig)
    created.append(path)

    iso = backup_summary[backup_summary["portfolio"] == "backup_isolated"]
    fig, axes = plt.subplots(1, 2, figsize=(10.8, 4.5))
    compromise = (iso.groupby("isolated_backup_traversal", as_index=False)
                  ["backup_compromise_prob"].mean())
    axes[0].plot(compromise["isolated_backup_traversal"],
                 compromise["backup_compromise_prob"] * 100,
                 marker="o", color="#0B6E75", linewidth=2.2)
    axes[0].set_xlabel("Residual traversal into backup zone")
    axes[0].set_ylabel("Backup compromise probability (%)")
    axes[0].set_title("Compromise depends on isolation")
    for restore, grp in iso.groupby("restore_rate_multiplier"):
        axes[1].plot(grp["isolated_backup_traversal"],
                     grp["mean_hours_lost"], marker="o",
                     label=f"Restore x{restore:g}")
    axes[1].set_xlabel("Residual traversal into backup zone")
    axes[1].set_ylabel("Mean weighted service-hours lost")
    axes[1].set_title("Restore speed changes disruption")
    axes[1].legend(frameon=False, fontsize=8)
    fig.suptitle("Imperfect-isolation stress test", fontsize=14)
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    path = out_dir / "fig11_backup_stress.png"
    fig.savefig(path, dpi=220, bbox_inches="tight")
    plt.close(fig)
    created.append(path)

    prof = capacity_summary[capacity_summary["portfolio"] == "profile_baseline"]
    ref = float(prof[prof["setting_id"] == "intermediate_reference"][
        "mean_hours_lost"].iloc[0])
    changed = prof[prof["setting_id"] != "intermediate_reference"].copy()
    changed["change_from_intermediate"] = changed["mean_hours_lost"] - ref
    changed = changed.sort_values("change_from_intermediate")
    labels = []
    for _, row in changed.iterrows():
        component = str(row["ablation_component"]).replace("_", " ").title()
        value = "high-capacity" if "high_value" in row["setting_id"] else "resource-constrained"
        labels.append(f"{component}: {value} value")
    fig, ax = plt.subplots(figsize=(8.8, 5.5))
    colors = np.where(changed["change_from_intermediate"] < 0,
                      "#0B6E75", "#C85A54")
    ax.barh(labels,
            changed["change_from_intermediate"], color=colors)
    ax.axvline(0, color="#6B7280", linewidth=1)
    ax.set_xlabel("Change in mean weighted service-hours from intermediate bundle")
    ax.set_title("Detection and segmentation drive the largest one-at-a-time changes")
    ax.tick_params(axis="y", labelsize=8)
    fig.tight_layout()
    path = out_dir / "fig12_capacity_ablation.png"
    fig.savefig(path, dpi=220, bbox_inches="tight")
    plt.close(fig)
    created.append(path)
    return created


def analyze_all(cfg: Config) -> dict[str, Path]:
    raw_dir = resolve_path(cfg.output.raw_dir)
    proc_dir = resolve_path(cfg.output.processed_dir)
    fig_dir = resolve_path(cfg.output.figures_dir)
    ensure_dirs(proc_dir, fig_dir)

    main = pd.read_csv(raw_dir / "confirmatory_main_results.csv")
    sweep = pd.read_csv(raw_dir / "confirmatory_sweep_results.csv")
    main_summary, main_comp, convergence = analyze_paired_main(main, cfg)
    sweep_summary, interaction = analyze_sweep(sweep, cfg)

    discovery = pd.read_csv(raw_dir / "standard_optimization_results.csv")
    discovery_unc = bootstrap_optimizer_uncertainty(
        discovery, cfg, "discovery")
    holdout_path = raw_dir / "confirmatory_optimizer_holdout.csv"
    if holdout_path.exists():
        holdout = pd.read_csv(holdout_path)
        holdout_unc = bootstrap_optimizer_uncertainty(
            holdout, cfg, "holdout")
        optimizer_unc = pd.concat([discovery_unc, holdout_unc],
                                  ignore_index=True)
    else:
        optimizer_unc = discovery_unc
    cost_unc = independent_cost_uncertainty(discovery, cfg)

    sensitivity_raw = pd.read_csv(
        raw_dir / "confirmatory_global_sensitivity.csv")
    sensitivity_setting, sensitivity_corr, sensitivity_robust = (
        analyze_sensitivity(sensitivity_raw))
    capacity_raw = pd.read_csv(raw_dir / "confirmatory_capacity_ablation.csv")
    capacity_summary = _simple_group_summary(
        capacity_raw, ["setting_id", "ablation_component", "ablation_value"])
    backup_raw = pd.read_csv(raw_dir / "confirmatory_backup_stress.csv")
    backup_summary = _simple_group_summary(
        backup_raw, ["setting_id", "isolated_backup_traversal",
                     "restore_rate_multiplier"])
    structural_path = raw_dir / "confirmatory_structural_stress.csv"
    structural_summary = (_simple_group_summary(
        pd.read_csv(structural_path),
        ["setting_id", "structural_variant", "detection_model_variant",
         "horizon_steps_variant", "catastrophic_threshold_steps_variant",
         "service_weight_variant"])
        if structural_path.exists() else pd.DataFrame())

    frames = {
        "confirmatory_main_summary": main_summary,
        "confirmatory_paired_comparisons": main_comp,
        "confirmatory_convergence": convergence,
        "confirmatory_sweep_summary": sweep_summary,
        "confirmatory_interaction_model": interaction,
        "optimizer_ranking_uncertainty": optimizer_unc,
        "independent_cost_uncertainty": cost_unc,
        "sensitivity_setting_results": sensitivity_setting,
        "sensitivity_correlations": sensitivity_corr,
        "sensitivity_robustness": sensitivity_robust,
        "capacity_ablation_summary": capacity_summary,
        "backup_stress_summary": backup_summary,
        "structural_stress_summary": structural_summary,
    }
    outputs: dict[str, Path] = {}
    for name, frame in frames.items():
        path = proc_dir / f"{name}.csv"
        write_csv(frame, path)
        outputs[name] = path
    figures = create_advanced_figures(
        main_comp, sensitivity_setting, optimizer_unc,
        backup_summary, capacity_summary, fig_dir)
    outputs.update({f"figure_{i + 8}": p for i, p in enumerate(figures)})
    manifest = proc_dir / "confirmatory_analysis_manifest.json"
    manifest.write_text(json.dumps({
        "outputs": {k: str(v) for k, v in outputs.items()},
        "uncertainty_methods": {
            "paired_effects": "scenario bootstrap, 4000 resamples",
            "portfolio_rankings": "within-candidate bootstrap, 1000 resamples",
            "costs": "5000 independent log-uniform 0.5x-2x cost vectors",
            "interaction": "logistic model with scenario-clustered sandwich SE",
        },
    }, indent=2), encoding="utf-8")
    outputs["manifest"] = manifest
    return outputs
