#!/usr/bin/env python3
"""Run the certified cyber-range benchmark (study/DEFENSE_RANGE_PLAN.md).

Scores every reference automated defender (greedy, coverage, random, exact
optimal, empty, all) across the adaptive threat-regime sweep -- assumed vs real
CIPHER-derived degradation, an epsilon grid, and k = 1..n -- on the real MITRE
ATT&CK-driven hospital, and writes the leaderboard, optimality-gap and
regime-robustness tables with a provenance manifest. Deterministic (seeded random
policy); the score is the distribution-free residual-risk certificate, not an
empirical attack-success rate.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from grrc.attack_graph import build_graph, load_bundle
from grrc.cipher_bounds import load_corpus
from grrc.hospital_attack_model import build_model
from grrc.provenance import build_manifest, git_state, write_manifest
from grrc.range import default_regimes
from grrc.range.regimes import BASE_BOUNDS, DEFAULT_EFF, EVIDENCE_EFF, EPSILONS
from grrc.range.runner import run_sweep
from grrc.utilities import write_csv

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "data/attack/raw/enterprise-attack-17.1.json.gz"
CIPHER = ROOT / "data/cipher/raw/cipher-v1.0.1.csv"
SEED = 20260921


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-dirty", action="store_true")
    args = parser.parse_args()
    state = git_state()
    if (not state.get("available") or state["dirty"]) and not args.allow_dirty:
        raise SystemExit("Commit source and inputs before generation.")
    out = ROOT / "data/defense_range"
    out.mkdir(exist_ok=True)

    model = build_model(build_graph(load_bundle(BUNDLE)))
    df = load_corpus(CIPHER)
    regimes = default_regimes(model, cipher_df=df)
    result = run_sweep(model, regimes, seed=SEED)

    outputs = []
    for name in ("leaderboard", "optimality_gap", "regime_robustness"):
        path = out / (name + ".csv")
        write_csv(pd.DataFrame(result[name]), path)
        outputs.append(path)

    inputs = [Path(__file__), ROOT / "study/DEFENSE_RANGE_PLAN.md", BUNDLE,
              ROOT / "data/attack/raw/source.json", CIPHER,
              ROOT / "data/cipher/raw/source_manifest.json"] + [
        ROOT / ("src/grrc/range/" + m + ".py") for m in
        ["__init__", "environment", "policies", "regimes", "runner"]] + [
        ROOT / ("src/grrc/" + m + ".py") for m in
        ["attack_graph", "hospital_attack_model", "control_certificate", "joint_bounds",
         "cipher_bounds", "betting", "enums", "provenance", "utilities"]]
    manifest = build_manifest(
        run_id="defense-range", stage="analysis",
        description="Certified cyber-range benchmark: reference automated defenders scored by a "
                    "distribution-free residual-risk certificate across an adaptive threat-regime "
                    "sweep on the real ATT&CK-driven hospital.",
        inputs=inputs, outputs=outputs, source_state=state,
        parameters=dict(attack_version=model.graph.version, base_bounds=list(BASE_BOUNDS),
                        default_eff=list(DEFAULT_EFF), evidence_eff=EVIDENCE_EFF,
                        epsilons=list(EPSILONS), n_mitigations=model.graph.n_mitigations,
                        services=[s.value for s in model.services], seed=SEED,
                        adequacy_target="catastrophic k-of-n clinical (cat_guaranteed): worst-corner "
                                        "P(>=k services in sustained outage) <= epsilon",
                        policies=["greedy", "coverage", "random", "optimal", "empty", "all"],
                        scope="evaluation-environment/benchmark (WIP tier); ATT&CK and CIPHER are real; "
                              "hospital synthetic; effectiveness/degradation are analyst-prior intervals; "
                              "certificate verdicts are conditional worst-case frequencies, not "
                              "confidence levels; reference defenders are simple automated policies"))
    write_manifest(manifest, out / "defense_range_manifest.json")
    print(pd.DataFrame(result["regime_robustness"]).to_string(index=False))
    print("\noptimality gap (assumed source):")
    print(pd.DataFrame([g for g in result["optimality_gap"] if g["degradation_source"] == "assumed"])
          [["epsilon", "k", "optimal_size", "greedy_cost", "coverage_cost", "random_cost"]]
          .to_string(index=False))


if __name__ == "__main__":
    main()
