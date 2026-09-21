#!/usr/bin/env python3
"""Generate the cyber-range paper's numbers/tables from committed CSVs."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from grrc.provenance import verify_manifest

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/defense_range"
PAPER = ROOT / "docs/defense_range"
WORD = {1: "One", 2: "Two", 3: "Three", 4: "Four"}       # macro names cannot contain digits


def _cost(x, computed=True):
    """Format a cost cell: -1 is 'none' (infeasible) or '$>$4' (beyond the exact cap)."""
    x = int(x)
    if x >= 0:
        return str(x)
    return "none" if computed else "$>$4"


def content():
    verify_manifest(DATA / "defense_range_manifest.json")
    params = json.loads((DATA / "defense_range_manifest.json").read_text())["parameters"]
    robust = pd.read_csv(DATA / "regime_robustness.csv").set_index("policy")
    gap = pd.read_csv(DATA / "optimality_gap.csv")
    lead = pd.read_csv(DATA / "leaderboard.csv")

    assumed = gap[gap.degradation_source == "assumed"]
    head = assumed[(assumed.epsilon == 0.05) & (assumed.k == 1)].iloc[0]   # headline regime

    def one(p):
        return f"{float(robust.loc[p, 'mean_cost_when_certified']):.1f}"

    values = {
        "RangeAttackVersion": str(params["attack_version"]),
        "RangeMitigations": str(int(params["n_mitigations"])),
        "RangeRegimes": str(int(gap.shape[0])),
        "RangeGreedyMeanCost": one("greedy"),
        "RangeCoverageMeanCost": one("coverage"),
        "RangeRandomMeanCost": one("random"),
        "RangeOptimalMeanCost": one("optimal"),
        "RangeOptimalCertPct": f"{100*float(robust.loc['optimal','certified_fraction']):.0f}",
        "RangeGreedyAssumedCost": f"{float(robust.loc['greedy','mean_cost_assumed']):.1f}",
        "RangeGreedyCipherCost": f"{float(robust.loc['greedy','mean_cost_cipher']):.1f}",
        "RangeHeadOptimal": _cost(head.optimal_size, bool(head.optimal_computed)),
        "RangeHeadGreedy": _cost(head.greedy_cost),
        "RangeHeadCoverage": _cost(head.coverage_cost),
        "RangeHeadRandom": _cost(head.random_cost),
        "RangeUndefendedKOnePct": f"{100*float(assumed[assumed.k==1].iloc[0].empty_cat_worst):.1f}",
    }
    generated = {"range_numbers.tex": "% Generated; do not edit. Certified cyber-range benchmark.\n"
                 + "".join("\\newcommand{\\" + k + "}{" + v + "}\n" for k, v in sorted(values.items()))}

    # Robustness / leaderboard table.
    rows = []
    disp = {"optimal": "Optimal (exact)", "greedy": "Greedy (certificate)",
            "coverage": "Coverage (blind)", "random": "Random"}
    for p in ("optimal", "greedy", "coverage", "random"):
        r = robust.loc[p]
        rows.append([disp[p], f"{100*float(r.certified_fraction):.0f}",
                     f"{float(r.mean_cost_when_certified):.1f}",
                     f"{float(r.mean_cost_assumed):.1f}", f"{float(r.mean_cost_cipher):.1f}"])
    generated["table_range_leaderboard_rows.tex"] = "% Generated from regime_robustness.csv.\n" + "".join(
        " & ".join(r) + " \\\\\n" for r in rows)

    # Optimality-gap table (assumed source).
    rows = []
    for _, r in assumed.sort_values(["epsilon", "k"], ascending=[False, True]).iterrows():
        rows.append([f"{r.epsilon:.2f}", str(int(r.k)),
                     _cost(r.optimal_size, bool(r.optimal_computed)),
                     _cost(r.greedy_cost), _cost(r.coverage_cost), _cost(r.random_cost)])
    generated["table_range_gap_rows.tex"] = "% Generated from optimality_gap.csv (assumed source).\n" + "".join(
        " & ".join(r) + " \\\\\n" for r in rows)
    return generated


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    generated = content()
    PAPER.mkdir(parents=True, exist_ok=True)
    if args.check:
        for name, value in generated.items():
            if (PAPER / name).read_text(encoding="utf-8") != value:
                raise AssertionError("stale generated TeX: " + name)
        print("cyber-range paper values verified")
        return 0
    for name, value in generated.items():
        (PAPER / name).write_text(value, encoding="utf-8", newline="\n")
    print(f"wrote {len(generated)} generated files to {PAPER.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
