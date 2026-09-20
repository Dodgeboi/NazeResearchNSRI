#!/usr/bin/env python3
"""Execute CLINICAL_VALIDATION_PLAN.md: validate the ATT&CK-clinical model vs CIPHER.

Compares the model's CIPHER-independent predicted per-service impact profiles
(uniform ATT&CK-null; Neprash-anchored assumed) against the held-out real CIPHER
harm distribution, via total-variation distance, an exact Monte-Carlo multinomial
goodness-of-fit, and the reconciling-gamma; and emits the CIPHER clinical-resolution
overlay that ATT&CK lacks.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from grrc.attack_graph import build_graph, load_bundle
from grrc.cipher_bounds import (load_corpus, high_severity_counts, DOMAIN_SERVICE,
                                CLINICAL_SERVICES, HIGH_SEVERITY)
from grrc.clinical_validation import (predicted_profiles, observed_profile,
                                      total_variation, multinomial_gof, reconciling_gamma)
from grrc.hospital_attack_model import build_model
from grrc.provenance import build_manifest, git_state, write_manifest
from grrc.utilities import write_csv

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "data/attack/raw/enterprise-attack-17.1.json.gz"
CIPHER = ROOT / "data/cipher/raw/cipher-v1.0.1.csv"
TAUS = (6, 7, 8)
PRIMARY_TAU = HIGH_SEVERITY
MC_DRAWS = 20000
MC_SEED = 20260920
TIME_ORDER = ["First Hour", "First Day", "First Week", "Week 2", "First Month"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-dirty", action="store_true")
    args = parser.parse_args()
    state = git_state()
    if (not state.get("available") or state["dirty"]) and not args.allow_dirty:
        raise SystemExit("Commit source and inputs before generation.")
    out = ROOT / "data/clinical_validation"
    out.mkdir(exist_ok=True)

    model = build_model(build_graph(load_bundle(BUNDLE)))
    df = load_corpus(CIPHER)
    services = [s.value for s in CLINICAL_SERVICES]
    preds = predicted_profiles(model)

    # Profiles table (primary tau).
    counts, obs, other, total = observed_profile(df, PRIMARY_TAU)
    profile_rows = [dict(profile="observed_cipher", tau=PRIMARY_TAU,
                         **{s: float(v) for s, v in zip(services, obs)})]
    for name, p in preds.items():
        profile_rows.append(dict(profile=name, tau=PRIMARY_TAU,
                                 **{s: float(v) for s, v in zip(services, p)}))

    # Goodness-of-fit across profiles and tau sensitivity.
    gof_rows, residual_rows = [], []
    for tau in TAUS:
        c, o, oth, tot = observed_profile(df, tau)
        for name, p in preds.items():
            mc, chi, stat = multinomial_gof(c, p, draws=MC_DRAWS, seed=MC_SEED)
            rg = reconciling_gamma(c, tot, p)
            gof_rows.append(dict(profile=name, tau=tau, total_variation=total_variation(p, o),
                                 mc_pvalue=mc, chi2_pvalue=chi, chi2_stat=stat,
                                 reconciling_gamma=(None if rg == float("inf") else rg),
                                 high_severity_total=int(tot),
                                 modelled_service_records=int(c.sum())))
            if tau == PRIMARY_TAU:
                for s, pv, ov in zip(services, p, o):
                    residual_rows.append(dict(profile=name, service=s, predicted=float(pv),
                                              observed=float(ov), residual=float(pv - ov)))

    # Overlay: CIPHER clinical-resolution layer ATT&CK lacks.
    inv = {d: s.value for d, s in DOMAIN_SERVICE.items()}
    df2 = df.copy()
    df2["service"] = df2["Technical Domain"].map(inv)
    mapped = df2[df2["service"].notna()]
    specialty_rows, timing_rows, severity_rows = [], [], []
    for svc in services:
        sub = mapped[mapped["service"] == svc]
        n = len(sub)
        severity_rows.append(dict(service=svc, records=n,
                                  mean_impact=float(sub["Clinical Impact Score"].mean()) if n else 0.0))
        for spec, cnt in sub["Speciality"].value_counts().head(5).items():
            specialty_rows.append(dict(service=svc, specialty=str(spec), records=int(cnt),
                                       share=float(cnt / n) if n else 0.0))
        tp = sub["Time Point"].value_counts()
        denom = int(tp.reindex(TIME_ORDER).fillna(0).sum())
        for t in TIME_ORDER:
            timing_rows.append(dict(service=svc, time_point=t,
                                    fraction=float(tp.get(t, 0) / denom) if denom else 0.0))

    # Sanity gates.
    for name, p in preds.items():
        if abs(float(np.sum(p)) - 1) > 1e-9:
            raise AssertionError("predicted profile must sum to one")
    if abs(obs.sum() - 1) > 1e-9:
        raise AssertionError("observed profile must sum to one")
    for r in gof_rows:
        if not 0 <= r["total_variation"] <= 1:
            raise AssertionError("total variation must lie in [0, 1]")
    # reconciling gamma is 0 only for an exact match.
    self_g = reconciling_gamma(counts, total, obs)
    if abs(self_g) > 1e-9:
        raise AssertionError("reconciling gamma against the observed profile itself must be 0")

    outputs = []
    for name, rows in [("profiles", profile_rows), ("goodness_of_fit", gof_rows),
                       ("residuals", residual_rows), ("overlay_specialty", specialty_rows),
                       ("overlay_timing", timing_rows), ("overlay_severity", severity_rows)]:
        path = out / (name + ".csv")
        write_csv(pd.DataFrame(rows), path)
        outputs.append(path)
    inputs = [Path(__file__), ROOT / "study/CLINICAL_VALIDATION_PLAN.md", BUNDLE,
              ROOT / "data/attack/raw/source.json", CIPHER,
              ROOT / "data/cipher/raw/source_manifest.json"] + [
        ROOT / ("src/grrc/" + m + ".py") for m in
        ["clinical_validation", "cipher_bounds", "hospital_attack_model", "attack_graph",
         "enums", "provenance", "utilities"]]
    manifest = build_manifest(
        run_id="clinical-validation", stage="validation",
        description="First calibration of an ATT&CK-based clinical-impact model against the "
                    "real CIPHER coded patient-harm corpus, with an ATT&CK clinical-resolution overlay.",
        inputs=inputs, outputs=outputs, source_state=state,
        parameters=dict(attack_version=model.graph.version, taus=list(TAUS), primary_tau=PRIMARY_TAU,
                        mc_draws=MC_DRAWS, mc_seed=MC_SEED, services=services,
                        predicted_profiles=list(preds.keys()),
                        held_out="CIPHER used only as ground truth; predicted profiles are "
                                 "CIPHER-independent (uniform null and Neprash-anchored assumed)",
                        scope="convenience sample; consistency with this corpus, not population; "
                              "small N, low power; single-label coding; not causal"))
    write_manifest(manifest, out / "clinical_validation_manifest.json")
    print(pd.DataFrame(gof_rows)[gof_rows[0].keys()].to_string(index=False))
    print("\nresiduals (primary tau, predicted - observed):")
    print(pd.DataFrame(residual_rows).to_string(index=False))


if __name__ == "__main__":
    main()
