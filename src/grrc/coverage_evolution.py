"""MITRE ATT&CK mitigation gaps across releases, the risk floor they impose, and repair.

Operates on the compact per-release extracts written by
``scripts/fetch_attack_history.py`` (active techniques with tactics, active
mitigations, active ``mitigates`` edges). Pure functions, no I/O beyond reading an
extract.

Definitions (see ``study/ATTACK_GAPS_PLAN.md``):

- *Kill-chain technique*: an active technique carrying at least one tactic of the
  post-compromise ransomware kill chain ``grrc.attack_graph.RANSOMWARE_STAGES``.
- *Real mitigation*: an active mitigation other than the placeholders
  ``M1055 Do Not Mitigate`` and ``M1056 Pre-compromise`` (matched by id or name), which
  document that no preventive control applies rather than supplying one.
- *Uncovered technique*: a kill-chain technique with no real mitigation.

Risk floor (adaptive adversary, worst interval corner, every mitigation deployed): a
technique's residual is ``base * prod(1 - eff_m)`` over its real mitigations; a stage
succeeds with the *maximum* residual over its techniques; reachability is the product
over stages. Because reachability is monotone non-increasing in the portfolio, deploying
every mitigation attains the minimum, so this is a floor no portfolio of ATT&CK
mitigations can beat. An uncovered technique keeps residual ``base``, so any stage
containing one has factor exactly ``base`` (Proposition 1).

Minimal repair: give a set ``R`` of uncovered techniques a new mitigation with
worst-corner effectiveness ``e_new``. A stage's factor drops below ``base`` only if
*every* uncovered technique in it is repaired, so an optimal ``R`` is a union of whole
stage gap sets (Proposition 2); exact enumeration over stage subsets therefore solves
the minimum-cost repair.
"""
from __future__ import annotations

import gzip
import json
from itertools import combinations
from pathlib import Path

import numpy as np

from grrc.attack_graph import RANSOMWARE_STAGES, IMPACT_TECHNIQUE
from grrc.enums import CLINICAL_SERVICES
from grrc.hospital_attack_model import IMPACT_TECHNIQUES, SERVICE_DEGRADATION
from grrc.joint_bounds import sharp_k_of_n_upper

PLACEHOLDER_MITIGATIONS = frozenset({"M1055", "M1056"})
PLACEHOLDER_NAMES = frozenset({"do not mitigate", "pre-compromise"})
# Kill-chain stage -> the ATT&CK tactics that populate it. ATT&CK v19 split Defense
# Evasion into Stealth and Defense Impairment; the crosswalk keeps one stage so the
# kill-chain model is constant across releases (the split is reported as a sensitivity).
STAGE_MAP = {s: frozenset({s}) for s in RANSOMWARE_STAGES}
STAGE_MAP["defense-evasion"] = frozenset({"defense-evasion", "stealth", "defense-impairment"})
SPLIT_STAGE_MAP = {}
for _s in RANSOMWARE_STAGES:
    if _s == "defense-evasion":
        SPLIT_STAGE_MAP["stealth"] = frozenset({"stealth"})
        SPLIT_STAGE_MAP["defense-impairment"] = frozenset({"defense-impairment"})
    else:
        SPLIT_STAGE_MAP[_s] = frozenset({_s})
NON_IMPACT_STAGES = tuple(s for s in STAGE_MAP if s != "impact")
BASE_HIGH = 0.9                       # worst-corner base rate (as in the certificate studies)
EFF_LOW = 0.20                        # worst-corner effectiveness, default prior
EFF_OVERRIDES = {"M1032": 0.85}       # the one evidence-tightened control (MFA)
DEG_HIGH = np.array([SERVICE_DEGRADATION[s][1] for s in CLINICAL_SERVICES], float)


def load_extract(path) -> dict:
    with gzip.open(Path(path), "rt", encoding="utf-8") as fh:
        return json.load(fh)


def is_placeholder(mid: str, name: str = "") -> bool:
    return mid in PLACEHOLDER_MITIGATIONS or name.strip().lower() in PLACEHOLDER_NAMES


def _non_impact(stage_map):
    return tuple(s for s in stage_map if s != "impact")


def kill_chain_techniques(ex, stage_map=STAGE_MAP) -> dict:
    """``{technique_id: record}`` for active techniques on the ransomware kill chain."""
    tactics = set().union(*stage_map.values())
    return {t["id"]: t for t in ex["techniques"] if set(t["tactics"]) & tactics}


