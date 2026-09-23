#!/usr/bin/env python3
"""Execute CONTROL_CERTIFICATE_PLAN.md against the pinned MITRE ATT&CK bundle.

Certifies which control portfolios (sets of real ATT&CK mitigations) provably keep
ransomware reachability below a level under interval uncertainty, and reports the
greedy cost-vs-guarantee frontier, named realistic bundles, and a sensitivity of
the minimum guaranteed portfolio size to the assumed effectiveness prior.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from grrc.attack_graph import build_graph, load_bundle, RANSOMWARE_STAGES
from grrc.control_certificate import certify_portfolios, greedy_frontier, reachability
from grrc.provenance import build_manifest, git_state, write_manifest
from grrc.utilities import write_csv

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "data/attack/raw/enterprise-attack-17.1.json.gz"
BASE_BOUNDS = (0.5, 0.9)
EPSILONS = (0.10, 0.05, 0.01)
DEFAULT_EFF = (0.20, 0.70)
# Documented evidence-tightened interval: multi-factor authentication.
EVIDENCE_EFF = {"M1032": (0.85, 0.99)}
PRIORS = {"narrow": (0.35, 0.55), "default": DEFAULT_EFF, "wide": (0.10, 0.85)}
NAMED = {
    "identity": ["M1032", "M1027", "M1018", "M1026"],
    "backup": ["M1053"],
    "segmentation": ["M1030"],
    "patching": ["M1051"],
    "detection": ["M1040", "M1049"],
    "hospital_core": ["M1032", "M1030", "M1051", "M1053", "M1040"],
}


def _eff_bounds(mitigations, prior):
    bounds = np.tile(prior, (len(mitigations), 1)).astype(float)
    index = {m: i for i, m in enumerate(mitigations)}
    for mid, interval in EVIDENCE_EFF.items():
        if mid in index and prior == DEFAULT_EFF:
            bounds[index[mid]] = interval
    return bounds


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-dirty", action="store_true")
    args = parser.parse_args()
    state = git_state()
    if (not state.get("available") or state["dirty"]) and not args.allow_dirty:
        raise SystemExit("Commit source and inputs before generation.")
    out = ROOT / "data/attack_certificate"
    out.mkdir(exist_ok=True)

    graph = build_graph(load_bundle(BUNDLE))
    stages = [s for s in RANSOMWARE_STAGES if s != "impact"]
    stage_index = [graph.stage_members[s] for s in stages]
    impact = graph.impact_index
    n_mit = graph.n_mitigations
    index = {m: i for i, m in enumerate(graph.mitigations)}
    cov, usage = graph.coverage, graph.usage
    eff = _eff_bounds(graph.mitigations, DEFAULT_EFF)
    args_common = (cov, usage, stage_index, impact)

    empty = np.zeros((1, n_mit), bool)
    empty_worst = float(certify_portfolios(empty, BASE_BOUNDS, eff, *args_common, 0.5)[0][0])

    # Greedy cost-vs-guarantee frontier (default prior).
    order, _ = greedy_frontier(BASE_BOUNDS, eff, *args_common)
    frontier_rows, min_guaranteed = [], {e: None for e in EPSILONS}
    running = np.zeros(n_mit, bool)
    for size, m in enumerate(order, start=1):
        running = running.copy()
        running[m] = True
        worst, best, _, _ = certify_portfolios(running[None], BASE_BOUNDS, eff, *args_common, 0.5)
        row = dict(size=size, added=graph.mitigations[m],
                   added_name=graph.mitigation_names[m],
                   worst_reachability=float(worst[0]), best_reachability=float(best[0]))
        for e in EPSILONS:
            guaranteed = bool(worst[0] <= e)
            row[f"guaranteed_{int(e*100):02d}"] = guaranteed
            if guaranteed and min_guaranteed[e] is None:
                min_guaranteed[e] = size
        frontier_rows.append(row)

    # Named realistic bundles.
    named_rows = []
    for name, ids in NAMED.items():
        present = [index[m] for m in ids if m in index]
        port = np.zeros((1, n_mit), bool)
        port[0, present] = True
        worst, best, _, _ = certify_portfolios(port, BASE_BOUNDS, eff, *args_common, 0.5)
        row = dict(portfolio=name, mitigations="+".join(ids), size=len(present),
                   worst_reachability=float(worst[0]), best_reachability=float(best[0]))
        for e in EPSILONS:
            row[f"guaranteed_{int(e*100):02d}"] = bool(worst[0] <= e)
            row[f"possible_{int(e*100):02d}"] = bool(best[0] <= e)
        named_rows.append(row)

    # Summary per level.
    summary_rows = []
    for e in EPSILONS:
        summary_rows.append(dict(
            epsilon=e, empty_worst_reachability=empty_worst,
            min_guaranteed_portfolio_size=min_guaranteed[e],
            named_guaranteed=int(sum(r[f"guaranteed_{int(e*100):02d}"] for r in named_rows)),
            named_total=len(named_rows)))

    # Sensitivity of the minimum guaranteed size to the effectiveness prior.
    sensitivity_rows = []
    for label, prior in PRIORS.items():
        eff_p = _eff_bounds(graph.mitigations, prior)
        ew = float(certify_portfolios(empty, BASE_BOUNDS, eff_p, *args_common, 0.5)[0][0])
        order_p, _ = greedy_frontier(BASE_BOUNDS, eff_p, *args_common)
        run = np.zeros(n_mit, bool)
        size_at_05 = None
        for size, m in enumerate(order_p, start=1):
            run = run.copy(); run[m] = True
            worst = certify_portfolios(run[None], BASE_BOUNDS, eff_p, *args_common, 0.5)[0]
            if worst[0] <= 0.05:
                size_at_05 = size
                break
        sensitivity_rows.append(dict(prior=label, eff_low=prior[0], eff_high=prior[1],
                                     empty_worst_reachability=ew,
                                     min_guaranteed_size_at_05=size_at_05))

    # Sanity gates.
    for r in frontier_rows:
        if r["best_reachability"] > r["worst_reachability"] + 1e-12:
            raise AssertionError("best corner exceeds worst corner")
    worsts = [r["worst_reachability"] for r in frontier_rows]
    if any(worsts[i] < worsts[i + 1] - 1e-12 for i in range(len(worsts) - 1)):
        raise AssertionError("greedy worst-case reachability must be non-increasing")
    # Zero-uncertainty reproduces the point model.
    zero = np.column_stack([eff[:, 0], eff[:, 0]])
    pt = reachability(empty, BASE_BOUNDS[1], zero[:, 0], *args_common)[0]
    zc = certify_portfolios(empty, (BASE_BOUNDS[1], BASE_BOUNDS[1]), zero, *args_common, 0.5)[0][0]
    if abs(pt - zc) > 1e-12:
        raise AssertionError("zero-uncertainty corner must equal the point reachability")

    outputs = []
    for name, rows in [("greedy_frontier", frontier_rows), ("named_portfolios", named_rows),
                       ("certificate_summary", summary_rows), ("prior_sensitivity", sensitivity_rows)]:
        path = out / (name + ".csv")
        write_csv(pd.DataFrame(rows), path)
        outputs.append(path)
    inputs = [Path(__file__), ROOT / "study/CONTROL_CERTIFICATE_PLAN.md", BUNDLE,
              ROOT / "data/attack/raw/source.json"] + [
        ROOT / ("src/grrc/" + m + ".py") for m in
        ["attack_graph", "control_certificate", "betting", "provenance", "utilities"]]
    manifest = build_manifest(
        run_id="control-certificate", stage="analysis",
        description="Distribution-free ransomware-reachability control-adequacy certificates "
                    "on the pinned MITRE ATT&CK Enterprise kill chain.",
        inputs=inputs, outputs=outputs, source_state=state,
        parameters=dict(attack_version=graph.version, base_bounds=list(BASE_BOUNDS),
                        default_eff=list(DEFAULT_EFF), evidence_eff=EVIDENCE_EFF,
                        epsilons=list(EPSILONS), stages=stages, impact_technique="T1486",
                        n_techniques=graph.n_techniques, n_mitigations=n_mit,
                        scope="ATT&CK structure is real; effectiveness intervals are analyst "
                              "priors (one evidence-tightened); no real-incident validation"))
    write_manifest(manifest, out / "control_certificate_manifest.json")
    print(pd.DataFrame(summary_rows).to_string(index=False))
    print("\nnamed portfolios:")
    print(pd.DataFrame(named_rows)[["portfolio", "size", "worst_reachability",
          "guaranteed_10", "guaranteed_05"]].to_string(index=False))


if __name__ == "__main__":
    main()
