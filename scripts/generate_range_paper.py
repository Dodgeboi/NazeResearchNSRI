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


def _gapcell(x, computed=True, feasible=True):
    """Cost cell for the gap table: 'none' when no portfolio certifies, '>4' beyond the cap."""
    x = int(x)
    if x >= 0:
        return str(x)
    if not feasible:
        return "none"
    return "none" if computed else "$>$4"


def content():
    verify_manifest(DATA / "defense_range_manifest.json")
    params = json.loads((DATA / "defense_range_manifest.json").read_text())["parameters"]
    robust = pd.read_csv(DATA / "regime_robustness.csv").set_index("policy")
    gap = pd.read_csv(DATA / "optimality_gap.csv")

    assumed_adv = gap[(gap.adversary == "adaptive") & (gap.degradation_source == "assumed")]
    assumed_typ = gap[(gap.adversary == "typical") & (gap.degradation_source == "assumed")]
    # The one regime where the adaptive adversary is non-trivially certifiable (k=3),
    # illustrating greedy's gap from the exact optimum.
    ex = assumed_adv[(assumed_adv.epsilon == 0.10) & (assumed_adv.k == 3)].iloc[0]

    def undef(df):
        return f"{100*float(df[df.k == 1].iloc[0].empty_cat_worst):.1f}"

    values = {
        "RangeAttackVersion": str(params["attack_version"]),
        "RangeMitigations": str(int(params["n_mitigations"])),
        "RangeRegimes": str(int(gap.shape[0])),
        "RangeAdaptiveRegimes": str(int(len(assumed_adv))),
        "RangeAdaptiveUncert": str(int((~assumed_adv.all_certifies).sum())),
        "RangeTypicalUncert": str(int((~assumed_typ.all_certifies).sum())),
        "RangeUndefendedTypicalKOnePct": undef(assumed_typ),
        "RangeUndefendedAdaptiveKOnePct": undef(assumed_adv),
        "RangeAdvExEps": f"{float(ex.epsilon):.2f}",
        "RangeAdvExK": str(int(ex.k)),
        "RangeAdvExOptimal": _gapcell(ex.optimal_size, bool(ex.optimal_computed), bool(ex.all_certifies)),
        "RangeAdvExGreedy": _gapcell(ex.greedy_cost, feasible=bool(ex.all_certifies)),
        "RangeAdvExCoverage": _gapcell(ex.coverage_cost, feasible=bool(ex.all_certifies)),
    }
    for p in ("greedy", "coverage", "optimal", "random"):
        values[f"Range{p.capitalize()}TypicalCost"] = f"{float(robust.loc[p,'mean_cost_typical']):.1f}"
        values[f"Range{p.capitalize()}AdaptiveCost"] = f"{float(robust.loc[p,'mean_cost_adaptive']):.1f}"
    generated = {"range_numbers.tex": "% Generated; do not edit. Certified cyber-range benchmark.\n"
                 + "".join("\\newcommand{\\" + k + "}{" + v + "}\n" for k, v in sorted(values.items()))}

    # Leaderboard table: mean cost per policy under each adversary (over certified regimes).
    rows = []
    disp = {"optimal": "Optimal (exact)", "greedy": "Greedy (certificate)",
            "coverage": "Coverage (blind)", "random": "Random"}
    for p in ("optimal", "greedy", "coverage", "random"):
        r = robust.loc[p]
        rows.append([disp[p], f"{100*float(r.certified_fraction):.0f}",
                     f"{float(r.mean_cost_typical):.1f}", f"{float(r.mean_cost_adaptive):.1f}"])
    generated["table_range_leaderboard_rows.tex"] = "% Generated from regime_robustness.csv.\n" + "".join(
        " & ".join(r) + " \\\\\n" for r in rows)

    # Adaptive-adversary feasibility/gap table (assumed degradation): 'none' where no
    # portfolio certifies at any cost -- the range's key finding.
    rows = []
    for _, r in assumed_adv.sort_values(["epsilon", "k"], ascending=[False, True]).iterrows():
        feas = bool(r.all_certifies)
        rows.append([f"{r.epsilon:.2f}", str(int(r.k)),
                     _gapcell(r.optimal_size, bool(r.optimal_computed), feas),
                     _gapcell(r.greedy_cost, feasible=feas),
                     _gapcell(r.coverage_cost, feasible=feas),
                     _gapcell(r.random_cost, feasible=feas)])
    generated["table_range_gap_rows.tex"] = "% Generated from optimality_gap.csv (adaptive, assumed).\n" + "".join(
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
