"""Prespecified summaries for the fresh public-evidence validation phase."""

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

from .config import Config
from .statistics import wilson_ci
from .utilities import ensure_dirs, resolve_path, write_csv


PAIR_KEYS = ["master_seed", "scenario_id", "entry_point"]
LABELS = {
    "baseline_flat": "Flat reference",
    "seg_detect_backup": "Layered portfolio",
    "full_defense": "Full portfolio",
}
COLORS = {
    "baseline_flat": "#6B7280",
    "seg_detect_backup": "#1F6F78",
    "full_defense": "#B05A3C",
}


def _paired(primary: pd.DataFrame, treatment: str) -> pd.DataFrame:
    baseline = primary[primary["portfolio"] == "baseline_flat"]
    treated = primary[primary["portfolio"] == treatment]
    return baseline.merge(treated, on=PAIR_KEYS, suffixes=("_base", "_tx"))


def _bootstrap_mean(values: np.ndarray, *, seed: int,
                    n_boot: int = 8000) -> tuple[float, float]:
    values = np.asarray(values, dtype=float)
    rng = np.random.default_rng(seed)
    means = np.empty(n_boot)
    # Chunking avoids a large temporary matrix for future larger studies.
    for start in range(0, n_boot, 1000):
        stop = min(start + 1000, n_boot)
        idx = rng.integers(0, len(values), size=(stop - start, len(values)))
        means[start:stop] = values[idx].mean(axis=1)
    return tuple(float(x) for x in np.percentile(means, [2.5, 97.5]))


def primary_summary(primary: pd.DataFrame, seed: int) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    treatments = [name for name in ("seg_detect_backup", "full_defense")
                  if name in set(primary["portfolio"])]
    for i, treatment in enumerate(treatments):
        pair = _paired(primary, treatment)
        baseline = pair["weighted_service_hours_lost_base"].to_numpy(float)
        treated = pair["weighted_service_hours_lost_tx"].to_numpy(float)
        difference = treated - baseline
        lo, hi = _bootstrap_mean(difference, seed=seed + i)
        base_cat = pair["catastrophic_base"].to_numpy(int)
        tx_cat = pair["catastrophic_tx"].to_numpy(int)
        rows.append({
            "treatment": treatment,
            "n_pairs": len(pair),
            "baseline_mean_hours": baseline.mean(),
            "treatment_mean_hours": treated.mean(),
            "paired_mean_difference_hours": difference.mean(),
            "paired_median_difference_hours": np.median(difference),
            "paired_difference_ci95_lo": lo,
            "paired_difference_ci95_hi": hi,
            "relative_reduction_of_means": (
                1.0 - treated.mean() / baseline.mean()),
            "scenarios_with_lower_loss_fraction": (difference < 0).mean(),
            "difference_p05": np.quantile(difference, 0.05),
            "difference_p95": np.quantile(difference, 0.95),
            "baseline_sustained_outage_fraction": base_cat.mean(),
            "treatment_sustained_outage_fraction": tx_cat.mean(),
            "paired_sustained_outage_risk_difference": (
                tx_cat - base_cat).mean(),
            "paired_difference_sd": difference.std(ddof=1),
            "monte_carlo_standard_error": (
                difference.std(ddof=1) / np.sqrt(len(difference))),
            "protocol_mcse_target": 0.02 * baseline.mean(),
        })
    return pd.DataFrame(rows)


def service_specific_summary(primary: pd.DataFrame) -> pd.DataFrame:
    """Report unweighted service outcomes so weights cannot hide drivers."""
    services = ("ehr", "laboratory", "pharmacy", "imaging", "scheduling",
                "identity", "backup_recovery")
    rows: list[dict[str, object]] = []
    for portfolio, group in primary.groupby("portfolio"):
        step_hours = group["step_minutes"].to_numpy(float) / 60.0
        for service in services:
            values = (group[f"{service}_downtime_steps"].to_numpy(float)
                      * step_hours)
            rows.append({
                "portfolio": portfolio, "service": service,
                "n": len(values), "mean_downtime_hours": values.mean(),
                "median_downtime_hours": np.median(values),
                "scenarios_with_any_downtime_fraction": (values > 0).mean(),
                "downtime_hours_p95": np.quantile(values, 0.95),
            })
    return pd.DataFrame(rows)


