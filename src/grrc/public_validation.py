"""Fresh public-evidence validation experiments.

The observational literature constrains operational windows and validation
patterns, but not universal cyber-transition probabilities. Accordingly, this
module treats mechanistic inputs as broad stress variables and keeps all
portfolio comparisons paired within the same latent scenario.
"""

from __future__ import annotations

import copy
import hashlib
import json
import time
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import qmc

from .advanced_experiments import SettingGroup, _execute_groups
from .config import Config
from .defenses import get_portfolio
from .experiments import run_specs
from .models import TrialSpec
from .utilities import ensure_dirs, resolve_path, write_csv


VALIDATION_SEEDS = (3701001, 3701002, 3701003, 3701004, 3701005)
PORTFOLIOS = ("baseline_flat", "seg_detect_backup", "full_defense")

# Deliberately broad stress ranges, not fitted hospital estimates.
STRESS_RANGES: dict[str, tuple[float, float]] = {
    "base_spread_rate": (0.05, 0.50),
    "patch_effectiveness": (0.30, 0.95),
    "intra_zone_degree": (2.0, 5.0),
    "cross_zone_out_degree": (1.0, 4.0),
    "identity_breach_multiplier": (1.0, 2.0),
    "restore_rate_fraction": (0.0025, 0.04),
    "no_backup_restore_penalty": (0.10, 0.50),
    "service_functional_fraction": (0.45, 0.75),
    "false_positive_rate": (0.0, 0.002),
    "legacy_fraction": (0.05, 0.35),
    "isolation_success": (0.25, 0.95),
    "detection_delay_steps": (3.0, 96.0),
    "isolated_backup_traversal": (0.0, 0.10),
}


def _specs(*, experiment: str, facility: str, profile: str,
           n_scenarios: int, scenario_offset: int,
           portfolios: tuple[str, ...] = PORTFOLIOS) -> list[TrialSpec]:
    specs: list[TrialSpec] = []
    entries = ("workstation", "internet_facing", "privileged_system",
               "medical_device", "vendor_connection")
    trial_id = scenario_offset * 10
    for rep in range(n_scenarios):
        scenario_id = scenario_offset + rep
        seed = VALIDATION_SEEDS[rep % len(VALIDATION_SEEDS)]
        entry = entries[rep % len(entries)]
        for portfolio in portfolios:
            specs.append(TrialSpec(
                trial_id=trial_id, experiment=experiment,
                facility=facility, profile=profile, portfolio=portfolio,
                entry_point=entry, master_seed=seed,
                scenario_id=scenario_id, paired=True))
            trial_id += 1
    return specs


def _apply_stress(cfg: Config, values: dict[str, float]) -> None:
    sim = cfg.simulation
    net = cfg.network
    profile = cfg.profiles["intermediate_posture"]
    sim.base_spread_rate = values["base_spread_rate"]
    sim.patch_effectiveness = values["patch_effectiveness"]
    net.intra_zone_degree = values["intra_zone_degree"]
    net.cross_zone_out_degree = values["cross_zone_out_degree"]
    sim.identity_breach_multiplier = values["identity_breach_multiplier"]
    sim.restore_rate_fraction = values["restore_rate_fraction"]
    sim.no_backup_restore_penalty = values["no_backup_restore_penalty"]
    sim.service_functional_fraction = values[
        "service_functional_fraction"]
    sim.false_positive_rate = values["false_positive_rate"]
    profile.legacy_fraction = values["legacy_fraction"]
    profile.isolation_success = values["isolation_success"]
    profile.detection_delay_steps = int(round(
        values["detection_delay_steps"]))
    net.backup_traversal["isolated"] = values[
        "isolated_backup_traversal"]
    cfg.validate()


def _hazard_for_step(probability_15m: float, step_minutes: int) -> float:
    """Convert a 15-minute Bernoulli hazard to another step duration."""
    return 1.0 - (1.0 - probability_15m) ** (step_minutes / 15.0)


