#!/usr/bin/env python3
"""Certified clinical-impact-bounded control selection on the ATT&CK-driven hospital.

For the evidence-anchored hospital model (grrc.hospital_attack_model), certify which
control portfolios provably keep patient-facing clinical-service outage below a
level under interval uncertainty, and report the certified cost-vs-outage frontier,
named realistic bundles, and sensitivity to the assumed uncertainty.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from grrc.attack_graph import build_graph, load_bundle
from grrc.hospital_attack_model import build_model, certify_clinical, SERVICE_DEGRADATION
from grrc.provenance import build_manifest, git_state, write_manifest
from grrc.utilities import write_csv

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "data/attack/raw/enterprise-attack-17.1.json.gz"
BASE_BOUNDS = (0.5, 0.9)
DEFAULT_EFF = (0.20, 0.70)
EVIDENCE_EFF = {"M1032": (0.85, 0.99)}
EPSILONS = (0.10, 0.05, 0.01)
PRIORS = {"narrow": (0.35, 0.55), "default": DEFAULT_EFF, "wide": (0.10, 0.85)}
NAMED = {
    "identity": ["M1032", "M1027", "M1018", "M1026"],
    "backup": ["M1053"],
    "segmentation": ["M1030"],
    "patching": ["M1051"],
    "detection": ["M1040", "M1049"],
    "hospital_core": ["M1032", "M1030", "M1051", "M1053", "M1040"],
}


def _eff(mitigations, prior):
    bounds = np.tile(prior, (len(mitigations), 1)).astype(float)
    idx = {m: i for i, m in enumerate(mitigations)}
    if prior == DEFAULT_EFF:
        for mid, interval in EVIDENCE_EFF.items():
            if mid in idx:
                bounds[idx[mid]] = interval
    return bounds


def _worst_union(port, model, eff, deg):
    return float(certify_clinical(port[None], BASE_BOUNDS, eff, deg, model, 0.5)[0][0, -1])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-dirty", action="store_true")
    args = parser.parse_args()
    state = git_state()
    if (not state.get("available") or state["dirty"]) and not args.allow_dirty:
        raise SystemExit("Commit source and inputs before generation.")
    out = ROOT / "data/clinical_certificate"
    out.mkdir(exist_ok=True)

    model = build_model(build_graph(load_bundle(BUNDLE)))
    mits = model.graph.mitigations
    idx = {m: i for i, m in enumerate(mits)}
    n = model.graph.n_mitigations
    deg = model.degradation
    eff = _eff(mits, DEFAULT_EFF)
    services = [s.value for s in model.services]

    empty = np.zeros((1, n), bool)
    empty_worst = certify_clinical(empty, BASE_BOUNDS, eff, deg, model, 0.5)[0][0]
    empty_union = float(empty_worst[-1])

    # Greedy frontier on worst-case union clinical outage.
    order, running = [], np.zeros(n, bool)
    remaining = set(range(n))
    frontier_rows, min_guard = [], {e: None for e in EPSILONS}
    while remaining:
        cands = sorted(remaining)
        best_m, best_u = None, None
        for m in cands:
            trial = running.copy(); trial[m] = True
            u = _worst_union(trial, model, eff, deg)
            if best_u is None or u < best_u:
                best_u, best_m = u, m
        running = running.copy(); running[best_m] = True
        remaining.discard(best_m)
        order.append(best_m)
        worst = certify_clinical(running[None], BASE_BOUNDS, eff, deg, model, 0.5)[0][0]
        row = dict(size=len(order), added=mits[best_m],
                   added_name=model.graph.mitigation_names[best_m])
        for s, v in zip(services, worst[:-1]):
            row[f"worst_{s}"] = float(v)
        row["worst_union"] = float(worst[-1])
        for e in EPSILONS:
            g = bool((worst <= e).all())
            row[f"guaranteed_{int(e*100):02d}"] = g
            if g and min_guard[e] is None:
                min_guard[e] = len(order)
        frontier_rows.append(row)

    named_rows = []
    for name, ids in NAMED.items():
        present = [idx[m] for m in ids if m in idx]
        port = np.zeros((1, n), bool); port[0, present] = True
        worst, best, guaranteed, possible = certify_clinical(port, BASE_BOUNDS, eff, deg, model, 0.05)
        row = dict(portfolio=name, size=len(present), worst_union=float(worst[0, -1]),
                   worst_ehr=float(worst[0, 0]))
        for e in EPSILONS:
            row[f"guaranteed_{int(e*100):02d}"] = bool((worst[0] <= e).all())
            row[f"possible_{int(e*100):02d}"] = bool((best[0] <= e).all())
        named_rows.append(row)

    summary_rows = [dict(epsilon=e, empty_union_outage=empty_union,
                         min_guaranteed_size=min_guard[e],
                         named_guaranteed=int(sum(r[f"guaranteed_{int(e*100):02d}"] for r in named_rows)))
                    for e in EPSILONS]

    sensitivity_rows = []
    for label, prior in PRIORS.items():
        eff_p = _eff(mits, prior)
        ew = float(certify_clinical(empty, BASE_BOUNDS, eff_p, deg, model, 0.5)[0][0, -1])
        run = np.zeros(n, bool); size05 = None
        rem = set(range(n))
        while rem and size05 is None:
            best_m, best_u = None, None
            for m in sorted(rem):
                t = run.copy(); t[m] = True
                u = _worst_union(t, model, eff_p, deg)
                if best_u is None or u < best_u:
                    best_u, best_m = u, m
            run = run.copy(); run[best_m] = True; rem.discard(best_m)
            worst = certify_clinical(run[None], BASE_BOUNDS, eff_p, deg, model, 0.5)[0][0]
            if (worst <= 0.05).all():
                size05 = int(run.sum())
        sensitivity_rows.append(dict(prior=label, eff_low=prior[0], eff_high=prior[1],
                                     empty_union_outage=ew, min_guaranteed_size_at_05=size05))

    # Sanity gates.
    u = [r["worst_union"] for r in frontier_rows]
    if any(u[i] < u[i + 1] - 1e-12 for i in range(len(u) - 1)):
        raise AssertionError("greedy worst-case union outage must be non-increasing")

    outputs = []
    for name, rows in [("clinical_frontier", frontier_rows), ("clinical_named", named_rows),
                       ("clinical_summary", summary_rows), ("clinical_sensitivity", sensitivity_rows)]:
        path = out / (name + ".csv")
        write_csv(pd.DataFrame(rows), path)
        outputs.append(path)
    inputs = [Path(__file__), ROOT / "study/EVIDENCE_ANCHORED_HOSPITAL.md", BUNDLE,
              ROOT / "data/attack/raw/source.json"] + [
        ROOT / ("src/grrc/" + m + ".py") for m in
        ["attack_graph", "hospital_attack_model", "control_certificate", "betting",
         "enums", "provenance", "utilities"]]
    manifest = build_manifest(
        run_id="clinical-certificate", stage="analysis",
        description="Certified clinical-impact-bounded control selection on the "
                    "evidence-anchored ATT&CK-driven hospital model.",
        inputs=inputs, outputs=outputs, source_state=state,
        parameters=dict(attack_version=model.graph.version, base_bounds=list(BASE_BOUNDS),
                        default_eff=list(DEFAULT_EFF), evidence_eff=EVIDENCE_EFF,
                        service_degradation={s.value: list(v) for s, v in SERVICE_DEGRADATION.items()},
                        epsilons=list(EPSILONS), services=services,
                        impact_techniques=[model.graph.techniques[i] for i in model.impact_members],
                        scope="ATT&CK structure real; effectiveness and clinical-degradation are "
                              "evidence-anchored intervals; no hospital-specific validation"))
    write_manifest(manifest, out / "clinical_certificate_manifest.json")
    print(pd.DataFrame(summary_rows).to_string(index=False))
    print("\nnamed:")
    print(pd.DataFrame(named_rows)[["portfolio", "size", "worst_union", "guaranteed_05", "possible_05"]].to_string(index=False))
    print("\nsensitivity:")
    print(pd.DataFrame(sensitivity_rows).to_string(index=False))


if __name__ == "__main__":
    main()
