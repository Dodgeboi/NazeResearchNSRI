"""Dependency-closed controlled islanding (DCCI).

Specification: study/ISLANDING_SPECIFICATION.md. Read section 0 there before
reading this module: it states which parts of this method have precedents and
which combination is the proposed contribution.

The idea in one paragraph. Power-grid operators contain a cascading failure by
*controlled islanding*: opening pre-planned breakers so the grid splits into
islands that each keep generation and load in balance. The analogue proposed
here splits a hospital network, at the moment compromise is first detected,
into pre-planned islands that each keep their clinical service *dependency
chain* closed — a slice of every clinical zone, a core replica for every
service, and an identity replica. Hospital segmentation cuts between
functions (EHR from lab from identity), so cutting it severs service chains.
Islanding cuts across functions, so each island that stays clean can keep
serving on its own.

The claim the method makes testable is a single sentence: **disconnection is
protective only if what is disconnected is dependency-closed**. Severing part
of a hospital from its central identity and EHR core is itself an outage.
That is what health systems do today when they disconnect a site, and the
``dependency_closed=False`` variant here models exactly that, so the two can be
compared on matched scenarios.

Semantics, all of which the specification states as declared assumptions:

* Island membership is vertical and deterministic: within every zone, the
  node at position ``j`` belongs to island ``j % k``. The global core of each
  service sits at position 0, so it is always in island 0.
* In **connected** operation nothing changes. Replicas are standby only, so
  the connected-mode availability rule is the unmodified
  :func:`grrc.service_dependencies.service_availability`. This keeps the
  method's effect attributable to islanding, not to ordinary high
  availability, which already has a long literature.
* In **islanded** operation a node serves its service only if its own
  island has a functional core for that service and, where the service needs
  authentication, a functional identity replica. Hospital-level availability
  is then the serving fraction against the same threshold as before. With a
  single island this reduces exactly to the connected rule.
* Replicas share one credential store. Compromising identity anywhere still
  boosts credential-pathway spread everywhere. That is the conservative
  choice: replicas of one directory do not isolate a stolen credential.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .enums import SegmentationLevel, Service, Zone
from .models import HospitalNetwork
from .network_generator import VENDOR_PATHS, allowed_zone_pairs

#: The proposed method: islands cut across zones, each carrying a slice of
#: every service chain.
SERVICE_CHAIN = "service_chain"
#: The comparator it must beat — the closest prior art. On detection, tighten
#: to least-privilege segmentation: cut every cross-zone edge except the
#: architecture's required paths. Services keep working because their
#: dependencies stay reachable, and for exactly that reason the required
#: paths stay open to the attacker too.
ZONE = "zone"
#: A much stronger comparator: a micro-segmentation lockdown on detection.
#: Cut every intra-zone edge as well, so the only surviving paths are the
#: architecture's required cross-zone ones. This model charges nothing for
#: cutting intra-zone edges — in a real hospital an EHR application server and
#: its database are in one zone and must talk — so this is an upper bound on
#: what segmentation-based lockdown could do here, not a realistic one.
ZONE_MICRO = "zone_micro"
PARTITIONS = (SERVICE_CHAIN, ZONE, ZONE_MICRO)

#: Criticality given to an island core replica, matching the global core's
#: value in network_generator, so a replica is restored as early as the
#: primary it stands in for.
REPLICA_CRITICALITY = 2.0


@dataclass(frozen=True)
class IslandPlan:
    """A pre-planned partition of one network into islands.

    ``island[n]`` is node ``n``'s island. ``cores[svc][i]`` is the node that
    serves as ``svc``'s core inside island ``i``, or -1 when island ``i`` has
    none — which is always the case, outside island 0, for a plan that is not
    dependency-closed.
    """

    k: int
    dependency_closed: bool
    island: np.ndarray
    cores: dict[Service, np.ndarray] = field(default_factory=dict)
    primaries: dict[Service, int] = field(default_factory=dict)
    #: SERVICE_CHAIN (the method) or ZONE (the comparator).
    partition: str = SERVICE_CHAIN
    #: Per-edge mask: True where an edge stays traversable once tripped.
    traversable: np.ndarray | None = None
    #: Per-service supporting nodes, their islands, and island sizes.
    #: Precomputed because availability is evaluated every step of every
    #: severed trial; they are pure functions of the network and the plan.
    service_nodes: dict[Service, np.ndarray] = field(default_factory=dict)
    service_node_island: dict[Service, np.ndarray] = field(
        default_factory=dict)
    service_island_size: dict[Service, np.ndarray] = field(
        default_factory=dict)

    @property
    def severs_dependencies(self) -> bool:
        """Whether tripping disconnects services from their central cores.

        Service-chain islands are fully severed, so each island must supply
        its own dependencies. Zone tightening keeps the required paths, so
        dependencies stay reachable and the connected availability rule
        still holds.
        """
        return self.partition == SERVICE_CHAIN

    @property
    def replicas(self) -> np.ndarray:
        """Nodes promoted to core in an island other than the primary's."""
        promoted = {int(node)
                    for svc, per_island in self.cores.items()
                    for node in per_island
                    if node >= 0 and node != self.primaries[svc]}
        return np.array(sorted(promoted), dtype=np.int64)


