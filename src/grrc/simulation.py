"""One Monte Carlo trial: generate network -> pick entry -> simulate.

Every trial is fully determined by ``(master_seed, trial_id)`` plus the
trial's configuration fields, all of which are written into its output
row — so any single row of the raw CSV can be re-simulated exactly.
"""

from __future__ import annotations

import numpy as np

from .config import Config
from .defenses import (DefensePortfolio, effective_settings, get_portfolio)
from .enums import BackupStrategy, EntryPoint, SegmentationLevel, Zone
from .models import HospitalNetwork, TrialSpec
from .network_generator import apply_controls_to_base, generate_network
from .propagation import RansomwareSimulation
from .utilities import trial_rng


def choose_entry(net: HospitalNetwork, entry_point: str,
                 rng: np.random.Generator) -> int:
    """Pick a random initial-foothold node in the requested category."""
    candidates = net.entry_candidates[EntryPoint(entry_point)]
    if candidates.size == 0:  # degenerate topologies: fall back
        candidates = net.nodes_in_zone(Zone.WORKSTATION)
    if candidates.size == 0:
        candidates = np.arange(net.n_nodes)
    return int(rng.choice(candidates))


def run_trial(cfg: Config, spec: TrialSpec,
              portfolio: DefensePortfolio | None = None,
              entry_node: int | None = None) -> dict:
    """Run one trial and return a flat result row (dict).

    Args:
        cfg: full study configuration.
        spec: reproducibility record (seed, ids, condition names).
        portfolio: explicit portfolio object (used by the optimizer, whose
            portfolios are generated rather than named in the catalog).
            If None, ``spec.portfolio`` is looked up in the catalog.
        entry_node: force a specific entry node (deterministic tests only).
    """
    if portfolio is None:
        portfolio = get_portfolio(spec.portfolio)
    profile = cfg.profiles[spec.profile]
    eff = effective_settings(
        profile, portfolio,
        patch_override=spec.patch_override,
        detection_override=spec.detection_override,
        rapid_isolation_success=cfg.simulation.rapid_isolation_success,
        detection_improvement_factor=
            cfg.simulation.detection_improvement_factor)

    if spec.paired:
        scenario_id = (spec.scenario_id if spec.scenario_id is not None
                       else spec.trial_id)
        topology_rng = trial_rng(spec.master_seed, scenario_id, stream_id=0)
        base = generate_network(
            cfg, spec.facility, spec.profile, topology_rng,
            segmentation=SegmentationLevel.FLAT,
            patch_coverage=0.0,
            backup_strategy=BackupStrategy.CONNECTED.value,
            identity_controls=False)
        net = apply_controls_to_base(
            cfg, base,
            segmentation=eff.segmentation,
            patch_coverage=eff.patch_coverage,
            backup_strategy=eff.backup_strategy,
            identity_controls=eff.identity_controls)
        entry_rng = trial_rng(spec.master_seed, scenario_id, stream_id=1)
        entry = entry_node if entry_node is not None else choose_entry(
            net, spec.entry_point, entry_rng)
        sim_rng = trial_rng(spec.master_seed, scenario_id, stream_id=2)
        sim = RansomwareSimulation(
            cfg, net, eff, sim_rng,
            random_field_key=(spec.master_seed, scenario_id))
    else:
        rng = trial_rng(spec.master_seed, spec.trial_id)
        net = generate_network(
            cfg, spec.facility, spec.profile, rng,
            segmentation=eff.segmentation,
            patch_coverage=eff.patch_coverage,
            backup_strategy=eff.backup_strategy,
            identity_controls=eff.identity_controls)
        entry = entry_node if entry_node is not None else choose_entry(
            net, spec.entry_point, rng)
        sim = RansomwareSimulation(cfg, net, eff, rng)
    metrics = sim.run(entry)

    return {
        "trial_id": spec.trial_id,
        "scenario_id": spec.scenario_id,
        "paired": int(spec.paired),
        "experiment": spec.experiment,
        "master_seed": spec.master_seed,
        "facility": spec.facility,
        "profile": spec.profile,
        "portfolio": spec.portfolio,
        "entry_point": spec.entry_point,
        "entry_node": entry,
        "n_nodes": net.n_nodes,
        "n_edges": net.n_edges,
        "segmentation": eff.segmentation.value,
        # Configured/target patch coverage (the policy knob) vs. the
        # fraction of nodes actually patched. These differ because legacy
        # nodes receive only half the configured probability, so a "90%"
        # policy yields a lower realized fraction (more so for profiles
        # with more legacy nodes). Both are recorded for transparency.
        "patch_coverage": round(eff.patch_coverage, 4),
        "realized_patch_fraction": round(float(net.patched.mean()), 4),
        "detection_delay": eff.detection_delay,
        "isolation_success": round(eff.isolation_success, 4),
        "backup_strategy": eff.backup_strategy,
        "identity_controls": int(eff.identity_controls),
        "rapid_isolation": int(eff.isolate_same_step),
        **metrics,
    }
