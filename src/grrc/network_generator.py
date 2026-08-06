"""Synthetic healthcare-network generator.

Builds a random directed graph for one facility according to a
:class:`~grrc.config.Config`, a cyber-capacity profile, and an *effective
defense setting* (segmentation level, patch coverage, backup strategy).

Every topology is synthetic. Node counts, zone proportions and access
rules are simulation settings documented in docs/assumptions.md — they
are NOT measurements of any real hospital.

Topology randomness: each Monte Carlo trial regenerates the network from
its own RNG stream, so node counts, edge placement, vulnerability scores
and patch assignments all jitter between trials. Conclusions therefore
never depend on one fixed network (design requirement).
"""

from __future__ import annotations

import numpy as np

from .config import Config, NetworkSpec
from .enums import (EntryPoint, Privilege, SegmentationLevel, Service,
                    SERVICE_ZONE, Zone)
from .models import HospitalNetwork

# ---------------------------------------------------------------------------
# Zone-to-zone access rules
# ---------------------------------------------------------------------------
# REQUIRED_PATHS: cross-zone communication that a healthcare facility needs
# to function; these exist under EVERY architecture (otherwise services
# could not operate). Under least-privilege these are the ONLY paths.
REQUIRED_PATHS: set[tuple[Zone, Zone]] = {
    (Zone.WORKSTATION, Zone.EHR), (Zone.WORKSTATION, Zone.LAB),
    (Zone.WORKSTATION, Zone.PHARMACY), (Zone.WORKSTATION, Zone.IMAGING),
    (Zone.WORKSTATION, Zone.ADMIN), (Zone.WORKSTATION, Zone.IDENTITY),
    (Zone.WORKSTATION, Zone.INTERNET_FACING),
    (Zone.EHR, Zone.LAB), (Zone.EHR, Zone.PHARMACY),
    (Zone.EHR, Zone.IDENTITY), (Zone.EHR, Zone.BACKUP),
    (Zone.LAB, Zone.EHR), (Zone.LAB, Zone.IDENTITY),
    (Zone.LAB, Zone.BACKUP),
    (Zone.PHARMACY, Zone.EHR), (Zone.PHARMACY, Zone.IDENTITY),
    (Zone.PHARMACY, Zone.BACKUP),
    (Zone.IMAGING, Zone.EHR), (Zone.IMAGING, Zone.IDENTITY),
    (Zone.IMAGING, Zone.BACKUP),
    (Zone.MEDICAL_DEVICE, Zone.EHR), (Zone.MEDICAL_DEVICE, Zone.IMAGING),
    (Zone.ADMIN, Zone.EHR), (Zone.ADMIN, Zone.IDENTITY),
    (Zone.ADMIN, Zone.BACKUP), (Zone.ADMIN, Zone.WORKSTATION),
    (Zone.IDENTITY, Zone.ADMIN),
    (Zone.INTERNET_FACING, Zone.EHR), (Zone.INTERNET_FACING, Zone.IDENTITY),
}

# EXTRA paths that additionally exist under BASIC segmentation
# (convenience/legacy links a partially segmented network still allows).
BASIC_EXTRA_PATHS: set[tuple[Zone, Zone]] = {
    (Zone.WORKSTATION, Zone.MEDICAL_DEVICE),
    (Zone.INTERNET_FACING, Zone.WORKSTATION),
    (Zone.ADMIN, Zone.LAB), (Zone.ADMIN, Zone.PHARMACY),
    (Zone.ADMIN, Zone.IMAGING), (Zone.ADMIN, Zone.MEDICAL_DEVICE),
    (Zone.ADMIN, Zone.INTERNET_FACING), (Zone.ADMIN, Zone.IDENTITY),
    (Zone.EHR, Zone.IMAGING), (Zone.EHR, Zone.ADMIN),
    (Zone.LAB, Zone.ADMIN), (Zone.MEDICAL_DEVICE, Zone.WORKSTATION),
}

# Vendor-support paths originating at vendor gateway nodes
# (third-party remote access; present in all architectures, weaker under
# stricter segmentation like every other cross-boundary edge).
VENDOR_PATHS: tuple[Zone, ...] = (Zone.MEDICAL_DEVICE, Zone.IMAGING,
                                  Zone.ADMIN)

#: Zones treated as extra-sensitive under least privilege.
SENSITIVE_ZONES: frozenset[Zone] = frozenset({Zone.IDENTITY, Zone.BACKUP})