def minimum_island_count(threshold: float) -> int:
    """Smallest island count at which losing one whole island is survivable.

    A service keeps ``(k - 1) / k`` of its supporting capacity after one of
    ``k`` equal islands is lost, and it survives only if that is at least
    the service threshold ``theta``. So ``k >= 1 / (1 - theta)``. At the
    study's declared ``theta = 0.60`` this is 3: two islands cannot keep any
    service up once either island is lost, however clean the other one is.

    This is arithmetic, not a finding. It is stated because it is the first
    thing an islanding design gets wrong, and because the experiment checks
    that the simulator agrees with it.
    """
    if not 0.0 < threshold < 1.0:
        raise ValueError("threshold must be in (0, 1)")
    k = int(np.ceil(1.0 / (1.0 - threshold) - 1e-12))
    return max(k, 1)


def plan_islands(net: HospitalNetwork, k: int,
                 dependency_closed: bool,
                 partition: str = SERVICE_CHAIN,
                 micro_within: bool = False) -> IslandPlan:
    """Build the deterministic island plan for ``net``.

    Deterministic in the network alone, so every candidate replaying one
    paired scenario — and the paired design shares one base graph across
    candidates — gets the same islands and the same replicas.
    """
    if k < 1:
        raise ValueError("island count must be >= 1")
    if partition not in PARTITIONS:
        raise ValueError(f"partition must be one of {PARTITIONS}")
    if partition in (ZONE, ZONE_MICRO):
        return _zone_tightening_plan(net, cut_intra_zone=partition == ZONE_MICRO)
    island = np.zeros(net.n_nodes, dtype=np.int64)
    for z in np.unique(net.zone):
        members = np.flatnonzero(net.zone == z)  # ascending node index
        island[members] = np.arange(members.size) % k

    cores: dict[Service, np.ndarray] = {}
    primaries: dict[Service, int] = {}
    for svc, info in (net.services or {}).items():
        per_island = np.full(k, -1, dtype=np.int64)
        primary = int(info["core"])
        primaries[svc] = primary
        per_island[island[primary]] = primary
        if dependency_closed:
            nodes = np.asarray(info["nodes"])
            for i in range(k):
                if per_island[i] >= 0:
                    continue
                in_island = nodes[island[nodes] == i]
                if in_island.size:
                    per_island[i] = int(in_island[0])
        cores[svc] = per_island
    service_nodes = {svc: np.asarray(info["nodes"])
                     for svc, info in (net.services or {}).items()}
    service_node_island = {svc: island[nodes]
                           for svc, nodes in service_nodes.items()}
    traversable = island[net.edge_src] == island[net.edge_dst]
    if micro_within:
        # Islands with the micro-segmentation lockdown applied inside each
        # one. Tests whether islanding adds anything on top of the strongest
        # segmentation comparator, rather than only whether it beats it.
        traversable &= _least_privilege_mask(net, cut_intra_zone=True)
    return IslandPlan(
        k=k, dependency_closed=dependency_closed, island=island, cores=cores,
        primaries=primaries, partition=SERVICE_CHAIN,
        traversable=traversable,
        service_nodes=service_nodes,
        service_node_island=service_node_island,
        service_island_size={svc: np.bincount(isl, minlength=k)
                             for svc, isl in service_node_island.items()})


