#!/usr/bin/env python3
"""Analyze the five-minute replication with the common paired summaries."""

import json
from pathlib import Path

import pandas as pd

from grrc.config import load_config
from grrc.public_validation_analysis import (
    _make_figures, primary_summary, service_specific_summary, stress_summary)
from grrc.utilities import ensure_dirs, resolve_path, write_csv

REPO = Path(__file__).resolve().parents[1]
CFG = load_config(REPO / "configs" / "fine_step_replication.yaml")

if __name__ == "__main__":
    raw_dir = resolve_path(CFG.output.raw_dir)
    processed_dir = resolve_path(CFG.output.processed_dir)
    figure_dir = resolve_path(CFG.output.figures_dir)
    ensure_dirs(processed_dir, figure_dir)
    primary = pd.read_csv(raw_dir / "primary_paired.csv")
    stress = pd.read_csv(raw_dir / "joint_stress.csv")
    primary_out = primary_summary(primary, CFG.seed)
    primary_out = primary_out[
        primary_out["treatment"] == "seg_detect_backup"].reset_index(drop=True)
    service_out = service_specific_summary(primary)
    stress_out, settings = stress_summary(stress)
    stress_out = stress_out[
        stress_out["treatment"] == "seg_detect_backup"].reset_index(drop=True)
    settings = settings[
        settings["treatment"] == "seg_detect_backup"].reset_index(drop=True)
    write_csv(primary_out, processed_dir / "primary_summary.csv")
    write_csv(service_out, processed_dir / "primary_service_summary.csv")
    write_csv(stress_out, processed_dir / "joint_stress_summary.csv")
    write_csv(settings, processed_dir / "joint_stress_setting_results.csv")

    # Reuse the two evidence-bearing distribution plots; horizon is reported
    # from the 15-minute diagnostic and is intentionally not mixed here.
    import matplotlib.pyplot as plt
    from grrc.public_validation_analysis import COLORS, LABELS, PAIR_KEYS
    baseline = primary[primary["portfolio"] == "baseline_flat"]
    treated = primary[primary["portfolio"] == "seg_detect_backup"]
    pair = baseline.merge(treated, on=PAIR_KEYS, suffixes=("_base", "_tx"))
    diff = (pair["weighted_service_hours_lost_tx"]
            - pair["weighted_service_hours_lost_base"]).sort_values().to_numpy()
    probability = (pd.Series(range(1, len(diff) + 1)) / len(diff)).to_numpy()
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9,
                         "axes.spines.top": False,
                         "axes.spines.right": False})
    fig, ax = plt.subplots(figsize=(6.5, 3.7))
    ax.step(diff, probability, where="post", linewidth=1.8,
            color=COLORS["seg_detect_backup"],
            label=LABELS["seg_detect_backup"])
    ax.axvline(0, color="#374151", linewidth=0.8, linestyle="--")
    ax.set_xlabel("Paired change in weighted service-hours (portfolio - reference)")
    ax.set_ylabel("Cumulative fraction of scenarios")
    ax.legend(frameon=False, loc="lower right")
    fig.tight_layout()
    for suffix in ("pdf", "png"):
        fig.savefig(figure_dir / f"fine_step_paired_effect_distribution.{suffix}",
                    dpi=240 if suffix == "png" else None,
                    bbox_inches="tight")
    plt.close(fig)

    values = settings["relative_reduction"].sort_values().to_numpy() * 100
    probability = (pd.Series(range(1, len(values) + 1)) / len(values)).to_numpy()
    fig, ax = plt.subplots(figsize=(6.5, 3.7))
    ax.step(values, probability, where="post", linewidth=1.8,
            color=COLORS["seg_detect_backup"],
            label=LABELS["seg_detect_backup"])
    ax.axvline(0, color="#374151", linewidth=0.8, linestyle="--")
    ax.set_xlabel("Reduction from reference across joint stress settings (%)")
    ax.set_ylabel("Cumulative fraction of settings")
    ax.legend(frameon=False, loc="lower right")
    fig.tight_layout()
    for suffix in ("pdf", "png"):
        fig.savefig(figure_dir / f"fine_step_joint_stress_distribution.{suffix}",
                    dpi=240 if suffix == "png" else None,
                    bbox_inches="tight")
    plt.close(fig)

    manifest = {
        "primary_success": bool(primary_out["paired_difference_ci95_hi"].iloc[0] < 0),
        "robustness_success": bool(
            stress_out["fraction_settings_favoring_treatment"].iloc[0] >= 0.95
            and stress_out["relative_reduction_p05"].iloc[0] > 0),
    }
    (processed_dir / "analysis_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8")
