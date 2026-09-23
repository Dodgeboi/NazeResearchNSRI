#!/usr/bin/env python3
"""Execute CIPHER_INFERENCE_PLAN.md: selection-robust harm bounds and their effect.

Computes, from the real CIPHER corpus, each clinical service's high-severity harm
share and its partial-identification interval under bounded underreporting; then
re-runs the clinical-impact certificate with these real-data-derived degradation
intervals and compares against the assumed intervals.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from grrc.attack_graph import build_graph, load_bundle
from grrc.cipher_bounds import (load_corpus, high_severity_counts,
                                partial_identification_bounds, degradation_bounds,
                                time_profile, CLINICAL_SERVICES, HIGH_SEVERITY)
from grrc.hospital_attack_model import build_model, certify_clinical, SERVICE_DEGRADATION
from grrc.provenance import build_manifest, git_state, write_manifest
from grrc.utilities import write_csv

ROOT = Path(__file__).resolve().parents[1]
CIPHER = ROOT / "data/cipher/raw/cipher-v1.0.1.csv"
BUNDLE = ROOT / "data/attack/raw/enterprise-attack-17.1.json.gz"
GAMMAS = (0.0, 0.5, 1.0, 2.0)
INTEGRATION_GAMMA = 1.0
BASE_BOUNDS = (0.5, 0.9)
DEFAULT_EFF = (0.20, 0.70)
EVIDENCE_EFF = {"M1032": (0.85, 0.99)}
NAMED = {
    "identity": ["M1032", "M1027", "M1018", "M1026"],
    "backup": ["M1053"], "segmentation": ["M1030"], "patching": ["M1051"],
    "detection": ["M1040", "M1049"],
    "hospital_core": ["M1032", "M1030", "M1051", "M1053", "M1040"],
}


def _eff(mits):
    b = np.tile(DEFAULT_EFF, (len(mits), 1)).astype(float)
    idx = {m: i for i, m in enumerate(mits)}
    for mid, iv in EVIDENCE_EFF.items():
        if mid in idx:
            b[idx[mid]] = iv
    return b


def _min_guaranteed(model, eff, deg, target=0.05):
    n = model.graph.n_mitigations
    run = np.zeros(n, bool); rem = set(range(n))
    while rem:
        best_m, best_u = None, None
        for m in sorted(rem):
            t = run.copy(); t[m] = True
            u = certify_clinical(t[None], BASE_BOUNDS, eff, deg, model, 0.5)[0][0, -1]
            if best_u is None or u < best_u:
                best_u, best_m = u, m
        run = run.copy(); run[best_m] = True; rem.discard(best_m)
        worst = certify_clinical(run[None], BASE_BOUNDS, eff, deg, model, 0.5)[0][0]
        if (worst <= target).all():
            return int(run.sum())
    return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-dirty", action="store_true")
    args = parser.parse_args()
    state = git_state()
    if (not state.get("available") or state["dirty"]) and not args.allow_dirty:
        raise SystemExit("Commit source and inputs before generation.")
    out = ROOT / "data/cipher_inference"
    out.mkdir(exist_ok=True)

    df = load_corpus(CIPHER)
    counts, other, total = high_severity_counts(df)

    observed_rows = [dict(service=s.value, high_severity_records=counts[s],
                          observed_share=counts[s] / total) for s in CLINICAL_SERVICES]
    observed_rows.append(dict(service="unmodelled_residual", high_severity_records=other,
                              observed_share=other / total))

    gamma_rows = []
    for g in GAMMAS:
        b = partial_identification_bounds(counts, total, g)
        for s in CLINICAL_SERVICES:
            gamma_rows.append(dict(service=s.value, gamma=g, share_low=b[s][0], share_high=b[s][1]))

    time_rows = [dict(time_point=k, fraction=v) for k, v in time_profile(df).items()]

    # Integration: re-certify with CIPHER-derived degradation vs the assumed intervals.
    model = build_model(build_graph(load_bundle(BUNDLE)))
    mits = model.graph.mitigations
    idx = {m: i for i, m in enumerate(mits)}
    n = model.graph.n_mitigations
    eff = _eff(mits)
    assumed_deg = model.degradation
    cipher_deg = degradation_bounds(df, INTEGRATION_GAMMA)
    if not np.array_equal([s for s in model.services], list(CLINICAL_SERVICES)):
        raise AssertionError("service order mismatch between model and CIPHER mapping")

    compare_rows = []
    for label, deg in [("assumed", assumed_deg), ("cipher_gamma1", cipher_deg)]:
        empty_union = float(certify_clinical(np.zeros((1, n), bool), BASE_BOUNDS, eff, deg, model, 0.5)[0][0, -1])
        row = dict(degradation=label, empty_union_outage=empty_union,
                   min_guaranteed_size_at_05=_min_guaranteed(model, eff, deg))
        for name, ids in NAMED.items():
            port = np.zeros((1, n), bool)
            port[0, [idx[m] for m in ids if m in idx]] = True
            worst = certify_clinical(port, BASE_BOUNDS, eff, deg, model, 0.5)[0][0]
            row[f"{name}_worst_union"] = float(worst[-1])
            row[f"{name}_guaranteed_05"] = bool((worst <= 0.05).all())
        compare_rows.append(row)

    # Sanity: gamma-envelope widens; observed within it.
    for s in CLINICAL_SERVICES:
        prev = None
        for g in GAMMAS:
            lo, hi = partial_identification_bounds(counts, total, g)[s]
            if not 0 <= lo <= counts[s] / total + 1e-12 <= hi + 1e-12 <= 1 + 1e-9:
                raise AssertionError("observed share must lie within the envelope")
            if prev and (lo > prev[0] + 1e-12 or hi < prev[1] - 1e-12):
                raise AssertionError("envelope must widen with gamma")
            prev = (lo, hi)

    outputs = []
    for name, rows in [("observed_shares", observed_rows), ("gamma_bounds", gamma_rows),
                       ("time_profile", time_rows), ("certificate_comparison", compare_rows)]:
        path = out / (name + ".csv")
        write_csv(pd.DataFrame(rows), path)
        outputs.append(path)
    inputs = [Path(__file__), ROOT / "study/CIPHER_INFERENCE_PLAN.md", CIPHER,
              ROOT / "data/cipher/raw/source_manifest.json", BUNDLE,
              ROOT / "data/attack/raw/source.json"] + [
        ROOT / ("src/grrc/" + m + ".py") for m in
        ["cipher_bounds", "hospital_attack_model", "attack_graph", "control_certificate",
         "enums", "provenance", "utilities"]]
    manifest = build_manifest(
        run_id="cipher-inference", stage="analysis",
        description="Selection-robust clinical-harm bounds from the real CIPHER corpus and "
                    "their effect on the clinical-impact certificate.",
        inputs=inputs, outputs=outputs, source_state=state,
        parameters=dict(tau=HIGH_SEVERITY, gammas=list(GAMMAS), integration_gamma=INTEGRATION_GAMMA,
                        records=int(len(df)), high_severity_total=int(total),
                        assumed_degradation={s.value: list(v) for s, v in SERVICE_DEGRADATION.items()},
                        scope="convenience sample of reported harms; partial identification, not "
                              "incidence or causal; domain->service via repo coverage mapping"))
    write_manifest(manifest, out / "cipher_inference_manifest.json")
    print(pd.DataFrame(observed_rows).to_string(index=False))
    print("\ncertificate comparison (assumed vs CIPHER-derived degradation):")
    cols = ["degradation", "empty_union_outage", "min_guaranteed_size_at_05",
            "identity_worst_union", "hospital_core_worst_union", "hospital_core_guaranteed_05"]
    print(pd.DataFrame(compare_rows)[cols].to_string(index=False))


if __name__ == "__main__":
    main()