def _least_privilege_mask(net: HospitalNetwork,
                          cut_intra_zone: bool) -> np.ndarray:
    """Edges a detection-triggered least-privilege lockdown leaves open.

    Cross-zone edges survive only where least-privilege segmentation permits
    them; vendor-gateway support paths keep the exemption the model gives them
    under every tier. Intra-zone edges survive unless ``cut_intra_zone``.
    """
    allowed = allowed_zone_pairs(SegmentationLevel.LEAST_PRIVILEGE)
    src_zone, dst_zone = net.zone[net.edge_src], net.zone[net.edge_dst]
    same_zone = src_zone == dst_zone
    traversable = same_zone & (not cut_intra_zone)
    for eid in np.flatnonzero(~same_zone):
        za, zb = Zone(int(src_zone[eid])), Zone(int(dst_zone[eid]))
        vendor_path = (net.node_type[int(net.edge_src[eid])]
                       == "vendor_gateway" and zb in VENDOR_PATHS)
        traversable[eid] = (za, zb) in allowed or vendor_path
    return traversable


def _zone_tightening_plan(net: HospitalNetwork,
                          cut_intra_zone: bool = False) -> IslandPlan:
    """The segmentation comparators: tighten to least privilege on detection.

    Cores and replicas are irrelevant because the required paths stay open,
    so the connected availability rule applies; none are designated beyond
    the primaries.
    """
    traversable = _least_privilege_mask(net, cut_intra_zone)
    primaries = {svc: int(info["core"])
                 for svc, info in (net.services or {}).items()}
    return IslandPlan(
        k=1, dependency_closed=True,
        island=np.zeros(net.n_nodes, dtype=np.int64),
        cores={svc: np.array([core]) for svc, core in primaries.items()},
        primaries=primaries,
        partition=ZONE_MICRO if cut_intra_zone else ZONE,
        traversable=traversable)


def island_restore_priority(net: HospitalNetwork,
                            plan: IslandPlan) -> np.ndarray:
    """Restoration priority with island core replicas raised to core level."""
    priority = np.array(net.criticality, dtype=float, copy=True)
    replicas = plan.replicas
    if replicas.size:
        priority[replicas] = np.maximum(priority[replicas],
                                        REPLICA_CRITICALITY)
    return priority


def islanded_service_availability(net: HospitalNetwork,
                                  functional: np.ndarray,
                                  threshold: float,
                                  plan: IslandPlan) -> dict[Service, bool]:
    """Service availability while the islands are severed.

    A supporting node *serves* only when it is functional, its island's core
    for the service is functional, and — for an authentication-dependent
    service — its island's identity replica is available. The hospital-level
    service is available when the serving fraction meets ``threshold``.

    With ``plan.k == 1`` this is exactly
    :func:`grrc.service_dependencies.service_availability`: a single island's
    core is the global core and its identity is the global identity, so the
    serving fraction is the functional fraction when both are up and zero
    otherwise.
    """
    avail: dict[Service, bool] = {}
    if not net.services:
        return avail
    k = plan.k

    def core_ok(svc: Service) -> np.ndarray:
        per_island = plan.cores[svc]
        ok = np.zeros(k, dtype=bool)
        present = per_island >= 0
        ok[present] = functional[per_island[present]]
        return ok

    def base_ok_per_island(svc: Service) -> np.ndarray:
        """Per-island analogue of service_dependencies.base_ok.

        The functional fraction is count / size in float64, which is the
        same arithmetic as the boolean mean the connected rule uses, so the
        single-island reduction stays exact.
        """
        sizes = plan.service_island_size[svc]
        up = np.bincount(plan.service_node_island[svc],
                         weights=functional[plan.service_nodes[svc]],
                         minlength=k)
        with np.errstate(divide="ignore", invalid="ignore"):
            frac = np.where(sizes > 0, up / np.maximum(sizes, 1), 0.0)
        return core_ok(svc) & (sizes > 0) & (frac >= threshold)

    identity_ok = (base_ok_per_island(Service.IDENTITY)
                   if Service.IDENTITY in net.services
                   else np.ones(k, dtype=bool))
    for svc, info in net.services.items():
        nodes = plan.service_nodes[svc]
        if not nodes.size:
            avail[svc] = False
            continue
        island_ok = core_ok(svc)
        if info["requires_identity"]:
            island_ok = island_ok & identity_ok
        serving = functional[nodes] & island_ok[plan.service_node_island[svc]]
        avail[svc] = float(serving.mean()) >= threshold
    return avail


def contained_island_mask(plan: IslandPlan, active: np.ndarray) -> np.ndarray:
    """Per-node mask: True where the node's island has no active compromise.

    ``active`` is compromised-and-not-isolated. A severed island with no
    active compromise cannot be reinfected while the breakers stay open, so
    restoring inside it is as safe as restoring after global containment.
    """
    dirty = np.zeros(plan.k, dtype=bool)
    if active.any():
        dirty[np.unique(plan.island[active])] = True
    return ~dirty[plan.island]