#: Baseline criticality weight by zone (restoration priority).
ZONE_CRITICALITY: dict[Zone, float] = {
    Zone.WORKSTATION: 0.3, Zone.EHR: 1.5, Zone.LAB: 1.2,
    Zone.PHARMACY: 1.3, Zone.IMAGING: 1.1, Zone.MEDICAL_DEVICE: 0.8,
    Zone.ADMIN: 0.7, Zone.IDENTITY: 1.4, Zone.BACKUP: 1.2,
    Zone.INTERNET_FACING: 0.6,
}


def allowed_zone_pairs(segmentation: SegmentationLevel) -> set[tuple[Zone, Zone]]:
    """Cross-zone pairs permitted under a segmentation architecture."""
    if segmentation == SegmentationLevel.FLAT:
        return {(a, b) for a in Zone for b in Zone if a != b}
    if segmentation == SegmentationLevel.BASIC:
        return REQUIRED_PATHS | BASIC_EXTRA_PATHS
    return set(REQUIRED_PATHS)


def _zone_counts(n_nodes: int, spec: NetworkSpec,
                 rng: np.random.Generator) -> dict[Zone, int]:
    """Split n_nodes across zones with jitter, min per zone enforced."""
    zones = list(Zone)
    props = np.array([spec.zone_proportions[z.name] for z in zones])
    jitter = rng.uniform(0.9, 1.1, size=len(zones))
    props = props * jitter
    props /= props.sum()
    counts = np.maximum(spec.min_nodes_per_zone,
                        np.round(props * n_nodes).astype(int))
    # Adjust the largest zone so counts sum exactly to n_nodes.
    diff = n_nodes - int(counts.sum())
    counts[int(np.argmax(counts))] = max(
        spec.min_nodes_per_zone, counts[int(np.argmax(counts))] + diff)
    return {z: int(c) for z, c in zip(zones, counts)}


