"""Sensitivity, capacity-ablation, and imperfect-backup experiments."""

from __future__ import annotations

import copy
import json
import os
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import qmc
from tqdm import tqdm

from .config import Config
from .defenses import DefensePortfolio, get_portfolio
from .enums import BackupStrategy, SegmentationLevel
from .models import TrialSpec
from .simulation import run_trial
from .utilities import ensure_dirs, resolve_path, write_csv

ADVANCED_SEEDS = (20260731, 20260801, 20260802, 20260803, 20260804)


@dataclass
class SettingGroup:
    cfg: Config
    setting_id: str
    metadata: dict[str, object]
    specs: list[TrialSpec]
    portfolios: dict[str, DefensePortfolio]


def _run_group(group: SettingGroup) -> list[dict]:
    rows: list[dict] = []
    for spec in group.specs:
        row = run_trial(group.cfg, spec,
                        portfolio=group.portfolios.get(spec.portfolio))
        row.update(group.metadata)
        row["setting_id"] = group.setting_id
        rows.append(row)
    return rows


def _execute_groups(groups: list[SettingGroup], desc: str) -> pd.DataFrame:
    workers = min(8, os.cpu_count() or 1, max(1, len(groups)))
    rows: list[dict] = []
    if workers == 1:
        for group in tqdm(groups, desc=desc, unit="setting"):
            rows.extend(_run_group(group))
    else:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            for result in tqdm(pool.map(_run_group, groups), total=len(groups),
                               desc=desc, unit="setting"):
                rows.extend(result)
    return pd.DataFrame(rows)


def _paired_specs(cfg: Config, setting_index: int, experiment: str,
                  portfolios: list[str], n_scenarios: int,
                  scenario_offset: int) -> list[TrialSpec]:
    specs: list[TrialSpec] = []
    entries = cfg.experiment.entry_points
    tid = scenario_offset * 10 + setting_index * n_scenarios * len(portfolios)
    for rep in range(n_scenarios):
        scenario_id = scenario_offset + rep
        seed = ADVANCED_SEEDS[rep % len(ADVANCED_SEEDS)]
        entry = entries[rep % len(entries)]
        for portfolio in portfolios:
            specs.append(TrialSpec(
                trial_id=tid, experiment=experiment,
                facility="regional_hospital",
                profile="intermediate_capacity", portfolio=portfolio,
                entry_point=entry, master_seed=seed,
                scenario_id=scenario_id, paired=True))
            tid += 1
    return specs


SENSITIVITY_RANGES: dict[str, tuple[float, float]] = {
    "base_spread_rate": (0.20, 0.50),
    "patch_effectiveness": (0.50, 0.95),
    "intra_zone_degree": (2.0, 5.0),
    "cross_zone_out_degree": (1.0, 4.0),
    "identity_breach_multiplier": (1.0, 2.0),
    "restore_rate_fraction": (0.01, 0.04),
    "service_functional_fraction": (0.45, 0.75),
    "false_positive_rate": (0.0, 0.005),
    "legacy_fraction": (0.05, 0.35),
    "isolation_success": (0.50, 0.95),
    "detection_delay_steps": (3.0, 24.0),
    "isolated_backup_traversal": (0.0, 0.10),
}


def _apply_sensitivity_values(cfg: Config,
                              values: dict[str, float]) -> None:
    sim = cfg.simulation
    net = cfg.network
    prof = cfg.profiles["intermediate_capacity"]
    sim.base_spread_rate = values["base_spread_rate"]
    sim.patch_effectiveness = values["patch_effectiveness"]
    net.intra_zone_degree = values["intra_zone_degree"]
    net.cross_zone_out_degree = values["cross_zone_out_degree"]
    sim.identity_breach_multiplier = values["identity_breach_multiplier"]
    sim.restore_rate_fraction = values["restore_rate_fraction"]
    sim.service_functional_fraction = values["service_functional_fraction"]
    sim.false_positive_rate = values["false_positive_rate"]
    prof.legacy_fraction = values["legacy_fraction"]
    prof.isolation_success = values["isolation_success"]
    prof.detection_delay_steps = int(round(values["detection_delay_steps"]))
    net.backup_traversal["isolated"] = values[
        "isolated_backup_traversal"]
    cfg.validate()