def _clock_time_config(cfg: Config, step_minutes: int,
                       horizon_hours: int = 72) -> Config:
    """Preserve clock-time hazards and durations at a new time step."""
    out = copy.deepcopy(cfg)
    scale = step_minutes / 15.0
    sim = out.simulation
    sim.step_minutes = step_minutes
    sim.max_steps = int(round(horizon_hours * 60 / step_minutes))
    sim.base_spread_rate = _hazard_for_step(
        sim.base_spread_rate, step_minutes)
    sim.false_positive_rate = _hazard_for_step(
        sim.false_positive_rate, step_minutes)
    sim.rapid_isolation_success = _hazard_for_step(
        sim.rapid_isolation_success, step_minutes)
    sim.false_positive_duration = max(1, int(round(
        sim.false_positive_duration / scale)))
    sim.restore_rate_fraction *= scale
    sim.restore_rate_min *= scale
    sim.restore_duration = max(1, int(round(sim.restore_duration / scale)))
    sim.catastrophic_service_steps = max(1, int(round(
        sim.catastrophic_service_steps / scale)))
    for profile in out.profiles.values():
        profile.detection_delay_steps = max(1, int(round(
            profile.detection_delay_steps / scale)))
        profile.isolation_success = _hazard_for_step(
            profile.isolation_success, step_minutes)
    out.validate()
    return out


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_public_validation(cfg: Config, config_path: Path) -> dict[str, Path]:
    """Execute the frozen fresh validation and write an audit manifest."""
    started = time.time()
    raw_dir = resolve_path(cfg.output.raw_dir)
    ensure_dirs(raw_dir)

    primary_specs = _specs(
        experiment="public_validation_primary", facility="scale_2",
        profile="intermediate_posture", n_scenarios=500,
        scenario_offset=81_000_000)
    primary = run_specs(cfg, primary_specs, desc="validation:primary")
    primary_path = raw_dir / "primary_paired.csv"
    write_csv(primary, primary_path)

    replication_specs: list[TrialSpec] = []
    offset = 82_000_000
    for facility in cfg.experiment.facilities:
        for profile in cfg.experiment.profiles:
            replication_specs.extend(_specs(
                experiment="public_validation_replication",
                facility=facility, profile=profile, n_scenarios=100,
                scenario_offset=offset))
            offset += 10_000
    replication = run_specs(
        cfg, replication_specs, desc="validation:cross-setting")
    replication_path = raw_dir / "cross_setting_replication.csv"
    write_csv(replication, replication_path)

    names = list(STRESS_RANGES)
    unit = qmc.LatinHypercube(d=len(names), seed=cfg.seed).random(128)
    lows = np.array([STRESS_RANGES[n][0] for n in names])
    highs = np.array([STRESS_RANGES[n][1] for n in names])
    matrix = qmc.scale(unit, lows, highs)
    groups: list[SettingGroup] = []
    stress_parameters: list[dict[str, object]] = []
    portfolio_map = {name: get_portfolio(name) for name in PORTFOLIOS}
    for index, row in enumerate(matrix):
        values = {name: float(value) for name, value in zip(names, row)}
        setting_cfg = copy.deepcopy(cfg)
        setting_cfg.experiment.workers = 1
        _apply_stress(setting_cfg, values)
        setting_id = f"lhs_{index:03d}"
        stress_parameters.append({"setting_id": setting_id, **values})
        groups.append(SettingGroup(
            cfg=setting_cfg, setting_id=setting_id, metadata=values,
            specs=_specs(
                experiment="public_validation_joint_stress",
                facility="scale_2", profile="intermediate_posture",
                n_scenarios=20, scenario_offset=83_000_000 + index * 100),
            portfolios=portfolio_map))
    stress = _execute_groups(groups, "validation:joint-stress")
    stress_path = raw_dir / "joint_stress.csv"
    write_csv(stress, stress_path)
    stress_parameter_path = raw_dir / "joint_stress_parameters.csv"
    write_csv(pd.DataFrame(stress_parameters), stress_parameter_path)

    step_groups: list[SettingGroup] = []
    for index, minutes in enumerate((5, 15, 30)):
        step_cfg = _clock_time_config(cfg, minutes)
        step_groups.append(SettingGroup(
            cfg=step_cfg, setting_id=f"step_{minutes}m",
            metadata={"time_step_minutes_variant": minutes},
            specs=_specs(
                experiment="public_validation_step_convergence",
                facility="scale_2", profile="intermediate_posture",
                n_scenarios=100,
                scenario_offset=84_000_000 + index * 10_000),
            portfolios=portfolio_map))
    step_results = _execute_groups(step_groups, "validation:time-step")
    step_path = raw_dir / "time_step_convergence.csv"
    write_csv(step_results, step_path)

    horizon_groups: list[SettingGroup] = []
    for index, hours in enumerate((72, 168, 504)):
        horizon_cfg = copy.deepcopy(cfg)
        horizon_cfg.simulation.max_steps = int(
            hours * 60 / horizon_cfg.simulation.step_minutes)
        horizon_cfg.validate()
        horizon_groups.append(SettingGroup(
            cfg=horizon_cfg, setting_id=f"horizon_{hours}h",
            metadata={"horizon_hours_variant": hours},
            specs=_specs(
                experiment="public_validation_recovery_horizon",
                facility="scale_2", profile="intermediate_posture",
                n_scenarios=100,
                scenario_offset=85_000_000 + index * 10_000),
            portfolios=portfolio_map))
    horizon = _execute_groups(horizon_groups, "validation:horizon")
    horizon_path = raw_dir / "recovery_horizon.csv"
    write_csv(horizon, horizon_path)

    manifest = {
        "design": "fresh paired public-evidence validation",
        "status": "local protocol; not externally preregistered",
        "validation_seeds": list(VALIDATION_SEEDS),
        "config": str(config_path.as_posix()),
        "config_sha256_at_run_start": _file_sha256(config_path),
        "protocol": "study/PUBLIC_EVIDENCE_VALIDATION_PROTOCOL.md",
        "protocol_sha256_at_run_start": _file_sha256(
            resolve_path("study/PUBLIC_EVIDENCE_VALIDATION_PROTOCOL.md")),
        "counts": {
            "primary": len(primary), "cross_setting": len(replication),
            "joint_stress": len(stress),
            "time_step_convergence": len(step_results),
            "recovery_horizon": len(horizon),
            "total": (len(primary) + len(replication) + len(stress)
                      + len(step_results) + len(horizon)),
        },
        "elapsed_seconds": round(time.time() - started, 1),
        "claim_boundary": (
            "All outputs are conditional synthetic-model results; no real-"
            "hospital probability or causal control efficacy is estimated."),
    }
    manifest_path = raw_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return {
        "primary": primary_path, "replication": replication_path,
        "stress": stress_path, "stress_parameters": stress_parameter_path,
        "step": step_path, "horizon": horizon_path,
        "manifest": manifest_path,
    }