def replication_summary(replication: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for (facility, profile), cell in replication.groupby(
            ["facility", "profile"]):
        for treatment in ("seg_detect_backup", "full_defense"):
            pair = _paired(cell, treatment)
            baseline = pair["weighted_service_hours_lost_base"].to_numpy(float)
            treated = pair["weighted_service_hours_lost_tx"].to_numpy(float)
            difference = treated - baseline
            rows.append({
                "facility": facility, "profile": profile,
                "treatment": treatment, "n_pairs": len(pair),
                "baseline_mean_hours": baseline.mean(),
                "treatment_mean_hours": treated.mean(),
                "paired_mean_difference_hours": difference.mean(),
                "relative_reduction_of_means": (
                    1.0 - treated.mean() / baseline.mean()
                    if baseline.mean() else np.nan),
                "scenarios_with_lower_loss_fraction": (difference < 0).mean(),
            })
    return pd.DataFrame(rows)


def stress_summary(stress: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    means = (stress.groupby(["setting_id", "portfolio"])
             ["weighted_service_hours_lost"].mean().unstack())
    rows: list[dict[str, object]] = []
    setting_rows: list[pd.DataFrame] = []
    treatments = [name for name in ("seg_detect_backup", "full_defense")
                  if name in means.columns]
    for treatment in treatments:
        reduction = 1.0 - means[treatment] / means["baseline_flat"]
        favorable = means[treatment] < means["baseline_flat"]
        count = int(favorable.sum())
        lo, hi = wilson_ci(count, len(favorable))
        rows.append({
            "treatment": treatment,
            "n_parameter_settings": len(favorable),
            "settings_favoring_treatment": count,
            "fraction_settings_favoring_treatment": favorable.mean(),
            "favoring_fraction_wilson_ci95_lo": lo,
            "favoring_fraction_wilson_ci95_hi": hi,
            "median_relative_reduction": reduction.median(),
            "relative_reduction_p05": reduction.quantile(0.05),
            "relative_reduction_p95": reduction.quantile(0.95),
        })
        setting_rows.append(pd.DataFrame({
            "setting_id": means.index,
            "treatment": treatment,
            "baseline_mean_hours": means["baseline_flat"].to_numpy(),
            "treatment_mean_hours": means[treatment].to_numpy(),
            "relative_reduction": reduction.to_numpy(),
            "treatment_favored": favorable.to_numpy(dtype=int),
        }))
    return pd.DataFrame(rows), pd.concat(setting_rows, ignore_index=True)


def variant_summary(raw: pd.DataFrame, variant: str) -> pd.DataFrame:
    return (raw.groupby([variant, "portfolio"])
            .agg(n=("trial_id", "size"),
                 mean_hours_lost=("weighted_service_hours_lost", "mean"),
                 median_hours_lost=("weighted_service_hours_lost", "median"),
                 sustained_outage_fraction=("catastrophic", "mean"),
                 recovery_within_horizon_fraction=(
                     "recovered_within_horizon", "mean"),
                 mean_steps_simulated=("steps_simulated", "mean"))
            .reset_index())


def _make_figures(primary: pd.DataFrame, setting: pd.DataFrame,
                  horizon: pd.DataFrame, out_dir: Path) -> list[Path]:
    ensure_dirs(out_dir)
    plt.rcParams.update({
        "font.family": "DejaVu Sans", "font.size": 9,
        "axes.spines.top": False, "axes.spines.right": False,
        "axes.linewidth": 0.7, "xtick.major.width": 0.7,
        "ytick.major.width": 0.7,
    })
    created: list[Path] = []

    fig, ax = plt.subplots(figsize=(6.5, 3.7))
    for treatment in ("seg_detect_backup", "full_defense"):
        pair = _paired(primary, treatment)
        diff = np.sort((pair["weighted_service_hours_lost_tx"]
                        - pair["weighted_service_hours_lost_base"])
                       .to_numpy(float))
        probability = np.arange(1, len(diff) + 1) / len(diff)
        ax.step(diff, probability, where="post", linewidth=1.8,
                color=COLORS[treatment], label=LABELS[treatment])
    ax.axvline(0, color="#374151", linewidth=0.8, linestyle="--")
    ax.set_xlabel("Paired change in weighted service-hours (portfolio - reference)")
    ax.set_ylabel("Cumulative fraction of scenarios")
    ax.legend(frameon=False, loc="lower right")
    fig.tight_layout()
    path = out_dir / "validation_paired_effect_distribution.pdf"
    fig.savefig(path, bbox_inches="tight")
    fig.savefig(path.with_suffix(".png"), dpi=240, bbox_inches="tight")
    plt.close(fig)
    created.extend([path, path.with_suffix(".png")])

    fig, ax = plt.subplots(figsize=(6.5, 3.7))
    for treatment in ("seg_detect_backup", "full_defense"):
        values = np.sort(setting.loc[
            setting["treatment"] == treatment,
            "relative_reduction"].to_numpy(float) * 100)
        probability = np.arange(1, len(values) + 1) / len(values)
        ax.step(values, probability, where="post", linewidth=1.8,
                color=COLORS[treatment], label=LABELS[treatment])
    ax.axvline(0, color="#374151", linewidth=0.8, linestyle="--")
    ax.set_xlabel("Reduction from reference across joint stress settings (%)")
    ax.set_ylabel("Cumulative fraction of settings")
    ax.legend(frameon=False, loc="lower right")
    fig.tight_layout()
    path = out_dir / "validation_joint_stress_distribution.pdf"
    fig.savefig(path, bbox_inches="tight")
    fig.savefig(path.with_suffix(".png"), dpi=240, bbox_inches="tight")
    plt.close(fig)
    created.extend([path, path.with_suffix(".png")])

    fig, ax = plt.subplots(figsize=(6.5, 3.7))
    for portfolio in ("baseline_flat", "seg_detect_backup", "full_defense"):
        sub = horizon[horizon["portfolio"] == portfolio].sort_values(
            "horizon_hours_variant")
        ax.plot(sub["horizon_hours_variant"] / 24,
                sub["recovery_within_horizon_fraction"] * 100,
                marker="o", linewidth=1.7, color=COLORS[portfolio],
                label=LABELS[portfolio])
    ax.set_xticks([3, 7, 21])
    ax.set_xlabel("Modeled horizon (days)")
    ax.set_ylabel("Scenarios recovered within horizon (%)")
    ax.set_ylim(0, 103)
    ax.legend(frameon=False, loc="lower right")
    fig.tight_layout()
    path = out_dir / "validation_recovery_horizon.pdf"
    fig.savefig(path, bbox_inches="tight")
    fig.savefig(path.with_suffix(".png"), dpi=240, bbox_inches="tight")
    plt.close(fig)
    created.extend([path, path.with_suffix(".png")])
    return created


def analyze_public_validation(cfg: Config) -> dict[str, Path]:
    raw_dir = resolve_path(cfg.output.raw_dir)
    processed_dir = resolve_path(cfg.output.processed_dir)
    figure_dir = resolve_path(cfg.output.figures_dir)
    ensure_dirs(processed_dir, figure_dir)

    primary = pd.read_csv(raw_dir / "primary_paired.csv")
    replication = pd.read_csv(raw_dir / "cross_setting_replication.csv")
    stress = pd.read_csv(raw_dir / "joint_stress.csv")
    step = pd.read_csv(raw_dir / "time_step_convergence.csv")
    horizon = pd.read_csv(raw_dir / "recovery_horizon.csv")

    outputs: dict[str, Path] = {}
    primary_out = primary_summary(primary, cfg.seed)
    outputs["primary"] = processed_dir / "primary_summary.csv"
    write_csv(primary_out, outputs["primary"])

    service_out = service_specific_summary(primary)
    outputs["services"] = processed_dir / "primary_service_summary.csv"
    write_csv(service_out, outputs["services"])

    replication_out = replication_summary(replication)
    outputs["replication"] = processed_dir / "cross_setting_summary.csv"
    write_csv(replication_out, outputs["replication"])

    stress_out, setting_out = stress_summary(stress)
    outputs["stress"] = processed_dir / "joint_stress_summary.csv"
    outputs["stress_setting"] = processed_dir / "joint_stress_setting_results.csv"
    write_csv(stress_out, outputs["stress"])
    write_csv(setting_out, outputs["stress_setting"])

    step_out = variant_summary(step, "time_step_minutes_variant")
    outputs["step"] = processed_dir / "time_step_summary.csv"
    write_csv(step_out, outputs["step"])

    horizon_out = variant_summary(horizon, "horizon_hours_variant")
    outputs["horizon"] = processed_dir / "recovery_horizon_summary.csv"
    write_csv(horizon_out, outputs["horizon"])

    figures = _make_figures(primary, setting_out, horizon_out, figure_dir)
    analysis_manifest = {
        "analysis": "prespecified public-evidence validation summaries",
        "primary_success": bool(
            primary_out.loc[
                primary_out["treatment"] == "seg_detect_backup",
                "paired_difference_ci95_hi"].iloc[0] < 0),
        "robustness_success": bool(
            stress_out.loc[
                stress_out["treatment"] == "seg_detect_backup",
                "fraction_settings_favoring_treatment"].iloc[0] >= 0.95
            and stress_out.loc[
                stress_out["treatment"] == "seg_detect_backup",
                "relative_reduction_p05"].iloc[0] > 0),
        "figures": [str(path) for path in figures],
    }
    outputs["manifest"] = processed_dir / "analysis_manifest.json"
    outputs["manifest"].write_text(
        json.dumps(analysis_manifest, indent=2), encoding="utf-8")
    return outputs