def mitigations_by_technique(ex, exclude_placeholders=True) -> dict:
    names = {m["id"]: m["name"] for m in ex["mitigations"]}
    by: dict[str, list[str]] = {}
    for mid, tid in ex["mitigates"]:
        if exclude_placeholders and is_placeholder(mid, names.get(mid, "")):
            continue
        by.setdefault(tid, []).append(mid)
    return {t: sorted(ms) for t, ms in by.items()}


def comparable(ex, stage_map=STAGE_MAP) -> tuple[bool, str]:
    """Whether a release supports the study: generalised M-series mitigations, every
    kill-chain stage populated, and the ransomware objective T1486 present."""
    mids = [m["id"] for m in ex["mitigations"]]
    if not mids or sum(m.startswith("M") for m in mids) / len(mids) < 0.9:
        return False, "technique-specific mitigations (before the M-series restructure)"
    techs = kill_chain_techniques(ex, stage_map)
    for stage, tactics in stage_map.items():
        if not any(set(t["tactics"]) & tactics for t in techs.values()):
            return False, f"no techniques for stage '{stage}'"
    if IMPACT_TECHNIQUE not in techs:
        return False, f"{IMPACT_TECHNIQUE} absent"
    return True, "comparable"


def stage_members(ex, stage_map=STAGE_MAP) -> dict:
    """Technique ids per non-impact stage, plus the clinical-impact members."""
    techs = kill_chain_techniques(ex, stage_map)
    out = {s: sorted(t for t, r in techs.items() if set(r["tactics"]) & stage_map[s])
           for s in _non_impact(stage_map)}
    out["impact"] = sorted(t for t in IMPACT_TECHNIQUES
                           if t in techs and "impact" in techs[t]["tactics"])
    return out


def coverage_profile(ex, exclude_placeholders=True, stage_map=STAGE_MAP) -> list[dict]:
    """Per stage (and in total): techniques, uncovered, and the parent-technique series."""
    techs = kill_chain_techniques(ex, stage_map)
    by = mitigations_by_technique(ex, exclude_placeholders)
    rows = []
    for stage, tactics in stage_map.items():
        ids = [t for t, r in techs.items() if set(r["tactics"]) & tactics]
        parents = [t for t in ids if not techs[t]["is_sub"]]
        rows.append(dict(stage=stage, techniques=len(ids),
                         uncovered=sum(t not in by for t in ids),
                         parents=len(parents), parents_uncovered=sum(t not in by for t in parents)))
    parents = [t for t in techs if not techs[t]["is_sub"]]
    rows.append(dict(stage="all", techniques=len(techs), uncovered=sum(t not in by for t in techs),
                     parents=len(parents), parents_uncovered=sum(t not in by for t in parents)))
    return rows


def technique_residuals(ex, base=BASE_HIGH, eff_low=EFF_LOW, overrides=None,
                        exclude_placeholders=True, repaired=frozenset(), e_new=EFF_LOW,
                        stage_map=STAGE_MAP):
    """Worst-corner residual of every kill-chain technique with every mitigation deployed.

    Techniques in ``repaired`` that have no real mitigation receive one new mitigation
    of worst-corner effectiveness ``e_new``.
    """
    overrides = EFF_OVERRIDES if overrides is None else overrides
    by = mitigations_by_technique(ex, exclude_placeholders)
    out = {}
    for tid in kill_chain_techniques(ex, stage_map):
        mits = by.get(tid, [])
        factor = float(np.prod([1.0 - overrides.get(m, eff_low) for m in mits])) if mits else 1.0
        if not mits and tid in repaired:
            factor = 1.0 - e_new
        out[tid] = base * factor
    return out


def floors(ex, base=BASE_HIGH, exclude_placeholders=True, repaired=frozenset(),
           e_new=EFF_LOW, eff_low=EFF_LOW, overrides=None, stage_map=STAGE_MAP):
    """Adaptive reachability floors and per-stage factors for one release."""
    res = technique_residuals(ex, base, eff_low, overrides, exclude_placeholders, repaired,
                              e_new, stage_map)
    members = stage_members(ex, stage_map)
    stages = _non_impact(stage_map)
    factors = {s: max(res[t] for t in members[s]) for s in stages}
    factors["impact"] = max(res[t] for t in members["impact"])
    chain = float(np.prod([factors[s] for s in stages]))
    return dict(control_floor=chain * res[IMPACT_TECHNIQUE],
                clinical_floor=chain * factors["impact"], stage_factors=factors)


def catastrophic_floor(clinical_floor, k, deg_high=DEG_HIGH) -> float:
    """Sharp worst-case P(at least k clinical services down) at the floor."""
    return sharp_k_of_n_upper(np.clip(clinical_floor * np.asarray(deg_high, float), 0, 1), k)