def run_corrected_diagnostics(cfg: Config) -> dict[str, Path]:
    """Rerun only diagnostics corrected after the initial validation run.

    The first diagnostic files used separate scenario identifiers across
    variants, and the fixed detection-improvement ladder did not preserve
    clock time at a 5-minute step. The first files are retained with an
    ``initial_design_error`` suffix. This rerun shares scenario identifiers
    and gives the rapid-response portfolios an explicit 90-minute detection
    delay at every discretization. Primary and joint-stress outputs are not
    changed.
    """
    raw_dir = resolve_path(cfg.output.raw_dir)
    ensure_dirs(raw_dir)

    step_groups: list[SettingGroup] = []
    for minutes in (5, 15, 30):
        step_cfg = _clock_time_config(cfg, minutes)
        improved_delay = max(1, int(round(90 / minutes)))
        step_portfolios = {"baseline_flat": get_portfolio("baseline_flat")}
        for name in ("seg_detect_backup", "full_defense"):
            step_portfolios[name] = replace(
                get_portfolio(name), detection_improvement=False,
                detection_delay_override=improved_delay)
        step_groups.append(SettingGroup(
            cfg=step_cfg, setting_id=f"step_{minutes}m",
            metadata={
                "time_step_minutes_variant": minutes,
                "rapid_portfolio_detection_minutes": 90,
                "diagnostic_revision": "shared scenarios; clock-time delay",
            },
            specs=_specs(
                experiment="public_validation_step_convergence_corrected",
                facility="scale_2", profile="intermediate_posture",
                n_scenarios=100, scenario_offset=84_000_000),
            portfolios=step_portfolios))
    step_results = _execute_groups(
        step_groups, "validation:time-step-corrected")
    step_path = raw_dir / "time_step_convergence.csv"
    write_csv(step_results, step_path)

    horizon_groups: list[SettingGroup] = []
    portfolio_map = {name: get_portfolio(name) for name in PORTFOLIOS}
    for hours in (72, 168, 504):
        horizon_cfg = copy.deepcopy(cfg)
        horizon_cfg.simulation.max_steps = int(
            hours * 60 / horizon_cfg.simulation.step_minutes)
        horizon_cfg.validate()
        horizon_groups.append(SettingGroup(
            cfg=horizon_cfg, setting_id=f"horizon_{hours}h",
            metadata={
                "horizon_hours_variant": hours,
                "diagnostic_revision": "shared scenarios",
            },
            specs=_specs(
                experiment="public_validation_recovery_horizon_corrected",
                facility="scale_2", profile="intermediate_posture",
                n_scenarios=100, scenario_offset=85_000_000),
            portfolios=portfolio_map))
    horizon = _execute_groups(horizon_groups, "validation:horizon-corrected")
    horizon_path = raw_dir / "recovery_horizon.csv"
    write_csv(horizon, horizon_path)

    manifest_path = raw_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["post_run_diagnostic_correction"] = {
        "date": "2026-08-03",
        "reason": (
            "Initial time-step and horizon diagnostics used different scenario "
            "banks; the 5-minute rapid-response detection ladder also failed "
            "to preserve a 90-minute delay."),
        "scope": (
            "Only time-step and recovery-horizon diagnostics were rerun. "
            "Primary, cross-setting, and joint-stress outputs are unchanged."),
        "preserved_initial_files": [
            "time_step_convergence_initial_design_error.csv",
            "recovery_horizon_initial_design_error.csv",
        ],
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return {"step": step_path, "horizon": horizon_path,
            "manifest": manifest_path}


def run_fine_step_pilot(cfg: Config, n_scenarios: int = 50) -> Path:
    """Exploratory 1/2/5-minute pilot after coarse-step sensitivity."""
    raw_dir = resolve_path(cfg.output.raw_dir)
    portfolio_names = ("baseline_flat", "seg_detect_backup")
    groups: list[SettingGroup] = []
    for minutes in (1, 2, 5):
        step_cfg = _clock_time_config(cfg, minutes)
        improved_delay = max(1, int(round(90 / minutes)))
        portfolios = {
            "baseline_flat": get_portfolio("baseline_flat"),
            "seg_detect_backup": replace(
                get_portfolio("seg_detect_backup"),
                detection_improvement=False,
                detection_delay_override=improved_delay),
        }
        groups.append(SettingGroup(
            cfg=step_cfg, setting_id=f"fine_step_{minutes}m",
            metadata={
                "time_step_minutes_variant": minutes,
                "rapid_portfolio_detection_minutes": 90,
                "analysis_status": "exploratory numerical pilot",
            },
            specs=_specs(
                experiment="public_validation_fine_step_pilot",
                facility="scale_2", profile="intermediate_posture",
                n_scenarios=n_scenarios, scenario_offset=86_000_000,
                portfolios=portfolio_names),
            portfolios=portfolios))
    results = _execute_groups(groups, "validation:fine-step-pilot")
    path = raw_dir / "fine_step_pilot.csv"
    write_csv(results, path)
    return path