def run_global_sensitivity(cfg: Config, n_settings: int = 100,
                           n_scenarios: int = 15) -> dict[str, Path]:
    """Run a Latin-hypercube sensitivity study on twelve assumptions."""
    names = list(SENSITIVITY_RANGES)
    sampler = qmc.LatinHypercube(d=len(names), seed=20260718)
    unit = sampler.random(n_settings)
    lows = np.array([SENSITIVITY_RANGES[n][0] for n in names])
    highs = np.array([SENSITIVITY_RANGES[n][1] for n in names])
    matrix = qmc.scale(unit, lows, highs)
    portfolio_names = ["baseline_flat", "seg_detect_backup", "full_defense"]
    portfolio_map = {n: get_portfolio(n) for n in portfolio_names}
    groups: list[SettingGroup] = []
    parameters: list[dict[str, object]] = []
    for i, row in enumerate(matrix):
        values = {name: float(value) for name, value in zip(names, row)}
        setting_cfg = copy.deepcopy(cfg)
        setting_cfg.experiment.workers = 1
        _apply_sensitivity_values(setting_cfg, values)
        setting_id = f"lhs_{i:03d}"
        parameters.append({"setting_id": setting_id, **values})
        groups.append(SettingGroup(
            cfg=setting_cfg, setting_id=setting_id, metadata=values,
            specs=_paired_specs(
                setting_cfg, i, "global_sensitivity", portfolio_names,
                n_scenarios, scenario_offset=40_000_000),
            portfolios=portfolio_map))
    raw = _execute_groups(groups, "global sensitivity")
    raw_dir = resolve_path(cfg.output.raw_dir)
    proc_dir = resolve_path(cfg.output.processed_dir)
    ensure_dirs(raw_dir, proc_dir)
    raw_path = raw_dir / "confirmatory_global_sensitivity.csv"
    param_path = proc_dir / "confirmatory_sensitivity_parameters.csv"
    write_csv(raw, raw_path)
    write_csv(pd.DataFrame(parameters), param_path)
    return {"raw": raw_path, "parameters": param_path}


def run_capacity_ablation(cfg: Config, n_scenarios: int = 100
                          ) -> dict[str, Path]:
    """Change one capacity-profile component at a time around intermediate."""
    base = cfg.profiles["intermediate_capacity"]
    low = cfg.profiles["resource_constrained"]
    high = cfg.profiles["high_capacity"]
    fields = [
        "patch_coverage", "detection_delay_steps", "isolation_success",
        "legacy_fraction", "base_segmentation", "backup_strategy",
        "complexity_factor",
    ]
    settings: list[tuple[str, str | None, object | None]] = [
        ("intermediate_reference", None, None)]
    for field in fields:
        settings.append((f"{field}_resource_value", field,
                         getattr(low, field)))
        settings.append((f"{field}_high_value", field,
                         getattr(high, field)))
    portfolio_names = ["baseline_flat", "profile_baseline", "full_defense"]
    portfolio_map = {n: get_portfolio(n) for n in portfolio_names}
    groups: list[SettingGroup] = []
    for i, (label, field, value) in enumerate(settings):
        setting_cfg = copy.deepcopy(cfg)
        setting_cfg.experiment.workers = 1
        if field is not None:
            setattr(setting_cfg.profiles["intermediate_capacity"], field, value)
        setting_cfg.validate()
        metadata = {
            "ablation_component": field or "reference",
            "ablation_value": str(value) if field else "intermediate",
        }
        groups.append(SettingGroup(
            cfg=setting_cfg, setting_id=label, metadata=metadata,
            specs=_paired_specs(
                setting_cfg, i, "capacity_ablation", portfolio_names,
                n_scenarios, scenario_offset=50_000_000),
            portfolios=portfolio_map))
    raw = _execute_groups(groups, "capacity ablation")
    raw_dir = resolve_path(cfg.output.raw_dir)
    ensure_dirs(raw_dir)
    path = raw_dir / "confirmatory_capacity_ablation.csv"
    write_csv(raw, path)
    return {"raw": path}


def run_backup_stress(cfg: Config, n_scenarios: int = 100
                      ) -> dict[str, Path]:
    """Stress isolated backups with residual paths and recovery-rate changes."""
    traversal_levels = (0.00, 0.01, 0.05, 0.10)
    restore_multipliers = (0.5, 1.0, 1.5)
    portfolio_names = ["backup_connected", "backup_isolated"]
    portfolios = {
        "backup_connected": DefensePortfolio(
            "backup_connected", segmentation=SegmentationLevel.FLAT,
            backup_override=BackupStrategy.CONNECTED),
        "backup_isolated": DefensePortfolio(
            "backup_isolated", segmentation=SegmentationLevel.FLAT,
            backup_override=BackupStrategy.ISOLATED),
    }
    groups: list[SettingGroup] = []
    i = 0
    for traversal in traversal_levels:
        for restore_mult in restore_multipliers:
            setting_cfg = copy.deepcopy(cfg)
            setting_cfg.experiment.workers = 1
            setting_cfg.network.backup_traversal["isolated"] = traversal
            setting_cfg.simulation.restore_rate_fraction *= restore_mult
            setting_cfg.validate()
            metadata = {
                "isolated_backup_traversal": traversal,
                "restore_rate_multiplier": restore_mult,
            }
            groups.append(SettingGroup(
                cfg=setting_cfg,
                setting_id=f"backup_t{traversal:.2f}_r{restore_mult:.1f}",
                metadata=metadata,
                specs=_paired_specs(
                    setting_cfg, i, "backup_stress", portfolio_names,
                    n_scenarios, scenario_offset=60_000_000),
                portfolios=portfolios))
            i += 1
    raw = _execute_groups(groups, "backup stress")
    raw_dir = resolve_path(cfg.output.raw_dir)
    ensure_dirs(raw_dir)
    path = raw_dir / "confirmatory_backup_stress.csv"
    write_csv(raw, path)
    return {"raw": path}


