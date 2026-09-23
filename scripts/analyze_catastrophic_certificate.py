#!/usr/bin/env python3
"""Sharp k-of-n catastrophic clinical-outage certification on the ATT&CK-hospital.

Certifies P(at least k of the four clinical services in simultaneous sustained
outage) <= epsilon for k = 1..4, under both the assumed and the CIPHER-derived
degradation intervals, and reports the minimum guaranteed control count and the
named-bundle guarantees. k = 1 reproduces the loose union-bound result; higher k is
the clinically meaningful catastrophic event and is far more certifiable.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from grrc.attack_graph import build_graph, load_bundle
from grrc.cipher_bounds import degradation_bounds
from grrc.hospital_attack_model import build_model, certify_catastrophic
from grrc.provenance import build_manifest, git_state, write_manifest
from grrc.utilities import write_csv

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "data/attack/raw/enterprise-attack-17.1.json.gz"
CIPHER = ROOT / "data/cipher/raw/cipher-v1.0.1.csv"
BASE_BOUNDS = (0.5, 0.9)
DEFAULT_EFF = (0.20, 0.70)
EVIDENCE_EFF = {"M1032": (0.85, 0.99)}
EPSILON = 0.05
KS = (1, 2, 3, 4)
CIPHER_GAMMA = 1.0
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


def _worst(port, model, eff, deg, k):
    return float(certify_catastrophic(port[None], BASE_BOUNDS, eff, deg, model, k, 0.5)[0][0])


def _min_guaranteed(model, eff, deg, k, eps=EPSILON):
    n = model.graph.n_mitigations
    run = np.zeros(n, bool); rem = set(range(n))
    if _worst(run, model, eff, deg, k) <= eps:
        return 0
    while rem:
        best_m, best_v = None, None
        for m in sorted(rem):
            t = run.copy(); t[m] = True
            v = _worst(t, model, eff, deg, k)
            if best_v is None or v < best_v:
                best_v, best_m = v, m
        run = run.copy(); run[best_m] = True; rem.discard(best_m)
        if _worst(run, model, eff, deg, k) <= eps:
            return int(run.sum())
    return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-dirty", action="store_true")
    args = parser.parse_args()
    state = git_state()
    if (not state.get("available") or state["dirty"]) and not args.allow_dirty:
        raise SystemExit("Commit source and inputs before generation.")
    out = ROOT / "data/catastrophic_certificate"
    out.mkdir(exist_ok=True)

    model = build_model(build_graph(load_bundle(BUNDLE)))
    mits = model.graph.mitigations
    idx = {m: i for i, m in enumerate(mits)}
    n = model.graph.n_mitigations
    eff = _eff(mits)
    degradations = {"assumed": model.degradation,
                    "cipher_gamma1": degradation_bounds(pd_read(CIPHER), CIPHER_GAMMA)}

    summary_rows, named_rows = [], []
    empty = np.zeros(n, bool)
    for label, deg in degradations.items():
        for k in KS:
            ew = _worst(empty, model, eff, deg, k)
            summary_rows.append(dict(degradation=label, k=k, epsilon=EPSILON,
                                     empty_worst=ew, min_guaranteed_size=_min_guaranteed(model, eff, deg, k)))
        for name, ids in NAMED.items():
            port = np.zeros((1, n), bool)
            port[0, [idx[m] for m in ids if m in idx]] = True
            row = dict(degradation=label, portfolio=name,
                       size=int(port.sum()))
            for k in KS:
                worst, best, guaranteed, possible = certify_catastrophic(
                    port, BASE_BOUNDS, eff, deg, model, k, EPSILON)
                row[f"worst_k{k}"] = float(worst[0])
                row[f"guaranteed_k{k}"] = bool(guaranteed[0])
            named_rows.append(row)

    # Sanity gates.
    assumed = model.degradation
    for k in KS:  # worst is non-increasing in k
        vals = [_worst(empty, model, eff, assumed, kk) for kk in KS]
        assert all(vals[i] >= vals[i + 1] - 1e-9 for i in range(len(vals) - 1)), "P(>=k) must fall in k"
        break
    # k=1 sharp equals the union of per-service outage (min(1, sum)).
    from grrc.hospital_attack_model import certify_clinical
    u = certify_clinical(empty[None], BASE_BOUNDS, eff, assumed, model, 0.5)[0][0, -1]
    if abs(_worst(empty, model, eff, assumed, 1) - min(1.0, u)) > 1e-9:
        raise AssertionError("k=1 sharp bound must equal the union bound")

    outputs = []
    for name, rows in [("catastrophic_summary", summary_rows), ("catastrophic_named", named_rows)]:
        path = out / (name + ".csv")
        write_csv(pd.DataFrame(rows), path)
        outputs.append(path)
    inputs = [Path(__file__), BUNDLE, ROOT / "data/attack/raw/source.json", CIPHER,
              ROOT / "data/cipher/raw/source_manifest.json"] + [
        ROOT / ("src/grrc/" + m + ".py") for m in
        ["joint_bounds", "hospital_attack_model", "attack_graph", "cipher_bounds",
         "control_certificate", "enums", "provenance", "utilities"]]
    manifest = build_manifest(
        run_id="catastrophic-certificate", stage="analysis",
        description="Sharp distribution-free k-of-n catastrophic clinical-outage certificate "
                    "on the ATT&CK-driven hospital, assumed vs CIPHER-derived degradation.",
        inputs=inputs, outputs=outputs, source_state=state,
        parameters=dict(attack_version=model.graph.version, base_bounds=list(BASE_BOUNDS),
                        default_eff=list(DEFAULT_EFF), evidence_eff=EVIDENCE_EFF, epsilon=EPSILON,
                        ks=list(KS), cipher_gamma=CIPHER_GAMMA, services=[s.value for s in model.services],
                        bound="sharp k-of-n distribution-free (closed form, study/KOFN_THEOREM.md; LP-verified)",
                        scope="classical aggregation bound; ATT&CK structure real; effectiveness and "
                              "degradation are evidence-anchored intervals; no incident validation"))
    write_manifest(manifest, out / "catastrophic_certificate_manifest.json")
    print(pd.DataFrame(summary_rows).to_string(index=False))


def pd_read(path):
    from grrc.cipher_bounds import load_corpus
    return load_corpus(path)


if __name__ == "__main__":
    main()
