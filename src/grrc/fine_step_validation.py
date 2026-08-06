"""Post-diagnostic five-minute replication with fresh paired scenarios."""

from __future__ import annotations

import copy
import hashlib
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import qmc

from .advanced_experiments import SettingGroup, _execute_groups
from .config import Config
from .defenses import get_portfolio
from .experiments import run_specs
from .models import TrialSpec
from .public_validation import STRESS_RANGES
from .utilities import ensure_dirs, resolve_path, write_csv


FINE_SEEDS = (5701001, 5701002, 5701003, 5701004, 5701005)
PORTFOLIOS = ("baseline_flat", "seg_detect_backup")


def _hazard_15m_to_5m(probability: float) -> float:
    return 1.0 - (1.0 - probability) ** (1.0 / 3.0)


def _specs(*, experiment: str, n_scenarios: int,
           scenario_offset: int) -> list[TrialSpec]:
    entries = ("workstation", "internet_facing", "privileged_system",
               "medical_device", "vendor_connection")
    rows: list[TrialSpec] = []
    trial_id = scenario_offset * 10
    for rep in range(n_scenarios):
        scenario_id = scenario_offset + rep
        for portfolio in PORTFOLIOS:
            rows.append(TrialSpec(
                trial_id=trial_id, experiment=experiment,
                facility="scale_2", profile="intermediate_posture",
                portfolio=portfolio, entry_point=entries[rep % len(entries)],
                master_seed=FINE_SEEDS[rep % len(FINE_SEEDS)],
                scenario_id=scenario_id, paired=True))
            trial_id += 1
    return rows


def _apply_clock_time_stress(cfg: Config,
                             values_15m: dict[str, float]) -> None:
    sim = cfg.simulation
    net = cfg.network
    profile = cfg.profiles["intermediate_posture"]
    sim.base_spread_rate = _hazard_15m_to_5m(
        values_15m["base_spread_rate"])
    sim.patch_effectiveness = values_15m["patch_effectiveness"]
    net.intra_zone_degree = values_15m["intra_zone_degree"]
    net.cross_zone_out_degree = values_15m["cross_zone_out_degree"]
    sim.identity_breach_multiplier = values_15m[
        "identity_breach_multiplier"]
    sim.restore_rate_fraction = values_15m["restore_rate_fraction"] / 3.0
    sim.no_backup_restore_penalty = values_15m[
        "no_backup_restore_penalty"]
    sim.service_functional_fraction = values_15m[
        "service_functional_fraction"]
    sim.false_positive_rate = _hazard_15m_to_5m(
        values_15m["false_positive_rate"])
    profile.legacy_fraction = values_15m["legacy_fraction"]
    profile.isolation_success = _hazard_15m_to_5m(
        values_15m["isolation_success"])
    profile.detection_delay_steps = int(round(
        values_15m["detection_delay_steps"] * 3.0))
    net.backup_traversal["isolated"] = values_15m[
        "isolated_backup_traversal"]
    cfg.validate()


def run_fine_step_replication(cfg: Config, config_path: Path) -> dict[str, Path]:
    started = time.time()
    raw_dir = resolve_path(cfg.output.raw_dir)
    ensure_dirs(raw_dir)

    primary_specs = _specs(
        experiment="fine_step_primary", n_scenarios=500,
        scenario_offset=91_000_000)
    primary = run_specs(cfg, primary_specs, desc="fine-step:primary")
    primary_path = raw_dir / "primary_paired.csv"
    write_csv(primary, primary_path)

    names = list(STRESS_RANGES)
    unit = qmc.LatinHypercube(d=len(names), seed=cfg.seed).random(128)
    lows = np.array([STRESS_RANGES[name][0] for name in names])
    highs = np.array([STRESS_RANGES[name][1] for name in names])
    matrix = qmc.scale(unit, lows, highs)
    portfolio_map = {name: get_portfolio(name) for name in PORTFOLIOS}
    groups: list[SettingGroup] = []
    parameters: list[dict[str, object]] = []
    for index, row in enumerate(matrix):
        values = {name: float(value) for name, value in zip(names, row)}
        setting_cfg = copy.deepcopy(cfg)
        setting_cfg.experiment.workers = 1
        _apply_clock_time_stress(setting_cfg, values)
        setting_id = f"fine_lhs_{index:03d}"
        parameters.append({"setting_id": setting_id, **values})
        groups.append(SettingGroup(
            cfg=setting_cfg, setting_id=setting_id,
            metadata={**values, "source_step_minutes": 15,
                      "simulation_step_minutes": 5},
            specs=_specs(
                experiment="fine_step_joint_stress", n_scenarios=10,
                scenario_offset=92_000_000 + index * 100),
            portfolios=portfolio_map))
    stress = _execute_groups(groups, "fine-step:joint-stress")
    stress_path = raw_dir / "joint_stress.csv"
    write_csv(stress, stress_path)
    parameter_path = raw_dir / "joint_stress_parameters.csv"
    write_csv(pd.DataFrame(parameters), parameter_path)

    protocol = resolve_path("study/FINE_STEP_REPLICATION_PROTOCOL.md")
    manifest = {
        "design": "post-diagnostic five-minute paired replication",
        "status": "local protocol; not externally preregistered",
        "prior_information_disclosed": True,
        "seeds": list(FINE_SEEDS),
        "config": str(config_path.as_posix()),
        "config_sha256_at_run_start": hashlib.sha256(
            config_path.read_bytes()).hexdigest(),
        "protocol": "study/FINE_STEP_REPLICATION_PROTOCOL.md",
        "protocol_sha256_at_run_start": hashlib.sha256(
            protocol.read_bytes()).hexdigest(),
        "counts": {"primary": len(primary), "joint_stress": len(stress),
                   "total": len(primary) + len(stress)},
        "elapsed_seconds": round(time.time() - started, 1),
    }
    manifest_path = raw_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return {"primary": primary_path, "stress": stress_path,
            "parameters": parameter_path, "manifest": manifest_path}
