import hashlib
import json
from itertools import combinations
from pathlib import Path

import pytest

from grrc.attack_graph import RANSOMWARE_STAGES
from grrc.coverage_evolution import (
    BASE_HIGH, SPLIT_STAGE_MAP, STAGE_MAP, catastrophic_floor, comparable, coverage_profile,
    floor_threshold, floors, load_extract, minimal_repair, stage_gaps)

ROOT = Path(__file__).resolve().parents[1]
EXTRACTS = ROOT / "data/attack_history/extracts"
SOURCE = ROOT / "data/attack_history/source_manifest.json"
RELEASES = [r["version"] for r in json.loads(SOURCE.read_text())["releases"]]


def _ex(v):
    return load_extract(EXTRACTS / f"enterprise-{v}.json.gz")


COMPARABLE = [v for v in RELEASES if comparable(_ex(v))[0]]


def test_extracts_match_source_manifest_hashes():
    for rec in json.loads(SOURCE.read_text())["releases"]:
        data = (ROOT / rec["extract"]).read_bytes()
        assert hashlib.sha256(data).hexdigest() == rec["extract_sha256"]


def test_closed_form_floor_equals_audited_range_machinery():
    """Oracle: placeholders included, the extract-based floor equals the audited
    grrc.range.adversary.adaptive_floor on the pinned v17.1 bundle."""
    from grrc.attack_graph import build_graph, load_bundle
    from grrc.hospital_attack_model import build_model
    from grrc.range.adversary import adaptive_floor
    from grrc.range.regimes import effectiveness_bounds
    mine = floors(_ex("17.1"), exclude_placeholders=False)
    g = build_graph(load_bundle(ROOT / "data/attack/raw/enterprise-attack-17.1.json.gz"))
    ref = adaptive_floor(build_model(g), BASE_HIGH, effectiveness_bounds(g.mitigations)[:, 0])
    assert mine["control_floor"] == pytest.approx(ref[0], abs=1e-12)
    assert mine["clinical_floor"] == pytest.approx(ref[1], abs=1e-12)


def test_comparability_rules():
    assert not comparable(_ex("4.0"))[0]                         # technique-specific mitigations
    assert comparable(_ex("5.2"))[0]
    plain = {s: frozenset({s}) for s in RANSOMWARE_STAGES}       # no v19 crosswalk
    assert not comparable(_ex("19.2"), plain)[0]                 # defense-evasion was split
    assert comparable(_ex("19.2"), STAGE_MAP)[0]
    assert comparable(_ex("19.2"), SPLIT_STAGE_MAP)[0]


@pytest.mark.parametrize("v", COMPARABLE)
def test_placeholders_never_reduce_the_gap(v):
    excl = {r["stage"]: r["uncovered"] for r in coverage_profile(_ex(v), True)}
    incl = {r["stage"]: r["uncovered"] for r in coverage_profile(_ex(v), False)}
    assert all(excl[s] >= incl[s] for s in excl)


@pytest.mark.parametrize("v", COMPARABLE)
def test_proposition1_gap_stage_factor_is_base(v):
    ex = _ex(v)
    factors = floors(ex)["stage_factors"]
    for stage, gap in stage_gaps(ex).items():
        if gap:
            assert factors[stage] == pytest.approx(BASE_HIGH)
        else:
            assert factors[stage] < BASE_HIGH


def test_proposition2_partial_stage_repair_is_useless():
    ex = _ex("19.2")
    gaps = stage_gaps(ex)
    stage = max(gaps, key=lambda s: len(gaps[s]))
    assert len(gaps[stage]) >= 2
    partial = floors(ex, repaired=frozenset(gaps[stage][:-1]))["stage_factors"][stage]
    full = floors(ex, repaired=frozenset(gaps[stage]))["stage_factors"]
    assert partial == pytest.approx(BASE_HIGH)
    # Whole-stage repair can lower it (unless a shared technique elsewhere keeps it at base).
    assert full[stage] <= BASE_HIGH


def test_floor_threshold_inverts_the_catastrophic_map():
    for eps in (0.2, 0.1, 0.05, 0.01):
        for k in (1, 2, 3, 4):
            f = floor_threshold(eps, k)
            assert catastrophic_floor(f, k) <= eps + 1e-12
            if f < 1.0:
                assert catastrophic_floor(f * 1.001 + 1e-12, k) > eps


def _synthetic():
    """Tiny release: one covered technique per stage plus five uncovered ones, one of
    them shared by two stages (so repair cost is not additive per stage)."""
    techs, edges = [], []
    for i, stage in enumerate(s for s in RANSOMWARE_STAGES if s != "impact"):
        techs.append(dict(id=f"T90{i:02d}", name="", tactics=[stage], is_sub=False))
        edges.append(["M1001", f"T90{i:02d}"])
    for tid in ("T1486", "T1490", "T1489", "T1485"):
        techs.append(dict(id=tid, name="", tactics=["impact"], is_sub=False))
        edges.append(["M1001", tid])
    for tid, tactics in [("T8001", ["persistence", "privilege-escalation"]),
                         ("T8002", ["persistence"]), ("T8003", ["discovery"]),
                         ("T8004", ["collection"]), ("T8005", ["defense-evasion"])]:
        techs.append(dict(id=tid, name="", tactics=tactics, is_sub=False))
    return dict(version="synthetic", techniques=techs,
                mitigations=[dict(id="M1001", name="Real control")], mitigates=edges)


