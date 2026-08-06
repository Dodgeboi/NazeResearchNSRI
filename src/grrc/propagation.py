"""Abstract compromise-propagation state machine.

The 'attack' is purely an epidemic-style state transition process on a
synthetic graph: HEALTHY/VULNERABLE -> COMPROMISED -> DETECTED ->
ISOLATED -> RESTORING -> RESTORED. No malware behavior, payloads,
exploits, or network traffic are modeled or produced.

Per-edge, per-step success probability (documented in docs/methodology.md):

    p(edge) = base_spread_rate
              x privilege_modifier(source)
              x edge_access x edge_strength x edge_traversal_modifier
              x vulnerability(target) x patch_factor(target)

with every factor in [0, 1]. patch_factor = 1 - patch_effectiveness for
patched targets, 1 for unpatched. If the identity service is compromised,
all probabilities are multiplied by ``identity_breach_multiplier``
(capped at 1) — a simple abstraction of credential abuse.

All probabilities are precomputed once per trial, so each step is a small
set of vectorized numpy operations; a full standard experiment runs on an
ordinary laptop.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .config import Config
from .defenses import EffectiveSettings
from .enums import (CLINICAL_SERVICES, NodeState, Privilege, Service, Zone)
from .models import HospitalNetwork
from .service_dependencies import service_availability
from .utilities import event_uniform

#: Zones whose nodes hold clinical/operational data; used to size the
#: simulated unrecoverable-data metric when backups are lost.
DATA_ZONES: frozenset[int] = frozenset({
    int(Zone.EHR), int(Zone.LAB), int(Zone.PHARMACY),
    int(Zone.IMAGING), int(Zone.BACKUP),
})


@dataclass
class StepRecord:
    """Per-step service availability bookkeeping (internal)."""

    downtime: dict[Service, int] = field(default_factory=dict)
    cur_streak: dict[Service, int] = field(default_factory=dict)
    max_streak: dict[Service, int] = field(default_factory=dict)


class RansomwareSimulation:
    """Run one abstract compromise scenario on a generated network."""

    def __init__(self, cfg: Config, net: HospitalNetwork,
                 eff: EffectiveSettings, rng: np.random.Generator,
                 random_field_key: tuple[int, int] | None = None) -> None:
        self.cfg = cfg
        self.net = net
        self.eff = eff
        self.rng = rng
        self.random_field_key = random_field_key
        sim = cfg.simulation
        n = net.n_nodes

        # --- static per-edge success probabilities -----------------------
        priv_map = {
            int(Privilege.LOW): cfg.network.privilege_modifiers["LOW"],
            int(Privilege.STANDARD):
                cfg.network.privilege_modifiers["STANDARD"],
            int(Privilege.ADMIN): cfg.network.privilege_modifiers["ADMIN"],
        }
        priv_mod = np.array([priv_map[int(p)] for p in net.privilege])
        patch_factor = np.where(net.patched,
                                1.0 - sim.patch_effectiveness, 1.0)
        target_factor = net.vulnerability * patch_factor
        self.edge_p = np.clip(
            sim.base_spread_rate
            * priv_mod[net.edge_src]
            * net.edge_access * net.edge_strength * net.edge_traversal_mod
            * target_factor[net.edge_dst],
            0.0, 1.0)

        # --- mutable node state -------------------------------------------
        self.comp = np.zeros(n, dtype=bool)       # actively compromised
        self.detected = np.zeros(n, dtype=bool)
        self.isolated = np.zeros(n, dtype=bool)
        self.fp_isolated = np.zeros(n, dtype=bool)
        self.restored = np.zeros(n, dtype=bool)
        self.ever_comp = np.zeros(n, dtype=bool)
        self.fp_release = np.full(n, -1, dtype=np.int64)
        self.restoring_until = np.full(n, -1, dtype=np.int64)
        self.time_compromised = np.full(n, -1.0)
        self.time_detected = np.full(n, -1.0)
        self.time_isolated = np.full(n, -1.0)
        self.time_restored = np.full(n, -1.0)

        # detection probability / schedule
        delay = max(1, eff.detection_delay)
        self.detect_prob = np.clip(net.detect_capability / delay, 0.0, 1.0)
        self.fixed_delay = delay
        self.identity_nodes = net.nodes_in_zone(Zone.IDENTITY)
        self.backup_nodes = net.nodes_in_zone(Zone.BACKUP)

        # counters
        self.lateral_movements = 0
        self.peak_compromised = 0
        self.containment_step = -1
        self.restore_carry = 0.0
        self.defensive_isolation_node_steps = 0

    # ------------------------------------------------------------------
    def node_states(self) -> np.ndarray:
        """Derive the NodeState enum value for every node (reporting)."""
        n = self.net.n_nodes
        states = np.full(n, int(NodeState.HEALTHY), dtype=np.int64)
        states[~self.net.patched] = int(NodeState.VULNERABLE)
        states[self.comp] = int(NodeState.COMPROMISED)
        states[self.comp & self.detected] = int(NodeState.DETECTED)
        states[self.isolated] = int(NodeState.ISOLATED)
        states[self.restoring_until >= 0] = int(NodeState.RESTORING)
        states[self.restored] = int(NodeState.RESTORED)
        return states

    def compromise(self, nodes: np.ndarray, t: int) -> None:
        fresh = nodes[~self.comp[nodes] & ~self.isolated[nodes]]
        self.comp[fresh] = True
        self.ever_comp[fresh] = True
        self.time_compromised[fresh] = t

    def functional(self) -> np.ndarray:
        """Nodes able to provide service: not compromised, not isolated."""
        return ~self.comp & ~self.isolated

    # ------------------------------------------------------------------
    def _spread(self, t: int, rng: np.random.Generator) -> None:
        net = self.net
        active_src = self.comp[net.edge_src] & ~self.isolated[net.edge_src]
        susceptible = ~self.comp[net.edge_dst] & ~self.isolated[net.edge_dst]
        candidates = np.flatnonzero(active_src & susceptible)
        if candidates.size == 0:
            return
        mult = 1.0
        if self.identity_nodes.size and bool(
                np.any(self.comp[self.identity_nodes])):
            mult = self.cfg.simulation.identity_breach_multiplier
        p = np.minimum(1.0, self.edge_p[candidates] * mult)
        if self.random_field_key is None:
            draws = rng.random(candidates.size)
        else:
            master_seed, scenario_id = self.random_field_key
            full = event_uniform(
                master_seed, scenario_id, 10, t,
                int(net.base_edge_count or net.n_edges))
            draws = full[np.asarray(net.edge_base_id)[candidates]]
        hits = candidates[draws < p]
        if hits.size:
            self.lateral_movements += int(hits.size)
            self.compromise(np.unique(net.edge_dst[hits]), t)

    def _detect(self, t: int, rng: np.random.Generator) -> np.ndarray:
        undetected = np.flatnonzero(self.comp & ~self.detected
                                    & ~self.isolated)
        if undetected.size == 0:
            return undetected
        if self.cfg.simulation.detection_model == "fixed":
            newly = undetected[
                t - self.time_compromised[undetected] >= self.fixed_delay]
        else:  # geometric
            if self.random_field_key is None:
                draws = rng.random(undetected.size)
            else:
                master_seed, scenario_id = self.random_field_key
                draws = event_uniform(
                    master_seed, scenario_id, 11, t,
                    self.net.n_nodes)[undetected]
            newly = undetected[draws < self.detect_prob[undetected]]
        self.detected[newly] = True
        self.time_detected[newly] = t
        return newly

    def _isolate(self, t: int, newly_detected: np.ndarray,
                 rng: np.random.Generator) -> None:
        candidates = self.detected & ~self.isolated
        if not self.eff.isolate_same_step:
            candidates = candidates.copy()
            candidates[newly_detected] = False  # first attempt next step
        idx = np.flatnonzero(candidates)
        if idx.size == 0:
            return
        if self.random_field_key is None:
            draws = rng.random(idx.size)
        else:
            master_seed, scenario_id = self.random_field_key
            draws = event_uniform(
                master_seed, scenario_id, 12, t, self.net.n_nodes)[idx]
        success = idx[draws < self.eff.isolation_success]
        self.isolated[success] = True
        self.time_isolated[success] = t

    def _false_positives(self, t: int, rng: np.random.Generator) -> None:
        sim = self.cfg.simulation
        # release expired false-positive isolations
        expiring = self.fp_isolated & (self.fp_release <= t)
        self.isolated[expiring] = False
        self.fp_isolated[expiring] = False
        if sim.false_positive_rate <= 0:
            return
        eligible = np.flatnonzero(~self.comp & ~self.isolated)
        if eligible.size == 0:
            return
        if self.random_field_key is None:
            draws = rng.random(eligible.size)
        else:
            master_seed, scenario_id = self.random_field_key
            draws = event_uniform(
                master_seed, scenario_id, 13, t,
                self.net.n_nodes)[eligible]
        hits = eligible[draws < sim.false_positive_rate]
        self.isolated[hits] = True
        self.fp_isolated[hits] = True
        self.fp_release[hits] = t + sim.false_positive_duration
        self.time_isolated[hits] = t

    def _restore(self, t: int, backups_available: bool) -> None:
        sim = self.cfg.simulation
        # complete restorations that finish this step
        done = np.flatnonzero((self.restoring_until >= 0)
                              & (self.restoring_until <= t))
        if done.size:
            self.comp[done] = False
            self.isolated[done] = False
            self.detected[done] = False
            self.restored[done] = True
            self.restoring_until[done] = -1
            self.time_restored[done] = t
        # start new restorations up to capacity
        rate = max(sim.restore_rate_min,
                   sim.restore_rate_fraction * self.net.n_nodes)
        if not backups_available:
            rate *= sim.no_backup_restore_penalty
        self.restore_carry += rate
        k = int(self.restore_carry)
        if k <= 0:
            return
        candidates = np.flatnonzero(self.comp & self.isolated
                                    & (self.restoring_until < 0))
        if candidates.size == 0:
            return
        order = candidates[np.argsort(-self.net.criticality[candidates],
                                      kind="stable")]
        chosen = order[:k]
        self.restore_carry -= len(chosen)
        self.restoring_until[chosen] = t + sim.restore_duration
        self.time_restored[chosen] = -1.0

    # ------------------------------------------------------------------
    def run(self, entry_node: int) -> dict:
        """Simulate from a single initial foothold; return the metric row."""
        cfg = self.cfg
        sim = cfg.simulation
        net = self.net
        rng = self.rng
        weights = cfg.service_weights.as_dict()
        clinical_w = sum(weights[s.value] for s in CLINICAL_SERVICES)

        self.compromise(np.asarray([entry_node]), 0)
        rec = StepRecord(
            downtime={s: 0 for s in Service},
            cur_streak={s: 0 for s in Service},
            max_streak={s: 0 for s in Service},
        )
        weighted_clinical_lost_sum = 0.0
        last_clinical_unavail = -1  # step of most recent clinical outage
        clinical_avail_at_end = True
        backup_compromised = False
        steps_simulated = 0

        for t in range(1, sim.max_steps + 1):
            steps_simulated = t
            self._spread(t, rng)
            newly = self._detect(t, rng)
            self._isolate(t, newly, rng)
            self._false_positives(t, rng)

            if self.backup_nodes.size and bool(
                    np.any(self.comp[self.backup_nodes])):
                backup_compromised = True
            backups_available = not backup_compromised

            contained = not bool(np.any(self.comp & ~self.isolated))
            if contained and self.containment_step < 0:
                self.containment_step = t
            if contained:
                self._restore(t, backups_available)

            self.peak_compromised = max(self.peak_compromised,
                                        int(self.comp.sum()))
            self.defensive_isolation_node_steps += int(
                (self.isolated & ~self.comp).sum())

            avail = service_availability(net, self.functional(),
                                         sim.service_functional_fraction)
            clinical_unavail_w = 0.0
            for svc in avail:
                if avail[svc]:
                    rec.cur_streak[svc] = 0
                else:
                    rec.downtime[svc] += 1
                    rec.cur_streak[svc] += 1
                    rec.max_streak[svc] = max(rec.max_streak[svc],
                                              rec.cur_streak[svc])
                    if svc in CLINICAL_SERVICES:
                        clinical_unavail_w += weights[svc.value]
            weighted_clinical_lost_sum += clinical_unavail_w / clinical_w
            if clinical_unavail_w > 0:
                last_clinical_unavail = t
            clinical_avail_at_end = clinical_unavail_w == 0

            if (sim.early_stop and contained and not bool(self.comp.any())
                    and not bool(self.fp_isolated.any())
                    and all(avail.values())):
                break  # steady state: remaining steps add no downtime

        # ---- final metrics ------------------------------------------------
        functional = self.functional()
        final_avail = service_availability(
            net, functional, sim.service_functional_fraction)
        catastrophic = any(
            rec.max_streak[s] > sim.catastrophic_service_steps
            for s in CLINICAL_SERVICES)
        if last_clinical_unavail < 0:
            recovery_step = 0
        elif clinical_avail_at_end:
            recovery_step = last_clinical_unavail + 1
        else:
            recovery_step = -1  # not recovered within the horizon (censored)

        unrecoverable = 0
        if backup_compromised:
            data_mask = np.isin(net.zone, list(DATA_ZONES))
            unrecoverable = int((self.ever_comp & data_mask).sum())

        step_hours = sim.step_minutes / 60.0
        weighted_hours_lost = sum(
            weights[s.value] * rec.downtime[s] * step_hours for s in Service)

        # Keep the three historical convenience ratios for compatibility,
        # but also emit explicitly named, independently recomputable fields.
        # The old ``pct_services_restored`` name was especially ambiguous:
        # it actually measured the fraction of all services available at the
        # terminal step, including services that were never disrupted.
        ever_compromised_fraction = float(self.ever_comp.mean())
        time_averaged_weighted_clinical_unavailability = float(
            weighted_clinical_lost_sum / sim.max_steps)
        final_availability = {
            s: bool(final_avail.get(s, True)) for s in Service
        }
        final_service_availability_fraction = float(
            sum(final_availability.values()) / len(final_availability))
        disrupted_services = [s for s in Service if rec.downtime[s] > 0]
        disrupted_service_recovery_fraction = float(
            sum(final_availability[s] for s in disrupted_services)
            / len(disrupted_services)
        ) if disrupted_services else 1.0

        return {
            "horizon_steps": sim.max_steps,
            "step_minutes": sim.step_minutes,
            # --- technical metrics ---
            "total_compromised": int(self.ever_comp.sum()),
            "ever_compromised_fraction": ever_compromised_fraction,
            # Deprecated compatibility alias; use
            # ``ever_compromised_fraction`` in new analyses.
            "pct_compromised": ever_compromised_fraction,
            "peak_compromised": self.peak_compromised,
            "zones_reached": int(np.unique(
                net.zone[self.ever_comp]).size) if self.ever_comp.any() else 0,
            "lateral_movements": self.lateral_movements,
            "containment_step": self.containment_step,
            "backup_compromised": int(backup_compromised),
            "identity_compromised": int(bool(
                np.any(self.ever_comp[self.identity_nodes]))),
            # --- healthcare-service metrics ---
            **{f"{s.value}_downtime_steps": rec.downtime[s] for s in Service},
            "services_disrupted_count": sum(
                1 for s in Service if rec.downtime[s] > 0),
            "total_service_downtime_steps": sum(rec.downtime.values()),
            "weighted_service_hours_lost": float(weighted_hours_lost),
            "time_averaged_weighted_clinical_unavailability":
                time_averaged_weighted_clinical_unavailability,
            # Deprecated compatibility alias. This is a time-averaged,
            # weighted service-unavailability fraction, not a direct measure
            # of clinical capacity.
            "pct_clinical_capacity_lost":
                time_averaged_weighted_clinical_unavailability,
            "catastrophic": int(catastrophic),
            "defensive_isolation_node_steps":
                self.defensive_isolation_node_steps,
            # --- recovery metrics ---
            "recovery_step": recovery_step,
            "recovered_within_horizon": int(recovery_step >= 0),
            **{f"{s.value}_available_final":
               int(final_availability[s]) for s in Service},
            "final_service_availability_fraction":
                final_service_availability_fraction,
            "disrupted_service_recovery_fraction":
                disrupted_service_recovery_fraction,
            # Deprecated compatibility alias. Historically this meant final
            # availability across all services, not the fraction of disrupted
            # services that had been restored.
            "pct_services_restored":
                final_service_availability_fraction,
            "unrecoverable_nodes": unrecoverable,
            "backups_available": int(not backup_compromised),
            "steps_simulated": steps_simulated,
        }
