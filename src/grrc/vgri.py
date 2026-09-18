"""Value-Gradient Reactive Isolation (VGRI) — targeted, cost-aware defense.

VGRI is a refinement of the reactive-segmentation policy in
:mod:`grrc.adaptive`. Reactive segmentation, when it engages, throttles
*every* cross-zone link at once — protective but operationally blunt: it pays
the full availability cost of a fully segmented network. VGRI instead throttles
**only the cross-zone links that guard the most clinical value per unit of
availability cost**, ranked along a "value gradient" over the service-
dependency graph.

Mechanism
---------
1. Once, at network build: for every node compute its *downstream clinical
   value* — the criticality-weighted set of service cores reachable from it
   along directed edges (reverse-BFS from each core). A cross-zone edge that
   leads toward high-value downstream is one whose throttling protects a lot.

2. On detection (same reactive trigger as :mod:`grrc.adaptive`): rank the
   cross-boundary edges by downstream value of their destination and clamp
   only the top ``cut_fraction`` of them. The clamp equals the least-privilege
   modifier, exactly as static/reactive segmentation.

3. The operational cost scales with how much is cut: while engaged, VGRI makes
   ``avail_cost_frac * cut_fraction`` of clinical supporting nodes unavailable,
   versus the full ``avail_cost_frac`` paid by an all-links posture. Cutting a
   third of the links costs a third as much — that is the whole point.

The hypothesis under test is that concentrating a small, cheap cut on the
highest-value links captures most of segmentation's protection at a fraction of
its cost, so VGRI wins across a broader region than the all-or-nothing reactive
policy. Whether it actually does is an empirical question the accompanying
experiment answers honestly.

Prior art (honest): this is NOT a novel technique. Crown-jewel
microsegmentation, targeted network immunization / graph-cut hardening, and
detection-triggered dynamic segmentation are all established (commercial
dynamic-microsegmentation products and academic moving-target-defense work).
VGRI/RPE are in-model implementations used here to *test whether* targeting
the segmentation lever helps — and the experiment's answer is that it does not
beat blunt full-network segmentation in this model. This module exists to
document that negative result, not to claim a new method.
"""

from __future__ import annotations

from collections import deque

import numpy as np

from .adaptive import AdaptiveSimulation, _CLINICAL_ZONES
from .config import Config
from .defenses import EffectiveSettings
from .enums import CLINICAL_SERVICES, SERVICE_ZONE, Service
from .models import HospitalNetwork


def downstream_clinical_value(net: HospitalNetwork) -> np.ndarray:
    """Criticality-weighted clinical value reachable downstream of each node.

    For every clinical service, reverse-BFS from its core node marks all nodes
    that can reach that core along directed edges; each such node accrues the
    core's criticality. Nodes closer to (able to reach) more valuable service
    cores score higher. Computed once per network.
    """
    n = net.n_nodes
    # Reverse adjacency: for edge s->d, predecessor of d is s.
    rev: list[list[int]] = [[] for _ in range(n)]
    for s, d in zip(net.edge_src.tolist(), net.edge_dst.tolist()):
        rev[d].append(s)

    value = np.zeros(n, dtype=float)
    if not net.services:
        return value
    for svc in CLINICAL_SERVICES:
        if svc not in net.services:
            continue
        core = int(net.services[svc]["core"])
        w = float(net.criticality[core])
        # Nodes that can reach `core` (including itself).
        seen = np.zeros(n, dtype=bool)
        seen[core] = True
        q = deque([core])
        while q:
            u = q.popleft()
            for p in rev[u]:
                if not seen[p]:
                    seen[p] = True
                    q.append(p)
        value[seen] += w
    return value


