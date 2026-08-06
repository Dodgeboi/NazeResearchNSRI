"""Core data structures: the synthetic network and trial bookkeeping.

The network is stored as flat numpy arrays plus per-node adjacency lists,
which keeps the Monte Carlo loop fast on an ordinary laptop while every
node/edge attribute required by the study design stays inspectable
(see docs/data_dictionary.md).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

from .enums import EntryPoint, Service, Zone


@dataclass
class HospitalNetwork:
    """One synthetic healthcare facility network (directed graph).

    Node attributes (parallel arrays, index = node_id):
        zone            Zone of each node
        node_type       short label ('workstation', 'ehr_core', ...)
        vulnerability   0..1 susceptibility score
        patched         patch status at t=0
        criticality     weight used to prioritize restoration
        privilege       Privilege tier (0 low / 1 standard / 2 admin)
        detect_capability  per-node detection-probability multiplier
        is_legacy       flagged high-vulnerability legacy node
        facility_id     constant tag for the facility instance

    Edge attributes (parallel arrays, index = edge_id):
        edge_src, edge_dst      endpoints (directed src -> dst)
        edge_access             access-permission strength 0..1
        edge_strength           connection strength 0..1
        edge_cross_boundary     True if the edge crosses a segmentation
                                boundary (different zones)
        edge_traversal_mod      combined attack-traversal modifier 0..1
                                (segmentation x backup-strategy effects)
    """

    facility_id: str
    facility_size: str
    n_nodes: int
    zone: np.ndarray
    node_type: list[str]
    vulnerability: np.ndarray
    patched: np.ndarray
    criticality: np.ndarray
    privilege: np.ndarray
    detect_capability: np.ndarray
    is_legacy: np.ndarray

    edge_src: np.ndarray
    edge_dst: np.ndarray
    edge_access: np.ndarray
    edge_strength: np.ndarray
    edge_cross_boundary: np.ndarray
    edge_traversal_mod: np.ndarray

    # Paired-experiment bookkeeping. ``patch_draw`` is the common uniform
    # variate used to assign patch status under every portfolio, making
    # higher coverage nested within lower coverage for the same scenario.
    # ``edge_base_id`` maps retained defended edges back to the common flat
    # base graph so event-level random fields line up across portfolios.
    patch_draw: np.ndarray | None = None
    edge_base_id: np.ndarray | None = None
    base_edge_count: int | None = None

    # node_id -> array of outgoing edge ids (built in __post_init__)
    out_edges: list[np.ndarray] = field(default_factory=list)
    # service -> dict(nodes=..., core=..., requires_identity=...)
    services: dict[Service, dict[str, Any]] = field(default_factory=dict)
    # entry point category -> candidate node ids
    entry_candidates: dict[EntryPoint, np.ndarray] = field(
        default_factory=dict)

    def __post_init__(self) -> None:
        if self.patch_draw is None:
            # Backward-compatible fallback for hand-built validation graphs.
            self.patch_draw = np.where(self.patched, 0.0, 1.0)
        if self.edge_base_id is None:
            self.edge_base_id = np.arange(len(self.edge_src), dtype=np.int64)
        if self.base_edge_count is None:
            self.base_edge_count = int(len(self.edge_src))
        if not self.out_edges:
            buckets: list[list[int]] = [[] for _ in range(self.n_nodes)]
            for eid, src in enumerate(self.edge_src):
                buckets[int(src)].append(eid)
            self.out_edges = [np.asarray(b, dtype=np.int64) for b in buckets]

    @property
    def n_edges(self) -> int:
        return int(len(self.edge_src))

    def nodes_in_zone(self, zone: Zone) -> np.ndarray:
        return np.flatnonzero(self.zone == int(zone))

    def to_networkx(self):
        """Export to networkx.DiGraph (used for Figure 1 and inspection)."""
        import networkx as nx

        g = nx.DiGraph()
        for i in range(self.n_nodes):
            g.add_node(
                i,
                zone=Zone(int(self.zone[i])).name,
                node_type=self.node_type[i],
                vulnerability=float(self.vulnerability[i]),
                patched=bool(self.patched[i]),
                criticality=float(self.criticality[i]),
                privilege=int(self.privilege[i]),
            )
        for e in range(self.n_edges):
            g.add_edge(
                int(self.edge_src[e]), int(self.edge_dst[e]),
                access=float(self.edge_access[e]),
                strength=float(self.edge_strength[e]),
                cross_boundary=bool(self.edge_cross_boundary[e]),
                traversal_mod=float(self.edge_traversal_mod[e]),
            )
        return g


@dataclass(frozen=True)
class TrialSpec:
    """Everything needed to reproduce one Monte Carlo trial."""

    trial_id: int
    experiment: str           # 'main' | 'sweep' | 'optimization'
    facility: str
    profile: str
    portfolio: str
    entry_point: str
    master_seed: int
    # Optional absolute overrides used by the sweep experiment.
    patch_override: float | None = None
    detection_override: int | None = None
    # Confirmatory experiments reuse ``scenario_id`` across portfolios.
    # Legacy/standard runs leave this unset and retain trial-id seeding.
    scenario_id: int | None = None
    paired: bool = False
