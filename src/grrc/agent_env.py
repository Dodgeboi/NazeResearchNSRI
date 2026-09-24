"""A cyber range for autonomous defenders on the hospital simulator.

An autonomous defender observes what a security operations centre would see
and chooses a *network response mode* every ``interval`` simulation steps. The
simulator's own node-level response — detection, then isolation of detected
nodes — keeps running underneath, exactly as in every other experiment in this
repository. The agent adds the network-level decision that autonomous
responders and playbooks actually take: whether to cut the network, and how.

Response modes (``MODES``):

``connected``
    No network-level response. The reference every other mode is judged
    against.
``disconnect``
    Sever the estate into three segments with no replicas. This is the
    "disconnect the affected systems" playbook step. It is the crude islanding
    of grrc.islanding: identical cuts to ``islands``, but segments without the
    primary cores and identity lose every authentication-dependent service.
``zone_lockdown``
    Tighten to least-privilege segmentation: keep only the architecture's
    required cross-zone paths. Services keep working because their
    dependencies stay reachable.
``islands``
    Dependency-closed islanding (grrc.islanding). Offered only on estates
    with ``replicas=True``, since the replicas are pre-provisioned
    architecture, not something an agent can create mid-incident.
``micro_lockdown``
    Also cut every intra-zone edge. **Not offered to learning agents.** The
    model cannot represent the dependency this breaks (an application server
    and its database share a zone), so the action would be rewarded for free.
    It is available to scripted comparators only, labeled as an upper bound.

Paired design. An episode replays one scenario of the study's paired design:
the same topology, entry node, event random fields and per-scenario parameter
draws as :func:`grrc.simulation.run_trial`. Two agents facing the same
scenario therefore face the same attacker and the same luck, so their
difference is attributable to their decisions. With the ``connected`` policy
the episode reproduces ``run_trial`` exactly, which
``tests/test_agent_env.py`` asserts.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field

import numpy as np

from .config import Config
from .defenses import DefensePortfolio, effective_settings
from .enums import CLINICAL_SERVICES, BackupStrategy, SegmentationLevel, Service
from .islanding import (ZONE, ZONE_MICRO, island_restore_priority,
                        islanded_service_availability, plan_islands)
from .models import TrialSpec
from .network_generator import apply_controls_to_base, generate_network
from .propagation import RansomwareSimulation
from .service_dependencies import service_availability
from .simulation import choose_entry
from .uncertainty import apply_parameters, sample_parameters
from .utilities import event_uniform, trial_rng

CONNECTED = "connected"
DISCONNECT = "disconnect"
ZONE_LOCKDOWN = "zone_lockdown"
ISLANDS = "islands"
MICRO_LOCKDOWN = "micro_lockdown"
MODES = (CONNECTED, DISCONNECT, ZONE_LOCKDOWN, ISLANDS, MICRO_LOCKDOWN)

#: Action sets offered to learning agents, by estate architecture.
LEARNING_ACTIONS = {
    "today": (CONNECTED, DISCONNECT, ZONE_LOCKDOWN),
    "replicas": (CONNECTED, DISCONNECT, ZONE_LOCKDOWN, ISLANDS),
}

REWARDS = ("containment", "soft", "clinical")


@dataclass
class Observation:
    """What a security operations centre can see. Never the true compromise."""

    t: int
    detections_total: int
    active_alerts: int
    isolated: int
    clinical_down: bool
    identity_down: bool
    mode: str
    steps_since_detection: int


@dataclass
class EpisodeLog:
    decisions: list[str] = field(default_factory=list)
    steps_in_mode: dict[str, int] = field(default_factory=dict)
    self_inflicted_steps: int = 0
    self_inflicted_service_steps: int = 0
    shield_interventions: int = 0


def build_paired_simulation(cfg: Config, spec: TrialSpec,
                            portfolio: DefensePortfolio):
    """The paired path of run_trial, returning the simulator before it runs.

    Mirrors :func:`grrc.simulation.run_trial` for ``spec.paired``. A test pins
    the two together, so a change to one that is not made to the other fails.
    """
    if not spec.paired:
        raise ValueError("the defender environment requires paired specs")
    drawn = sample_parameters(cfg, spec.master_seed, spec.scenario_id)
    cfg = apply_parameters(cfg, drawn)
    profile = cfg.profiles[spec.profile]
    eff = effective_settings(
        profile, portfolio,
        rapid_isolation_success=cfg.simulation.rapid_isolation_success,
        detection_improvement_factor=(
            cfg.simulation.detection_improvement_factor))
    lapse_draw = float(event_uniform(
        spec.master_seed, spec.scenario_id, 15, 0, 1)[0])
    if (eff.backup_strategy == BackupStrategy.ISOLATED.value
            and lapse_draw < cfg.network.backup_isolation_lapse):
        eff = dataclasses.replace(
            eff, backup_strategy=BackupStrategy.PERIODIC.value)
    base = generate_network(
        cfg, spec.facility, spec.profile,
        trial_rng(spec.master_seed, spec.scenario_id, stream_id=0),
        segmentation=SegmentationLevel.FLAT, patch_coverage=0.0,
        backup_strategy=BackupStrategy.CONNECTED.value,
        identity_controls=False)
    net = apply_controls_to_base(
        cfg, base, segmentation=eff.segmentation,
        patch_coverage=eff.patch_coverage,
        backup_strategy=eff.backup_strategy,
        identity_controls=eff.identity_controls)
    entry = choose_entry(net, spec.entry_point,
                         trial_rng(spec.master_seed, spec.scenario_id,
                                   stream_id=1))
    sim = RansomwareSimulation(
        cfg, net, eff,
        trial_rng(spec.master_seed, spec.scenario_id, stream_id=2),
        random_field_key=(spec.master_seed, spec.scenario_id))
    return cfg, sim, entry


class DefenderEnv:
    """One paired scenario, driven by an autonomous defender.

    ``reset()`` returns the first observation; ``step(mode)`` applies the
    requested mode for ``interval`` simulation steps and returns
    ``(observation, reward, done)``. ``shield`` is an optional runtime monitor
    (grrc.shield) that may override the requested mode at any step.
    """

    def __init__(self, cfg: Config, spec: TrialSpec, *,
                 interval: int = 12, replicas: bool = False,
                 reward: str = "containment", soft_lambda: float = 1.0,
                 shield=None, island_count: int = 3,
                 portfolio: DefensePortfolio | None = None) -> None:
        if reward not in REWARDS:
            raise ValueError(f"reward must be one of {REWARDS}")
        self.cfg_in = cfg
        self.spec = spec
        self.interval = interval
        self.replicas = replicas
        self.reward_kind = reward
        self.soft_lambda = soft_lambda
        self.shield = shield
        self.island_count = island_count
        self.portfolio = portfolio or DefensePortfolio("profile_baseline")

    # ------------------------------------------------------------------ setup
    def reset(self) -> Observation:
        self.cfg, self.sim, entry = build_paired_simulation(
            self.cfg_in, self.spec, self.portfolio)
        sim, net = self.sim, self.sim.net
        self.plans = {
            CONNECTED: None,
            DISCONNECT: plan_islands(net, self.island_count, False),
            ZONE_LOCKDOWN: plan_islands(net, 1, True, partition=ZONE),
            MICRO_LOCKDOWN: plan_islands(net, 1, True, partition=ZONE_MICRO),
        }
        if self.replicas:
            self.plans[ISLANDS] = plan_islands(net, self.island_count, True)
            sim.restore_priority = island_restore_priority(
                net, self.plans[ISLANDS])
        sim.auto_breakers = False
        sim.step_monitor = self._monitor
        self.mode = CONNECTED
        self.log = EpisodeLog(steps_in_mode={m: 0 for m in self.plans})
        self.t = 0
        self.done = False
        self.first_detection = -1
        self._compromised_so_far = 0
        sim.start(entry)
        self._compromised_so_far = int(sim.ever_comp.sum())
        return self._observe()

    def available_modes(self) -> tuple[str, ...]:
        return tuple(self.plans)

    # --------------------------------------------------------------- dynamics
    def set_mode(self, mode: str) -> None:
        if mode not in self.plans:
            raise ValueError(f"mode {mode!r} is not available on this estate")
        self.mode = mode
        plan = self.plans[mode]
        self.sim.island_plan = plan
        self.sim.islanded = plan is not None

    def availability_under(self, mode: str) -> dict:
        """Service availability if ``mode`` were active, on the current state."""
        sim = self.sim
        threshold = self.cfg.simulation.service_functional_fraction
        plan = self.plans[mode]
        functional = sim.functional()
        if plan is not None and plan.severs_dependencies:
            return islanded_service_availability(sim.net, functional,
                                                 threshold, plan)
        return service_availability(sim.net, functional, threshold)

    def self_inflicted(self, mode: str | None = None) -> list[Service]:
        """Clinical services the mode makes unavailable by itself.

        Available with no network response and unavailable under ``mode``,
        with node states held fixed. Only modes that sever dependencies can
        do this; the lockdowns keep the required paths, so they cannot.
        """
        mode = mode or self.mode
        plan = self.plans[mode]
        if plan is None or not plan.severs_dependencies:
            return []
        reference = self.availability_under(CONNECTED)
        proposed = self.availability_under(mode)
        return [s for s in CLINICAL_SERVICES
                if reference[s] and not proposed[s]]

    def _monitor(self, t: int) -> None:
        """Per-step hook, called before availability is recorded."""
        induced = self.self_inflicted()
        if induced and self.shield is not None:
            self.log.shield_interventions += 1
            self.set_mode(self.shield.fallback)
            induced = self.self_inflicted()
        if induced:
            self.log.self_inflicted_steps += 1
            self.log.self_inflicted_service_steps += len(induced)
        self.log.steps_in_mode[self.mode] += 1

    def step(self, mode: str) -> tuple[Observation, float, bool]:
        if self.done:
            raise RuntimeError("episode is over; call reset()")
        if self.shield is not None:
            mode = self.shield.admit(self, mode)
        self.set_mode(mode)
        self.log.decisions.append(mode)
        sim = self.sim
        max_steps = self.cfg.simulation.max_steps
        clinical_before = sim._weighted_clinical_lost_sum
        stop = False
        for _ in range(self.interval):
            if self.t >= max_steps:
                break
            self.t += 1
            if sim.advance(self.t):
                stop = True
                break
        if self.first_detection < 0 and (sim.time_detected >= 0).any():
            self.first_detection = int(
                sim.time_detected[sim.time_detected >= 0].min())
        compromised = int(sim.ever_comp.sum())
        new_compromised = compromised - self._compromised_so_far
        self._compromised_so_far = compromised
        step_hours = self.cfg.simulation.step_minutes / 60.0
        clinical_hours = (sim._weighted_clinical_lost_sum
                          - clinical_before) * step_hours
        reward = self._reward(new_compromised, clinical_hours)
        self.done = stop or self.t >= max_steps
        return self._observe(), reward, self.done

    def _reward(self, new_compromised: int, clinical_hours: float) -> float:
        """The training signal. Only ``clinical`` is the outcome that matters.

        ``containment`` rewards stopping spread — the signal autonomous
        cyber-defence benchmarks are built around. ``soft`` subtracts a
        clinical penalty, CAGE-4 style. ``clinical`` is the true objective,
        available here only because the simulator knows it.
        """
        if self.reward_kind == "containment":
            return -float(new_compromised)
        if self.reward_kind == "clinical":
            return -clinical_hours
        return -float(new_compromised) - self.soft_lambda * clinical_hours

    def _observe(self) -> Observation:
        sim = self.sim
        avail = sim.last_avail or {}
        detected_ever = sim.time_detected >= 0
        return Observation(
            t=self.t,
            detections_total=int(detected_ever.sum()),
            active_alerts=int((sim.detected & ~sim.isolated).sum()),
            isolated=int(sim.isolated.sum()),
            clinical_down=any(not avail.get(s, True)
                              for s in CLINICAL_SERVICES),
            identity_down=not avail.get(Service.IDENTITY, True),
            mode=self.mode,
            steps_since_detection=(self.t - self.first_detection
                                   if self.first_detection >= 0 else -1))

    def finish(self) -> dict:
        """Close the episode and return the simulator's metric row, extended."""
        sim = self.sim
        while not self.done:
            self.step(self.mode)
        row = sim.finish()
        row.update({
            "agent_decisions": len(self.log.decisions),
            "self_inflicted_steps": self.log.self_inflicted_steps,
            "self_inflicted_service_steps":
                self.log.self_inflicted_service_steps,
            "shield_interventions": self.log.shield_interventions,
            **{f"steps_{m}": n for m, n in self.log.steps_in_mode.items()},
        })
        return row