def run_structural_stress(cfg: Config, n_scenarios: int = 100
                          ) -> dict[str, Path]:
    """One-at-a-time structural alternatives for timing and outcomes."""
    settings: list[tuple[str, dict[str, object]]] = [
        ("reference", {}),
        ("fixed_detection", {"detection_model": "fixed"}),
        ("horizon_24h", {"max_steps": 96}),
        ("horizon_72h", {"max_steps": 288}),
        ("catastrophic_threshold_1h", {"catastrophic_service_steps": 4}),
        ("catastrophic_threshold_4h", {"catastrophic_service_steps": 16}),
        ("equal_service_weights", {"service_weights": "equal"}),
        ("clinical_priority_weights", {"service_weights": "clinical"}),
        ("recovery_priority_weights", {"service_weights": "recovery"}),
    ]
    portfolio_names = ["baseline_flat", "seg_detect_backup", "full_defense"]
    portfolio_map = {n: get_portfolio(n) for n in portfolio_names}
    groups: list[SettingGroup] = []
    for i, (label, changes) in enumerate(settings):
        setting_cfg = copy.deepcopy(cfg)
        setting_cfg.experiment.workers = 1
        if "detection_model" in changes:
            setting_cfg.simulation.detection_model = str(
                changes["detection_model"])
        if "max_steps" in changes:
            setting_cfg.simulation.max_steps = int(changes["max_steps"])
        if "catastrophic_service_steps" in changes:
            setting_cfg.simulation.catastrophic_service_steps = int(
                changes["catastrophic_service_steps"])
        weights = changes.get("service_weights")
        if weights == "equal":
            for name in vars(setting_cfg.service_weights):
                setattr(setting_cfg.service_weights, name, 1.0)
        elif weights == "clinical":
            setting_cfg.service_weights.ehr = 1.2
            setting_cfg.service_weights.laboratory = 1.0
            setting_cfg.service_weights.pharmacy = 1.1
            setting_cfg.service_weights.imaging = 1.0
            setting_cfg.service_weights.scheduling = 0.3
            setting_cfg.service_weights.identity = 0.8
            setting_cfg.service_weights.backup_recovery = 0.5
        elif weights == "recovery":
            setting_cfg.service_weights.backup_recovery = 1.2
            setting_cfg.service_weights.identity = 1.1
        setting_cfg.validate()
        metadata = {
            "structural_variant": label,
            "detection_model_variant": setting_cfg.simulation.detection_model,
            "horizon_steps_variant": setting_cfg.simulation.max_steps,
            "catastrophic_threshold_steps_variant":
                setting_cfg.simulation.catastrophic_service_steps,
            "service_weight_variant": str(weights or "reference"),
        }
        groups.append(SettingGroup(
            cfg=setting_cfg, setting_id=label, metadata=metadata,
            specs=_paired_specs(
                setting_cfg, i, "structural_stress", portfolio_names,
                n_scenarios, scenario_offset=70_000_000),
            portfolios=portfolio_map))
    raw = _execute_groups(groups, "structural stress")
    raw_dir = resolve_path(cfg.output.raw_dir)
    ensure_dirs(raw_dir)
    path = raw_dir / "confirmatory_structural_stress.csv"
    write_csv(raw, path)
    return {"raw": path}


def run_all_advanced(cfg: Config) -> dict[str, object]:
    outputs = {
        "sensitivity": run_global_sensitivity(cfg),
        "capacity_ablation": run_capacity_ablation(cfg),
        "backup_stress": run_backup_stress(cfg),
        "structural_stress": run_structural_stress(cfg),
    }
    manifest = resolve_path(cfg.output.raw_dir) / "advanced_manifest.json"
    repo_root = Path(__file__).resolve().parents[2]
    manifest.write_text(json.dumps({
        "design": "paired robustness experiments",
        "advanced_seeds": list(ADVANCED_SEEDS),
        "outputs": {k: {a: str(Path(b).resolve().relative_to(repo_root))
                        for a, b in v.items()}
                    for k, v in outputs.items()},
    }, indent=2), encoding="utf-8")
    return outputs
