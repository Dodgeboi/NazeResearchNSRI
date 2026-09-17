"""Reactive ("just-in-time") network segmentation — an adaptive defense.

This module studies a defense *policy* that the main study does not model:
segmentation that is **engaged reactively**, only once an intrusion has been
detected, rather than run permanently.

Motivation
----------
In the baseline engine, segmentation lowers cross-boundary spread but carries
*no* operational cost — a node's ability to provide service does not depend on
cross-zone connectivity. Real segmentation is not free: locking cross-zone
paths breaks the cross-zone clinical workflows that keep services usable
(a workstation that can no longer reach the EHR/lab/pharmacy it depends on is,
for service purposes, down). Once that ongoing cost is represented, a genuine
question appears that "always segment" cannot answer:

    Is it better to run permanently locked down (always protected, always
    paying the operational cost) or to run open and slam the barriers down
    only while an attack is actually underway (paying the cost only during
    incidents, but risking that the attacker has already spread by the time
    detection fires)?

Three postures are compared on *identical* networks and random streams so the
only difference is the segmentation policy:

* ``open``     — never segment (cross-boundary spread at full rate, no cost).
* ``static``   — always segment (cross-boundary spread clamped every step, and
                 the operational availability cost paid every step).
* ``reactive`` — start open; when the number of *detected* active compromises
                 reaches ``trigger`` engage segmentation (clamp + cost); once
                 the observable incident has been quiet for ``hold`` steps,
                 disengage. The controller uses only what a defender can see
                 (detections), never ground-truth compromise.

The operational cost is modeled by marking a fraction ``avail_cost_frac`` of
non-core supporting nodes in the clinical service zones as unavailable *while
segmentation is engaged* — i.e. their cross-zone workflow is broken. This
flows through the engine's normal service-availability accounting, so it lands
directly in the study's primary metric, ``weighted_service_hours_lost``.

Nothing here changes baseline dynamics: the extension seams in
:class:`grrc.propagation.RansomwareSimulation` are pure no-ops for that class.
"""

from __future__ import annotations

import numpy as np

from .config import Config
from .defenses import EffectiveSettings
from .enums import Zone
from .models import HospitalNetwork
from .propagation import RansomwareSimulation

#: Clinical service zones whose cross-zone workflows are disrupted when
#: emergency segmentation is engaged (the operational cost lands here).
_CLINICAL_ZONES: tuple[Zone, ...] = (
    Zone.EHR, Zone.LAB, Zone.PHARMACY, Zone.IMAGING,
)

_POSTURES = ("open", "static", "reactive")


class AdaptiveSimulation(RansomwareSimulation):
    """A compromise simulation with a reactive-segmentation controller.

    Parameters
    ----------
    posture:
        ``"open"``, ``"static"`` or ``"reactive"`` (see module docstring).
    seg_clamp:
        Multiplier applied to cross-boundary spread probability while
        segmentation is engaged (e.g. 0.25 = the least-privilege modifier).
    avail_cost_frac:
        Fraction of non-core clinical supporting nodes made unavailable while
        segmentation is engaged (the operational cost ``c``).
    trigger:
        Number of detected active compromises that engages reactive
        segmentation.
    hold:
        Consecutive steps with zero detected active compromise required before
        reactive segmentation disengages.
    """

    def __init__(self, cfg: Config, net: HospitalNetwork,
                 eff: EffectiveSettings, rng: np.random.Generator, *,
                 posture: str, seg_clamp: float, avail_cost_frac: float,
                 trigger: int = 1, hold: int = 6) -> None:
        if posture not in _POSTURES:
            raise ValueError(f"posture must be one of {_POSTURES}")
        super().__init__(cfg, net, eff, rng)
        self.posture = posture
        self.seg_clamp = float(seg_clamp)
        self.trigger = int(trigger)
        self.hold = int(hold)

        # Segmentation engaged from t=0 only for the static posture.
        self.seg_engaged = (posture == "static")
        self._clear_streak = 0
        self.engaged_steps = 0
        self.first_engage_step = -1

        # Precompute the cross-boundary mask over ALL edges so _seg_factor can
        # index it cheaply with the per-step candidate edge ids.
        self._cross = net.edge_cross_boundary

        # Choose the workflow-blocked nodes: a deterministic fraction of the
        # NON-core supporting nodes in each clinical zone. Core nodes are left
        # untouched (blocking a core would zero a whole service and overstate
        # the cost). Selection uses the trial RNG, so it is reproducible.
        self.blocked = np.zeros(net.n_nodes, dtype=bool)
        core_nodes = {int(info["core"]) for info in net.services.values()} \
            if net.services else set()
        for z in _CLINICAL_ZONES:
            nodes = net.nodes_in_zone(z)
            nodes = np.array([n for n in nodes if int(n) not in core_nodes],
                             dtype=np.int64)
            if nodes.size == 0:
                continue
            k = int(np.floor(avail_cost_frac * nodes.size))
            if k <= 0:
                continue
            chosen = rng.choice(nodes, size=min(k, nodes.size), replace=False)
            self.blocked[chosen] = True

    # -- overridden extension seams -------------------------------------
    def _on_step_start(self, t: int) -> None:
        """Update reactive segmentation engagement from observable signals."""
        if self.seg_engaged:
            self.engaged_steps += 1
        if self.posture != "reactive":
            return
        # Observable = compromises the defender has DETECTED and that are not
        # yet restored. Ground-truth compromise is deliberately not used.
        detected_active = int(np.count_nonzero(
            self.detected & self.comp & ~self.restored))
        if not self.seg_engaged:
            if detected_active >= self.trigger:
                self.seg_engaged = True
                if self.first_engage_step < 0:
                    self.first_engage_step = t
                self._clear_streak = 0
        else:
            if detected_active == 0:
                self._clear_streak += 1
                if self._clear_streak >= self.hold:
                    self.seg_engaged = False
            else:
                self._clear_streak = 0

    def _seg_factor(self, candidates: np.ndarray) -> np.ndarray | float:
        """Clamp cross-boundary candidate edges while segmentation is engaged."""
        if not self.seg_engaged:
            return 1.0
        return np.where(self._cross[candidates], self.seg_clamp, 1.0)

    def _service_functional(self) -> np.ndarray:
        """Baseline functionality minus workflow-blocked nodes while engaged."""
        func = self.functional()
        if self.seg_engaged and self.blocked.any():
            func = func & ~self.blocked
        return func
