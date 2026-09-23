#!/usr/bin/env python3
"""ATT&CK mitigation gaps across releases, the risk floor, and minimal repair.

Reads only the committed per-release extracts (``data/attack_history/extracts``) and
``source_manifest.json`` written by ``scripts/fetch_attack_history.py``, so a fresh
clone reproduces every number without network access. Writes six tables and a
provenance manifest to ``data/attack_history/``. Deterministic.

See ``study/ATTACK_GAPS_PLAN.md`` for definitions, comparability rules and proofs.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from grrc.coverage_evolution import (
    BASE_HIGH, EFF_LOW, SPLIT_STAGE_MAP, STAGE_MAP, catastrophic_floor, comparable,
    coverage_profile, floors, inherit_parent_mitigations, kill_chain_techniques, load_extract,
    minimal_repair, mitigations_by_technique, stage_binding, stage_gaps)
from grrc.provenance import build_manifest, git_state, write_manifest
from grrc.utilities import write_csv

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/attack_history"
SOURCE = OUT / "source_manifest.json"
EPSILONS = (0.10, 0.05, 0.01)
KS = (1, 2, 3, 4)
E_NEW_GRID = (0.10, 0.20, 0.50)          # assumed worst-corner strength of a new mitigation
HEADLINE = ((0.10, 1), (0.05, 1), (0.05, 2))
BASE_GRID = (0.5, 0.7, 0.9)               # parameter sensitivity (latest release)
EFF_LOW_GRID = (0.10, 0.20, 0.35)


def _variant_row(version, variant, ex, exclude=True, stage_map=STAGE_MAP):
    """Coverage, floor and headline repair costs for one release under one variant."""
    total = next(r for r in coverage_profile(ex, exclude, stage_map) if r["stage"] == "all")
    fl = floors(ex, exclude_placeholders=exclude, stage_map=stage_map)
    row = dict(version=version, variant=variant, uncovered=total["uncovered"],
               gap_stages=sum(1 for g in stage_gaps(ex, exclude, stage_map).values() if g),
               clinical_floor=fl["clinical_floor"],
               catastrophic_floor_k1=catastrophic_floor(fl["clinical_floor"], 1))
    for eps, tag in ((0.10, "10"), (0.05, "05")):
        rr = minimal_repair(ex, eps, 1, exclude_placeholders=exclude, stage_map=stage_map)
        row[f"repair_{tag}_k1"] = rr["cost"] if rr["feasible"] else -1
    return row


def _release_row(ex, rec):
    ok, why = comparable(ex)
    row = dict(version=rec["version"], release_date=rec["release_date"], comparable=ok,
               reason=why, real_mitigations=-1, kill_chain_techniques=-1, uncovered=-1,
               uncovered_share=-1.0, single_mitigation=-1, parents=-1, parents_uncovered=-1,
               gap_stages=-1)
    if not ok:
        return row
    total = next(r for r in coverage_profile(ex) if r["stage"] == "all")
    by = mitigations_by_technique(ex)
    techs = kill_chain_techniques(ex)
    real = {m for ms in by.values() for m in ms}
    row.update(real_mitigations=len(real), kill_chain_techniques=total["techniques"],
               uncovered=total["uncovered"],
               uncovered_share=round(total["uncovered"] / total["techniques"], 6),
               single_mitigation=sum(len(by.get(t, [])) == 1 for t in techs),
               parents=total["parents"], parents_uncovered=total["parents_uncovered"],
               gap_stages=sum(1 for g in stage_gaps(ex).values() if g))
    return row


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-dirty", action="store_true")
    args = parser.parse_args()
    state = git_state()
    if (not state.get("available") or state["dirty"]) and not args.allow_dirty:
        raise SystemExit("Commit source and inputs before generation.")

    source = json.loads(SOURCE.read_text())
    releases = [(rec, load_extract(ROOT / rec["extract"])) for rec in source["releases"]]

    coverage, tactic_rows, floor_rows, repair_rows, sens_rows = [], [], [], [], []
    for rec, ex in releases:
        coverage.append(_release_row(ex, rec))
        if not coverage[-1]["comparable"]:
            continue
        v = rec["version"]
        for r in coverage_profile(ex):
            if r["stage"] != "all":
                tactic_rows.append(dict(version=v, release_date=rec["release_date"], **r))
        f = floors(ex)
        gaps = stage_gaps(ex)
        everything = frozenset(set().union(*gaps.values()))
        repaired = floors(ex, repaired=everything, e_new=EFF_LOW)
        row = dict(version=v, release_date=rec["release_date"],
                   control_floor=f["control_floor"], clinical_floor=f["clinical_floor"],
                   clinical_floor_all_gaps_repaired=repaired["clinical_floor"])
        for k in KS:
            row[f"catastrophic_floor_k{k}"] = catastrophic_floor(f["clinical_floor"], k)
            row[f"repaired_catastrophic_floor_k{k}"] = catastrophic_floor(
                repaired["clinical_floor"], k)
        floor_rows.append(row)
        grid = E_NEW_GRID if v == releases[-1][0]["version"] else (EFF_LOW,)
        for e_new in grid:
            for eps in EPSILONS:
                for k in KS:
                    rr = minimal_repair(ex, eps, k, e_new=e_new)
                    repair_rows.append(dict(
                        version=v, release_date=rec["release_date"], e_new=e_new, epsilon=eps,
                        k=k, feasible=rr["feasible"],
                        cost=rr["cost"] if rr["feasible"] else -1,
                        repaired_stages=len(rr["stages"]), stages="+".join(rr["stages"]),
                        floor_before=rr["floor_before"], floor_after=rr["floor_after"],
                        threshold=rr["threshold"]))
        # Sensitivity: default; placeholders counted as controls (as the earlier studies
        # did); sub-techniques inheriting their parent's mitigations.
        sens_rows.append(_variant_row(v, "default", ex))
        sens_rows.append(_variant_row(v, "placeholders_included", ex, exclude=False))
        sens_rows.append(_variant_row(v, "parent_inheritance", inherit_parent_mitigations(ex)))

    # Sensitivity: the v19 Defense Evasion split kept as two separate stages.
    latest_rec, latest = releases[-1]
    if comparable(latest, SPLIT_STAGE_MAP)[0]:
        sens_rows.append(_variant_row(latest_rec["version"], "defense_evasion_split", latest,
                                      stage_map=SPLIT_STAGE_MAP))

    # Parameter sensitivity (latest release): the floor and the repair under other
    # worst-corner base rates and effectiveness values. Coverage itself does not depend
    # on them; the magnitudes do.
    default_list = set(minimal_repair(latest, 0.10, 1)["techniques"])
    param_rows = []
    for base in BASE_GRID:
        for eff_low in EFF_LOW_GRID:
            fl = floors(latest, base=base, eff_low=eff_low)["clinical_floor"]
            r10 = minimal_repair(latest, 0.10, 1, base=base, eff_low=eff_low)
            r05 = minimal_repair(latest, 0.05, 1, base=base, eff_low=eff_low)
            param_rows.append(dict(
                version=latest_rec["version"], base=base, eff_low=eff_low,
                clinical_floor=fl, catastrophic_floor_k1=catastrophic_floor(fl, 1),
                repair_10_k1=r10["cost"] if r10["feasible"] else -1,
                repair_05_k1=r05["cost"] if r05["feasible"] else -1,
                repair_10_k1_within_default=bool(set(r10["techniques"]) <= default_list)))

    # What moved the floor: stages whose factor changed between consecutive comparable
    # releases, with the technique that binds the stage before and after.
    change_rows, prev = [], None
    comparable_releases = [(rec, ex) for rec, ex in releases if comparable(ex)[0]]
    for rec, ex in comparable_releases:
        bind = stage_binding(ex)
        names = {t["id"]: t["name"] for t in ex["techniques"]}
        gaps_now = stage_gaps(ex)
        if prev is not None:
            prev_rec, prev_bind, prev_names = prev
            for stage in bind:
                a, b = prev_bind[stage], bind[stage]
                if abs(a["factor"] - b["factor"]) > 1e-12:
                    change_rows.append(dict(
                        version=rec["version"], prev_version=prev_rec["version"], stage=stage,
                        factor_before=a["factor"], factor_after=b["factor"],
                        binding_before=a["technique"], binding_before_name=prev_names.get(a["technique"], ""),
                        binding_after=b["technique"], binding_after_name=names.get(b["technique"], ""),
                        uncovered_after=len(gaps_now[stage])))
        prev = (rec, bind, names)

    # The prioritised repair list on the latest release at the headline targets.
    names = {t["id"]: t["name"] for t in latest["techniques"]}
    gaps = stage_gaps(latest)
    list_rows = []
    for eps, k in HEADLINE:
        rr = minimal_repair(latest, eps, k)
        for tid in rr["techniques"]:
            list_rows.append(dict(version=latest_rec["version"], epsilon=eps, k=k, technique=tid,
                                  name=names.get(tid, ""),
                                  stages="+".join(s for s in gaps if tid in gaps[s])))

    # Sanity gates.
    cmp_rows = [r for r in coverage if r["comparable"]]
    for r in sens_rows:
        if r["variant"] in ("placeholders_included", "parent_inheritance"):
            ours = next(c for c in cmp_rows if c["version"] == r["version"])
            assert r["uncovered"] <= ours["uncovered"], f"{r['variant']} must never widen the gap"
    for r in floor_rows:
        assert r["clinical_floor_all_gaps_repaired"] <= r["clinical_floor"] + 1e-15
    by_key = {}
    for r in repair_rows:
        by_key.setdefault((r["version"], r["e_new"], r["k"]), []).append(r)
    for rows in by_key.values():
        costs = [r["cost"] if r["feasible"] else float("inf")
                 for r in sorted(rows, key=lambda r: -r["epsilon"])]
        assert costs == sorted(costs), "repair cost must not fall as epsilon tightens"
    # Cross-study gate: with placeholders counted, v17.1 reproduces the cyber-range
    # study's per-stage gap counts (non-impact stages).
    range_gaps = ROOT / "data/defense_range/coverage_gaps.csv"
    v171 = next((ex for rec, ex in releases if rec["version"] == "17.1"), None)
    if range_gaps.exists() and v171 is not None:
        ref = pd.read_csv(range_gaps).set_index("stage")["uncoverable"]
        ours = {r["stage"]: r["uncovered"] for r in coverage_profile(v171, False)}
        for stage, count in ref.items():
            if stage != "impact":
                assert ours[stage] == count, f"v17.1 {stage}: {ours[stage]} != range {count}"

    outputs = []
    for name, rows in [("coverage_by_release", coverage), ("coverage_by_tactic", tactic_rows),
                       ("floor_by_release", floor_rows), ("minimal_repair", repair_rows),
                       ("repair_list_latest", list_rows), ("sensitivity", sens_rows),
                       ("floor_changes", change_rows), ("parameter_sensitivity", param_rows)]:
        path = OUT / (name + ".csv")
        write_csv(pd.DataFrame(rows), path)
        outputs.append(path)
    inputs = [Path(__file__), ROOT / "study/ATTACK_GAPS_PLAN.md", SOURCE,
              ROOT / "src/grrc/coverage_evolution.py", ROOT / "src/grrc/joint_bounds.py",
              ROOT / "src/grrc/attack_graph.py", ROOT / "src/grrc/hospital_attack_model.py",
              ROOT / "src/grrc/enums.py", ROOT / "src/grrc/provenance.py",
              ROOT / "src/grrc/utilities.py"] + [ROOT / rec["extract"] for rec, _ in releases]
    manifest = build_manifest(
        run_id="attack-history", stage="analysis",
        description="MITRE ATT&CK Enterprise mitigation gaps across releases, the adaptive-"
                    "adversary residual-risk floor they impose, and the minimal coverage repair.",
        inputs=inputs, outputs=outputs, source_state=state,
        parameters=dict(releases=[rec["version"] for rec, _ in releases],
                        base_high=BASE_HIGH, eff_low=EFF_LOW, epsilons=list(EPSILONS),
                        ks=list(KS), e_new_grid=list(E_NEW_GRID),
                        base_grid=list(BASE_GRID), eff_low_grid=list(EFF_LOW_GRID),
                        placeholders=["M1055 Do Not Mitigate", "M1056 Pre-compromise"],
                        crosswalk="ATT&CK v19 stealth + defense-impairment -> defense-evasion",
                        scope="measures the knowledge base's mitigation mapping, not whether a "
                              "real-world defense exists; kill-chain stage model and worst-corner "
                              "effectiveness are analyst abstractions"))
    write_manifest(manifest, OUT / "attack_history_manifest.json")
    print(pd.DataFrame(coverage)[["version", "release_date", "comparable", "kill_chain_techniques",
                                  "uncovered", "uncovered_share", "gap_stages"]].to_string(index=False))


if __name__ == "__main__":
    main()