def generate_network(
    cfg: Config,
    facility: str,
    profile: str,
    rng: np.random.Generator,
    *,
    segmentation: SegmentationLevel,
    patch_coverage: float,
    backup_strategy: str,
    identity_controls: bool = False,
) -> HospitalNetwork:
    """Generate one synthetic facility network.

    Parameters mirror the *effective* defense configuration produced by
    :func:`grrc.defenses.effective_settings` — the generator itself has no
    knowledge of budgets or portfolio names.
    """
    spec = cfg.network
    fac = cfg.facilities[facility]
    prof = cfg.profiles[profile]
    n_nodes = int(rng.integers(fac.min_nodes, fac.max_nodes + 1))
    counts = _zone_counts(n_nodes, spec, rng)
    n_nodes = sum(counts.values())  # after min-per-zone adjustment

    # ---- node attributes -------------------------------------------------
    zone = np.empty(n_nodes, dtype=np.int64)
    node_type: list[str] = [""] * n_nodes
    idx = 0
    zone_nodes: dict[Zone, np.ndarray] = {}
    for z, c in counts.items():
        zone[idx:idx + c] = int(z)
        for k in range(c):
            node_type[idx + k] = z.name.lower()
        zone_nodes[z] = np.arange(idx, idx + c)
        idx += c

    is_legacy = rng.random(n_nodes) < prof.legacy_fraction
    vulnerability = np.where(
        is_legacy,
        rng.uniform(*spec.legacy_vuln_range, size=n_nodes),
        rng.uniform(*spec.vuln_range, size=n_nodes),
    )
    # Legacy nodes are also less likely to be patchable/patched.
    patch_prob = np.where(is_legacy, patch_coverage * 0.5, patch_coverage)
    patch_draw = rng.random(n_nodes)
    patched = patch_draw < patch_prob

    privilege = np.full(n_nodes, int(Privilege.STANDARD), dtype=np.int64)
    privilege[zone_nodes[Zone.ADMIN]] = int(Privilege.ADMIN)
    privilege[zone_nodes[Zone.IDENTITY]] = int(Privilege.ADMIN)
    privilege[zone_nodes[Zone.MEDICAL_DEVICE]] = int(Privilege.LOW)
    other = np.flatnonzero((zone != int(Zone.ADMIN))
                           & (zone != int(Zone.IDENTITY)))
    extra_admin = other[rng.random(other.size)
                        < spec.admin_fraction_other_zones]
    privilege[extra_admin] = int(Privilege.ADMIN)

    detect_capability = np.ones(n_nodes)
    detect_capability[zone_nodes[Zone.MEDICAL_DEVICE]] = \
        spec.device_detect_capability
    detect_capability[is_legacy] = np.minimum(
        detect_capability[is_legacy], spec.legacy_detect_capability)

    criticality = np.array([ZONE_CRITICALITY[Zone(int(z))] for z in zone])

    # Designate one 'core' node per service zone (e.g. the primary EHR
    # database). Core nodes are required for the service and get higher
    # criticality.
    core_nodes: dict[Service, int] = {}
    for svc, svc_zone in SERVICE_ZONE.items():
        core = int(zone_nodes[svc_zone][0])
        core_nodes[svc] = core
        criticality[core] = 2.0
        node_type[core] = f"{svc_zone.name.lower()}_core"

    # Vendor gateways live in the internet-facing zone.
    inet = zone_nodes[Zone.INTERNET_FACING]
    n_vendor = min(spec.vendor_gateway_count, max(0, inet.size - 1))
    vendor_nodes = inet[-n_vendor:] if n_vendor else inet[:0]
    for v in vendor_nodes:
        node_type[int(v)] = "vendor_gateway"

    # ---- edges ------------------------------------------------------------
    seg_mod = spec.segmentation_modifiers[segmentation.value]
    backup_mod = spec.backup_traversal[backup_strategy]
    pairs = allowed_zone_pairs(segmentation)

    src_l: list[int] = []
    dst_l: list[int] = []
    access_l: list[float] = []
    strength_l: list[float] = []
    cross_l: list[bool] = []
    trav_l: list[float] = []
    # A directed edge (s, d) is stored at most once. Propagation makes one
    # independent infection attempt per stored edge, so a duplicated edge
    # would silently multiply the transmission probability between two
    # nodes. Deduplicating here keeps every pair a single channel and
    # removes a facility-size-dependent bias (smaller zones collide more).
    edge_seen: set[tuple[int, int]] = set()

    def add_edge(s: int, d: int, access: float, traversal: float,
                 cross: bool) -> None:
        if s == d or (s, d) in edge_seen:
            return
        edge_seen.add((s, d))
        src_l.append(s)
        dst_l.append(d)
        access_l.append(access)
        strength_l.append(float(rng.uniform(0.7, 1.0)))
        cross_l.append(cross)
        trav_l.append(traversal)

    # Intra-zone edges: sparse random digraph per zone, plus a ring so each
    # zone stays internally connected.
    for z, nodes in zone_nodes.items():
        m = nodes.size
        if m < 2:
            continue
        for k in range(m):
            add_edge(int(nodes[k]), int(nodes[(k + 1) % m]), 1.0, 1.0, False)
        n_extra = int(spec.intra_zone_degree * m) - m
        for _ in range(max(0, n_extra)):
            s, d = rng.choice(nodes, size=2, replace=False)
            add_edge(int(s), int(d), 1.0, 1.0, False)

    # Cross-zone edges: for each permitted pair, a number of random links
    # proportional to zone sizes and the profile's complexity factor.
    # (De-duplication is handled centrally by add_edge.)
    for (za, zb) in pairs:
        a_nodes, b_nodes = zone_nodes[za], zone_nodes[zb]
        n_links = max(1, int(round(
            spec.cross_zone_out_degree * prof.complexity_factor
            * min(a_nodes.size, b_nodes.size) / 2)))
        traversal = seg_mod
        if (segmentation == SegmentationLevel.LEAST_PRIVILEGE
                and zb in SENSITIVE_ZONES):
            traversal *= spec.sensitive_zone_modifier
        if zb == Zone.BACKUP:
            traversal *= backup_mod
        if identity_controls and zb == Zone.IDENTITY:
            traversal *= 0.5
        if traversal <= 0.0:
            continue  # e.g. isolated backups: no network path in
        for _ in range(n_links):
            s = int(rng.choice(a_nodes))
            d = int(rng.choice(b_nodes))
            add_edge(s, d, float(rng.uniform(0.6, 1.0)), traversal, True)

    # Vendor gateway support paths.
    for v in vendor_nodes:
        for zb in VENDOR_PATHS:
            traversal = seg_mod
            d = int(rng.choice(zone_nodes[zb]))
            add_edge(int(v), d, float(rng.uniform(0.6, 1.0)), traversal, True)

    net = HospitalNetwork(
        facility_id=f"{facility}:{profile}",
        facility_size=facility,
        n_nodes=n_nodes,
        zone=zone,
        node_type=node_type,
        vulnerability=vulnerability,
        patched=patched,
        criticality=criticality,
        privilege=privilege,
        detect_capability=detect_capability,
        is_legacy=is_legacy,
        edge_src=np.asarray(src_l, dtype=np.int64),
        edge_dst=np.asarray(dst_l, dtype=np.int64),
        edge_access=np.asarray(access_l),
        edge_strength=np.asarray(strength_l),
        edge_cross_boundary=np.asarray(cross_l, dtype=bool),
        edge_traversal_mod=np.asarray(trav_l),
        patch_draw=patch_draw,
        edge_base_id=np.arange(len(src_l), dtype=np.int64),
        base_edge_count=len(src_l),
    )

    # ---- service dependency map (see service_dependencies.py) -------------
    from .service_dependencies import build_service_map
    net.services = build_service_map(net, core_nodes)

    # ---- entry-point candidates -------------------------------------------
    non_vendor_inet = np.setdiff1d(inet, vendor_nodes)
    net.entry_candidates = {
        EntryPoint.WORKSTATION: zone_nodes[Zone.WORKSTATION],
        EntryPoint.INTERNET_FACING:
            non_vendor_inet if non_vendor_inet.size else inet,
        EntryPoint.PRIVILEGED_SYSTEM:
            np.flatnonzero(privilege == int(Privilege.ADMIN)),
        EntryPoint.MEDICAL_DEVICE: zone_nodes[Zone.MEDICAL_DEVICE],
        EntryPoint.VENDOR_CONNECTION:
            vendor_nodes if vendor_nodes.size else inet,
    }
    return net