class VGRISimulation(AdaptiveSimulation):
    """Reactive segmentation that cuts only the highest-value cross-zone links.

    Parameters extend :class:`grrc.adaptive.AdaptiveSimulation`:

    cut_fraction:
        Fraction of cross-boundary edges to throttle while engaged, chosen as
        the top-valued by :func:`downstream_clinical_value` of their
        destination. ``1.0`` reproduces blunt reactive segmentation.
    """

    def __init__(self, cfg: Config, net: HospitalNetwork,
                 eff: EffectiveSettings, rng: np.random.Generator, *,
                 seg_clamp: float, avail_cost_frac: float,
                 cut_fraction: float = 0.34, trigger: int = 1,
                 hold: int = 6) -> None:
        # VGRI is always a reactive controller.
        super().__init__(cfg, net, eff, rng, posture="reactive",
                         seg_clamp=seg_clamp, avail_cost_frac=avail_cost_frac,
                         trigger=trigger, hold=hold)
        self.cut_fraction = float(np.clip(cut_fraction, 0.0, 1.0))

        # Rank cross-boundary edges by downstream clinical value of their dst;
        # the cut set is the top `cut_fraction` of them (fixed per trial).
        value = downstream_clinical_value(net)
        cross_ids = np.flatnonzero(net.edge_cross_boundary)
        self._cut_edge = np.zeros(net.n_edges, dtype=bool)
        if cross_ids.size:
            order = cross_ids[np.argsort(-value[net.edge_dst[cross_ids]],
                                         kind="stable")]
            k = int(np.ceil(self.cut_fraction * order.size))
            self._cut_edge[order[:k]] = True

        # The operational cost is proportional to how much connectivity is cut.
        # Re-derive the workflow-blocked set at the reduced (targeted) size,
        # preferring clinical nodes that are destinations of cut edges (their
        # cross-zone workflow is the one actually disrupted).
        self.blocked = np.zeros(net.n_nodes, dtype=bool)
        core_nodes = {int(info["core"]) for info in net.services.values()} \
            if net.services else set()
        cut_dsts = set(net.edge_dst[self._cut_edge].tolist())
        for z in _CLINICAL_ZONES:
            nodes = [int(x) for x in net.nodes_in_zone(z)
                     if int(x) not in core_nodes]
            if not nodes:
                continue
            k = int(np.floor(avail_cost_frac * self.cut_fraction * len(nodes)))
            if k <= 0:
                continue
            # Prefer nodes downstream of an actual cut; fall back to the rest.
            preferred = [x for x in nodes if x in cut_dsts]
            rest = [x for x in nodes if x not in cut_dsts]
            ordered = preferred + rest
            chosen = np.array(ordered[:min(k, len(ordered))], dtype=np.int64)
            if chosen.size:
                self.blocked[chosen] = True

    def _seg_factor(self, candidates: np.ndarray) -> np.ndarray | float:
        """Clamp only the pre-selected high-value cut edges while engaged."""
        if not self.seg_engaged:
            return 1.0
        return np.where(self._cut_edge[candidates], self.seg_clamp, 1.0)


#: Zones enclaved by default: the four clinical service zones plus identity
#: (clinical services require identity, so it must be protected too).
_PROTECTED_ZONES: tuple = tuple(SERVICE_ZONE[s] for s in CLINICAL_SERVICES) \
    + (SERVICE_ZONE[Service.IDENTITY],)


class RPESimulation(AdaptiveSimulation):
    """Reactive Protective Enclaving — cut the *complete* inbound boundary of
    the crown-jewel zones on detection, leaving the rest of the network open.

    VGRI showed that cutting a *fraction* of links fails: a fast spread simply
    percolates around the survivors. RPE instead cuts every cross-zone edge
    entering a small protected set of zones (clinical + identity), forming a
    complete enclave those services cannot be reached through — while the low-
    value majority of the network stays connected. The operational cost is
    proportional to the size of that boundary, not the whole hospital, so RPE
    aims to buy static-segmentation-level protection of what matters at a
    fraction of static's cost, and only during an incident.
    """

    def __init__(self, cfg: Config, net: HospitalNetwork,
                 eff: EffectiveSettings, rng: np.random.Generator, *,
                 seg_clamp: float, avail_cost_frac: float,
                 protected_zones: tuple | None = None, trigger: int = 1,
                 hold: int = 6) -> None:
        super().__init__(cfg, net, eff, rng, posture="reactive",
                         seg_clamp=seg_clamp, avail_cost_frac=avail_cost_frac,
                         trigger=trigger, hold=hold)
        zones = protected_zones if protected_zones is not None \
            else _PROTECTED_ZONES
        prot = {int(z) for z in zones}

        # Complete inbound boundary of the protected zones.
        dst_zone = net.zone[net.edge_dst]
        self._cut_edge = net.edge_cross_boundary & np.isin(dst_zone,
                                                           list(prot))
        n_cross = int(net.edge_cross_boundary.sum())
        cut_share = (int(self._cut_edge.sum()) / n_cross) if n_cross else 0.0

        # Cost proportional to the boundary actually cut (see class docstring).
        self.blocked = np.zeros(net.n_nodes, dtype=bool)
        core_nodes = {int(info["core"]) for info in net.services.values()} \
            if net.services else set()
        for z in _CLINICAL_ZONES:
            nodes = [int(x) for x in net.nodes_in_zone(z)
                     if int(x) not in core_nodes]
            if not nodes:
                continue
            k = int(np.floor(avail_cost_frac * cut_share * len(nodes)))
            if k > 0:
                self.blocked[np.array(nodes[:k], dtype=np.int64)] = True

    def _seg_factor(self, candidates: np.ndarray) -> np.ndarray | float:
        if not self.seg_engaged:
            return 1.0
        return np.where(self._cut_edge[candidates], self.seg_clamp, 1.0)
