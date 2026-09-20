"""Parse the MITRE ATT&CK Enterprise STIX bundle into a kill-chain attack graph.

This module reads the pinned ATT&CK release fetched by scripts/fetch_attack.py and
exposes the real, curated structure the control-adequacy certificate operates on:
the ordered kill-chain tactics, the active techniques in each tactic, the active
mitigations, and the real ``mitigates`` edges (mitigation -> technique). It builds
a technique-by-mitigation coverage matrix. It performs no modelling and no I/O
beyond reading the bundle; the reachability model lives in
:mod:`grrc.control_certificate`.

ATT&CK gives authoritative *structure*, not measured effect sizes: a ``mitigates``
edge asserts that a mitigation is relevant to a technique, not by how much. The
certificate therefore treats effectiveness as an uncertain interval, never a point.
"""
from __future__ import annotations

import gzip
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

# The post-compromise ransomware kill chain: the ordered ATT&CK tactics an
# operation traverses from access to encryption. Reconnaissance and
# resource-development are pre-intrusion and excluded. This ordering is ATT&CK's
# own (the enterprise matrix tactic order); which tactics are *required* is the
# one modelling choice, stated as such and varied in sensitivity analysis.
RANSOMWARE_STAGES = (
    "initial-access", "execution", "persistence", "privilege-escalation",
    "defense-evasion", "credential-access", "discovery", "lateral-movement",
    "collection", "command-and-control", "exfiltration", "impact",
)
# The ransomware objective technique that defines "reached impact".
IMPACT_TECHNIQUE = "T1486"


def _external_id(obj: dict) -> str | None:
    for ref in obj.get("external_references", []):
        if ref.get("source_name") == "mitre-attack":
            return ref.get("external_id")
    return None


def _active(obj: dict) -> bool:
    return not obj.get("revoked") and not obj.get("x_mitre_deprecated")


@dataclass(frozen=True)
class AttackGraph:
    """Real ATT&CK structure for the certificate.

    ``techniques`` and ``mitigations`` are external-id lists in a fixed order;
    ``coverage`` is a boolean [technique, mitigation] matrix from ``mitigates``
    edges; ``stage_members`` maps each ransomware stage to the row indices of the
    active techniques carrying that tactic; ``impact_index`` is T1486's row.
    """
    version: str
    techniques: tuple[str, ...]
    technique_names: tuple[str, ...]
    mitigations: tuple[str, ...]
    mitigation_names: tuple[str, ...]
    coverage: np.ndarray
    usage: np.ndarray
    stage_members: dict[str, np.ndarray]
    impact_index: int

    @property
    def n_techniques(self) -> int:
        return len(self.techniques)

    @property
    def n_mitigations(self) -> int:
        return len(self.mitigations)


def load_bundle(path: str | Path) -> dict:
    """Load the ATT&CK STIX bundle (plain or gzipped) and confirm it is well formed."""
    path = Path(path)
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as handle:
        bundle = json.load(handle)
    if bundle.get("type") != "bundle" or "objects" not in bundle:
        raise ValueError("not a STIX bundle")
    return bundle


def build_graph(bundle: dict, stages: tuple[str, ...] = RANSOMWARE_STAGES) -> AttackGraph:
    """Build the kill-chain attack graph from a parsed ATT&CK bundle."""
    objects = bundle["objects"]
    version = next((c.get("x_mitre_version", "?") for c in objects
                    if c["type"] == "x-mitre-collection"), "?")
    stage_set = set(stages)

    # Active techniques that sit in at least one modelled ransomware stage.
    tech_by_ref: dict[str, int] = {}
    techniques, names, tech_phases = [], [], []
    for obj in objects:
        if obj["type"] != "attack-pattern" or not _active(obj):
            continue
        phases = {p["phase_name"] for p in obj.get("kill_chain_phases", [])}
        if not (phases & stage_set):
            continue
        ext = _external_id(obj)
        if ext is None:
            continue
        tech_by_ref[obj["id"]] = len(techniques)
        techniques.append(ext)
        names.append(obj["name"])
        tech_phases.append(phases & stage_set)

    mit_by_ref: dict[str, int] = {}
    mitigations, mit_names = [], []
    for obj in objects:
        if obj["type"] != "course-of-action" or not _active(obj):
            continue
        ext = _external_id(obj)
        if ext is None:
            continue
        mit_by_ref[obj["id"]] = len(mitigations)
        mitigations.append(ext)
        mit_names.append(obj["name"])

    coverage = np.zeros((len(techniques), len(mitigations)), dtype=bool)
    # Usage = number of "uses" edges (groups, malware, tools, campaigns ->
    # technique): a real prevalence weight, so covering a widely-used technique
    # counts for more than covering an obscure one.
    usage = np.zeros(len(techniques), dtype=float)
    for obj in objects:
        if obj["type"] != "relationship":
            continue
        kind = obj.get("relationship_type")
        if kind == "mitigates":
            m, t = mit_by_ref.get(obj["source_ref"]), tech_by_ref.get(obj["target_ref"])
            if m is not None and t is not None:
                coverage[t, m] = True
        elif kind == "uses":
            t = tech_by_ref.get(obj["target_ref"])
            if t is not None:
                usage[t] += 1.0

    stage_members = {
        stage: np.array([i for i, ph in enumerate(tech_phases) if stage in ph], dtype=int)
        for stage in stages
    }
    for stage, members in stage_members.items():
        if len(members) == 0:
            raise ValueError(f"no active techniques found for stage {stage!r}")
    if IMPACT_TECHNIQUE not in techniques:
        raise ValueError(f"impact technique {IMPACT_TECHNIQUE} not present")
    impact_index = techniques.index(IMPACT_TECHNIQUE)
    return AttackGraph(
        version=str(version),
        techniques=tuple(techniques), technique_names=tuple(names),
        mitigations=tuple(mitigations), mitigation_names=tuple(mit_names),
        coverage=coverage, usage=usage, stage_members=stage_members,
        impact_index=impact_index)