def apply_controls_to_base(
    cfg: Config,
    base: HospitalNetwork,
    *,
    segmentation: SegmentationLevel,
    patch_coverage: float,
    backup_strategy: str,
    identity_controls: bool = False,
) -> HospitalNetwork:
    """Apply one defense posture to a common flat/connected base graph.

    This function is used only by the confirmatory paired design. It keeps
    node attributes and the potential edge set common across portfolios,
    then deterministically filters or weakens edges and reapplies patch
    coverage using the base scenario's stored uniform patch draws.
    """
    spec = cfg.network
    allowed = allowed_zone_pairs(segmentation)
    src_zone = base.zone[base.edge_src]
    dst_zone = base.zone[base.edge_dst]
    cross = base.edge_cross_boundary

    keep = ~cross.copy()
    cross_ids = np.flatnonzero(cross)
    if cross_ids.size:
        permitted = np.zeros(cross_ids.size, dtype=bool)
        for i, eid in enumerate(cross_ids):
            za = Zone(int(src_zone[eid]))
            zb = Zone(int(dst_zone[eid]))
            vendor_path = (
                base.node_type[int(base.edge_src[eid])] == "vendor_gateway"
                and zb in VENDOR_PATHS
            )
            permitted[i] = (za, zb) in allowed or vendor_path
        keep[cross_ids] = permitted

    traversal = np.ones(base.n_edges, dtype=float)
    traversal[cross] = spec.segmentation_modifiers[segmentation.value]
    if segmentation == SegmentationLevel.LEAST_PRIVILEGE:
        sensitive = cross & np.isin(
            dst_zone, [int(z) for z in SENSITIVE_ZONES])
        traversal[sensitive] *= spec.sensitive_zone_modifier
    into_backup = cross & (dst_zone == int(Zone.BACKUP))
    traversal[into_backup] *= spec.backup_traversal[backup_strategy]
    if identity_controls:
        into_identity = cross & (dst_zone == int(Zone.IDENTITY))
        traversal[into_identity] *= 0.5
    keep &= traversal > 0.0
    edge_ids = np.flatnonzero(keep)

    patch_prob = np.where(
        base.is_legacy, patch_coverage * 0.5, patch_coverage)
    patched = np.asarray(base.patch_draw) < patch_prob

    net = HospitalNetwork(
        facility_id=base.facility_id,
        facility_size=base.facility_size,
        n_nodes=base.n_nodes,
        zone=base.zone.copy(),
        node_type=list(base.node_type),
        vulnerability=base.vulnerability.copy(),
        patched=patched,
        criticality=base.criticality.copy(),
        privilege=base.privilege.copy(),
        detect_capability=base.detect_capability.copy(),
        is_legacy=base.is_legacy.copy(),
        edge_src=base.edge_src[edge_ids].copy(),
        edge_dst=base.edge_dst[edge_ids].copy(),
        edge_access=base.edge_access[edge_ids].copy(),
        edge_strength=base.edge_strength[edge_ids].copy(),
        edge_cross_boundary=base.edge_cross_boundary[edge_ids].copy(),
        edge_traversal_mod=traversal[edge_ids],
        patch_draw=np.asarray(base.patch_draw).copy(),
        edge_base_id=np.asarray(base.edge_base_id)[edge_ids].copy(),
        base_edge_count=int(base.base_edge_count or base.n_edges),
    )
    net.services = {
        svc: {
            "nodes": info["nodes"].copy(),
            "core": info["core"],
            "requires_identity": info["requires_identity"],
        }
        for svc, info in base.services.items()
    }
    net.entry_candidates = {
        entry: nodes.copy() for entry, nodes in base.entry_candidates.items()
    }
    return net