def test_minimal_repair_matches_bruteforce_over_all_technique_subsets():
    ex = _synthetic()
    uncovered = sorted(set().union(*stage_gaps(ex).values()))
    assert len(uncovered) == 5
    for eps in (0.2, 0.1, 0.05, 0.03, 0.01):
        for k in (1, 2, 3, 4):
            thr = floor_threshold(eps, k)
            best = None
            for r in range(len(uncovered) + 1):
                for sub in combinations(uncovered, r):
                    if floors(ex, repaired=frozenset(sub))["clinical_floor"] <= thr + 1e-15:
                        best = r
                        break
                if best is not None:
                    break
            got = minimal_repair(ex, eps, k)
            assert got["feasible"] == (best is not None)
            if best is not None:
                assert got["cost"] == best
                assert got["floor_after"] <= thr + 1e-15


def test_minimal_repair_monotone_in_epsilon():
    ex = _ex("19.2")
    for k in (1, 2, 3, 4):
        costs = []
        for eps in (0.20, 0.10, 0.05):
            r = minimal_repair(ex, eps, k)
            costs.append(r["cost"] if r["feasible"] else float("inf"))
        assert costs == sorted(costs)                             # tighter eps never cheaper


@pytest.mark.parametrize("v", COMPARABLE)
def test_stage_binding_matches_floor_factors(v):
    from grrc.coverage_evolution import stage_binding, technique_residuals
    ex = _ex(v)
    bind, factors = stage_binding(ex), floors(ex)["stage_factors"]
    res = technique_residuals(ex)
    for stage, b in bind.items():
        assert b["factor"] == pytest.approx(factors[stage])
        assert res[b["technique"]] == pytest.approx(b["factor"])   # it really is the argmax


def test_parent_inheritance_only_covers_subtechniques_with_mitigated_parents():
    from grrc.coverage_evolution import (inherit_parent_mitigations, kill_chain_techniques,
                                         mitigations_by_technique)
    ex = _ex("19.2")
    inh = inherit_parent_mitigations(ex)
    before, after = mitigations_by_technique(ex), mitigations_by_technique(inh)
    techs = kill_chain_techniques(ex)
    for tid in techs:
        if tid in before:
            assert after[tid] == before[tid]                      # existing mappings untouched
        elif not techs[tid]["is_sub"]:
            assert tid not in after                               # parents never gain edges
        elif tid.split(".")[0] in before:
            assert after[tid] == before[tid.split(".")[0]]        # inherited from the parent
    assert inherit_parent_mitigations(inh) == inh                 # idempotent
    total = lambda e: next(r for r in coverage_profile(e) if r["stage"] == "all")["uncovered"]
    assert total(inh) < total(ex)


@pytest.mark.parametrize("base,eff_low", [(0.5, 0.10), (0.7, 0.35), (0.9, 0.20)])
def test_minimal_repair_evaluator_matches_floors_at_other_parameters(base, eff_low):
    """The repair's fast evaluator equals floors() at non-default base/effectiveness."""
    ex = _ex("19.2")
    r = minimal_repair(ex, 0.10, 1, base=base, eff_low=eff_low)
    direct = floors(ex, base=base, eff_low=eff_low, repaired=frozenset(r["techniques"]))
    assert r["floor_after"] == pytest.approx(direct["clinical_floor"])
    assert r["floor_before"] == pytest.approx(floors(ex, base=base, eff_low=eff_low)["clinical_floor"])


@pytest.mark.parametrize("v", ["5.2", "13.1", "19.2"])
def test_proposition3_floor_is_base_power_times_coverage_term(v):
    """Every stage factor is b times a coverage term, so F(b) = b**n_stages * C and the
    ratio of floors across releases does not depend on b."""
    ex = _ex(v)
    n = len(floors(ex)["stage_factors"])
    f9, f5 = floors(ex, base=0.9)["clinical_floor"], floors(ex, base=0.5)["clinical_floor"]
    assert f5 / f9 == pytest.approx((0.5 / 0.9) ** n, rel=1e-12)
    g = floors(_ex("5.2"), base=0.5)["clinical_floor"] / floors(_ex("5.2"), base=0.9)["clinical_floor"]
    assert (f5 / floors(_ex("5.2"), base=0.5)["clinical_floor"]) == pytest.approx(
        f9 / floors(_ex("5.2"), base=0.9)["clinical_floor"], rel=1e-12)
    assert g == pytest.approx((0.5 / 0.9) ** n, rel=1e-12)