def floor_threshold(eps, k, deg_high=DEG_HIGH) -> float:
    """Largest clinical floor F with catastrophic_floor(F, k) <= eps (monotone bisection)."""
    if catastrophic_floor(1.0, k, deg_high) <= eps:
        return 1.0
    lo, hi = 0.0, 1.0
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if catastrophic_floor(mid, k, deg_high) <= eps:
            lo = mid
        else:
            hi = mid
    return lo


def stage_gaps(ex, exclude_placeholders=True, stage_map=STAGE_MAP) -> dict:
    """Uncovered technique ids per stage (the clinical-impact members for 'impact')."""
    by = mitigations_by_technique(ex, exclude_placeholders)
    return {s: sorted(t for t in ids if t not in by)
            for s, ids in stage_members(ex, stage_map).items()}


def minimal_repair(ex, eps, k, e_new=EFF_LOW, exclude_placeholders=True,
                   base=BASE_HIGH, deg_high=DEG_HIGH, stage_map=STAGE_MAP, eff_low=EFF_LOW):
    """Fewest uncovered techniques to give a new mitigation so certification at (eps, k)
    becomes possible under the adaptive adversary.

    By Proposition 2 an optimal repair is a union of whole stage gap sets, so enumerating
    stage subsets is exact. Returns a dict with ``feasible``, ``cost`` (techniques),
    ``stages`` (fully repaired), ``techniques`` (the repair list), ``floor_before`` and
    ``floor_after`` (clinical), and ``threshold``.
    """
    gaps = stage_gaps(ex, exclude_placeholders, stage_map)
    gap_stages = [s for s in gaps if gaps[s]]
    threshold = floor_threshold(eps, k, deg_high)
    # Precompute once: residuals without repair, stage membership, and the residual a
    # repaired (previously uncovered) technique takes. Each subset evaluation is then a
    # cheap max/product, identical to ``floors(..., repaired=R)["clinical_floor"]``.
    res0 = technique_residuals(ex, base, eff_low, None, exclude_placeholders, frozenset(),
                               e_new, stage_map)
    members = stage_members(ex, stage_map)
    stages = _non_impact(stage_map) + ("impact",)
    fixed = base * (1.0 - e_new)
    uncovered = set().union(*gaps.values()) if gaps else set()

    def evaluate(repaired):
        rep = set(repaired)
        total = 1.0
        for stage in stages:
            total *= max(fixed if (t in rep and t in uncovered) else res0[t]
                         for t in members[stage])
        return total

    before = evaluate(())
    best = None
    for r in range(len(gap_stages) + 1):
        for subset in combinations(gap_stages, r):
            repaired = sorted(set().union(*[gaps[s] for s in subset])) if subset else []
            f = evaluate(repaired)
            if f <= threshold + 1e-15:
                key = (len(repaired), f, subset)
                if best is None or key < best[0]:
                    best = (key, repaired, f)
    if best is None:
        everything = sorted(set().union(*[gaps[s] for s in gap_stages])) if gap_stages else []
        return dict(feasible=False, cost=None, stages=(), techniques=(), threshold=threshold,
                    floor_before=before, floor_after=evaluate(everything))
    (cost, f, _), repaired, _ = best
    fully = tuple(s for s in gap_stages if set(gaps[s]) <= set(repaired))
    return dict(feasible=True, cost=cost, stages=fully, techniques=tuple(repaired),
                threshold=threshold, floor_before=before, floor_after=f)


def stage_binding(ex, base=BASE_HIGH, exclude_placeholders=True, stage_map=STAGE_MAP):
    """Per stage, the floor factor and the technique that sets it (the adaptive
    adversary's best route): the largest residual, ties broken by technique id."""
    res = technique_residuals(ex, base, EFF_LOW, None, exclude_placeholders,
                              frozenset(), EFF_LOW, stage_map)
    out = {}
    for stage, ids in stage_members(ex, stage_map).items():
        top = max(res[t] for t in ids)
        binding = min(t for t in ids if res[t] == top)
        out[stage] = dict(factor=top, technique=binding)
    return out


def inherit_parent_mitigations(ex, exclude_placeholders=True):
    """Sensitivity transform: a sub-technique with no real mitigation of its own inherits
    its parent's real mitigations (``T1234.001`` from ``T1234``). Returns a new extract;
    parents and already-mitigated sub-techniques are unchanged."""
    by = mitigations_by_technique(ex, exclude_placeholders)
    edges = {tuple(e) for e in ex["mitigates"]}
    for t in ex["techniques"]:
        if t["is_sub"] and t["id"] not in by:
            for m in by.get(t["id"].split(".")[0], []):
                edges.add((m, t["id"]))
    return dict(ex, mitigates=sorted([list(e) for e in edges]))
