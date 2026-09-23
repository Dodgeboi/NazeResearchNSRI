#!/usr/bin/env python3
"""Worked example for the closed-form k-of-n theorem (study/KOFN_THEOREM.md).

For real per-service sustained-outage marginals from the ATT&CK-driven hospital
(the worst interval corner, for the empty and the hospital_core portfolios), tabulate
for every k = 1..n: the theorem's closed form, the independent LP oracle (to show
they agree to machine precision), and the classical union and Markov upper bounds
(to show the closed form is at least as tight, and strictly tighter for k >= 2).
Deterministic; writes committed numbers the LaTeX note draws from, under a manifest.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from grrc.attack_graph import build_graph, load_bundle
from grrc.hospital_attack_model import build_model, service_outage
from grrc.joint_bounds import sharp_k_of_n_closed_form, _lp_k_of_n_upper
from grrc.provenance import build_manifest, git_state, write_manifest
from grrc.utilities import write_csv

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "data/attack/raw/enterprise-attack-17.1.json.gz"
BASE_HIGH = 0.9          # worst-corner base rate (matches the catastrophic certificate)
EFF_LOW = 0.20           # worst-corner effectiveness
PORTFOLIOS = {
    "empty": [],
    "hospital_core": ["M1032", "M1030", "M1051", "M1053", "M1040"],
}


def worst_corner_marginals(model, mitigation_ids):
    """Per-service worst-corner sustained-outage marginals for one portfolio."""
    mits = model.graph.mitigations
    idx = {m: i for i, m in enumerate(mits)}
    port = np.zeros((1, model.graph.n_mitigations), bool)
    port[0, [idx[m] for m in mitigation_ids if m in idx]] = True
    eff = np.tile((EFF_LOW, EFF_LOW), (model.graph.n_mitigations, 1)).astype(float)
    deg = model.degradation[:, 1]            # adverse (high) degradation corner
    return service_outage(port, BASE_HIGH, eff[:, 0], deg, model)[0]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-dirty", action="store_true")
    args = parser.parse_args()
    state = git_state()
    if (not state.get("available") or state["dirty"]) and not args.allow_dirty:
        raise SystemExit("Commit source and inputs before generation.")
    out = ROOT / "data/kofn_theorem"
    out.mkdir(exist_ok=True)

    model = build_model(build_graph(load_bundle(BUNDLE)))
    services = [s.value for s in model.services]
    n = len(services)

    marg_rows, bound_rows = [], []
    for name, ids in PORTFOLIOS.items():
        marg = worst_corner_marginals(model, ids)
        marg_rows.append(dict(portfolio=name,
                              **{s: float(v) for s, v in zip(services, marg)}))
        for k in range(1, n + 1):
            cf = sharp_k_of_n_closed_form(marg, k)
            lp = _lp_k_of_n_upper(marg, k)
            union = float(min(1.0, marg.sum()))
            markov = float(min(1.0, marg.sum() / k))
            bound_rows.append(dict(portfolio=name, k=k, closed_form=cf, lp_oracle=lp,
                                   lp_abs_error=abs(cf - lp), union_bound=union,
                                   markov_bound=markov))

    # Sanity gates: closed form == LP; closed form <= union and <= Markov;
    # strictly tighter than union for k>=2 (empty portfolio, unequal marginals).
    for r in bound_rows:
        if r["lp_abs_error"] > 1e-9:
            raise AssertionError("closed form must equal the LP oracle")
        if r["closed_form"] > r["union_bound"] + 1e-12 or r["closed_form"] > r["markov_bound"] + 1e-12:
            raise AssertionError("closed form must not exceed union/Markov")
    empty_k2 = next(r for r in bound_rows if r["portfolio"] == "empty" and r["k"] == 2)
    if not empty_k2["closed_form"] < empty_k2["union_bound"] - 1e-9:
        raise AssertionError("closed form must be strictly tighter than union for k>=2")

    outputs = []
    for fname, rows in [("worked_marginals", marg_rows), ("worked_bounds", bound_rows)]:
        path = out / (fname + ".csv")
        write_csv(pd.DataFrame(rows), path)
        outputs.append(path)
    inputs = [Path(__file__), ROOT / "study/KOFN_THEOREM.md", BUNDLE,
              ROOT / "data/attack/raw/source.json"] + [
        ROOT / ("src/grrc/" + m + ".py") for m in
        ["joint_bounds", "hospital_attack_model", "attack_graph", "enums",
         "provenance", "utilities"]]
    manifest = build_manifest(
        run_id="kofn-theorem", stage="analysis",
        description="Worked example for the closed-form sharp k-of-n outage theorem: "
                    "closed form vs LP oracle vs union/Markov on real hospital worst-corner marginals.",
        inputs=inputs, outputs=outputs, source_state=state,
        parameters=dict(attack_version=model.graph.version, base_high=BASE_HIGH,
                        eff_low=EFF_LOW, portfolios={k: v for k, v in PORTFOLIOS.items()},
                        services=services, n=n,
                        theorem="max_couplings P(sum X_i >= k) = min(1, min_j (1/(k-j)) sum of n-j "
                                "smallest marginals); see study/KOFN_THEOREM.md",
                        scope="classical Frechet/Ruschendorf lineage; closed form proved and LP-verified; "
                              "marginals are evidence-anchored worst-corner values, not measured incidents"))
    write_manifest(manifest, out / "kofn_theorem_manifest.json")
    print(pd.DataFrame(bound_rows).to_string(index=False))


if __name__ == "__main__":
    main()
