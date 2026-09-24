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
    gaps = pd.read_csv(DATA / "coverage_gaps.csv")
    afloor = pd.read_csv(DATA / "adaptive_floor.csv").set_index("k")
    priors = pd.read_csv(DATA / "prior_robustness.csv").set_index("prior")

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
    # Mechanism: coverage gaps, the reachability floor, and prior-robustness.
    values.update({
        "RangeStages": str(int(len(gaps))),
        "RangeUncoverableStages": str(int((gaps.uncoverable > 0).sum())),
        "RangeWorstGapStage": str(gaps.loc[gaps.uncoverable.idxmax(), "stage"]),
        "RangeWorstGapCount": str(int(gaps.uncoverable.max())),
        "RangeWorstGapTotal": str(int(gaps.loc[gaps.uncoverable.idxmax(), "techniques"])),
        "RangeControlFloorPct": f"{100*float(afloor['control_floor'].iloc[0]):.1f}",
        "RangeFloorKOnePct": f"{100*float(afloor.loc[1,'catastrophic_floor']):.1f}",
        "RangeFloorKFourPct": f"{100*float(afloor.loc[afloor.index.max(),'catastrophic_floor']):.1f}",
        "RangePriorMinUncert": str(int(priors["uncertifiable"].min())),
        "RangePriorRegimes": str(int(priors["regimes"].iloc[0])),
    })
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

    # Coverage-gap table: per stage, techniques MITRE lists no mitigation for.
    rows = []
    for _, r in gaps.iterrows():
        rows.append([str(r.stage), str(int(r.techniques)), str(int(r.uncoverable))])
    generated["table_range_coverage_rows.tex"] = "% Generated from coverage_gaps.csv.\n" + "".join(
        " & ".join(r) + " \\\\\n" for r in rows)
    generated.update(_llm_content())
    return generated


def _llm_constants():
    """The pre-declared protocol, read from the runner so the paper cannot drift from it."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("run_llm_defender",
                                                  ROOT / "scripts/run_llm_defender.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _llm_content():
    """Protocol macros always; results macros and table only once real runs exist."""
    run = _llm_constants()
    n_adaptive = sum(a == "adaptive" for a, _, _ in run.REGIMES)
    out = {"range_llm_protocol.tex": "% Generated from scripts/run_llm_defender.py.\n" + "".join(
        "\\newcommand{\\" + k + "}{" + v + "}\n" for k, v in sorted({
            "LlmRegimes": str(len(run.REGIMES)), "LlmTypical": str(len(run.REGIMES) - n_adaptive),
            "LlmAdaptive": str(n_adaptive), "LlmSeeds": str(len(run.SEEDS)),
            "LlmEpisodes": str(len(run.REGIMES) * len(run.SEEDS)),
            "LlmMaxSteps": str(run.MAX_STEPS), "LlmTemperature": f"{run.TEMPERATURE:g}",
            "LlmContext": str(run.NUM_CTX)}.items()))}
    runs = sorted(p for p in (ROOT / "data/llm_defender").glob("*/summary.csv")
                  if p.parent.name != "dry-run-greedy")
    if not runs:
        return out
    df = pd.concat([pd.read_csv(p) for p in runs], ignore_index=True)
    df = df[df.regime.isin([f"{a}|assumed|eps={e:.2f}|k={k}" for a, e, k in run.REGIMES])]
    records = {p.parent.name: json.loads((p.parent / "run_record.json").read_text()) for p in runs}
    first = records[sorted(records)[0]]
    meta = first.get("ollama") or {}
    typ = df[df.adversary == "typical"]
    cert_adapt = df[(df.adversary == "adaptive") & df.certifiable]
    uncert = df[~df.certifiable]
    typ_ok = typ[typ.certified]
    ratio = (typ_ok.cost_to_certify / typ_ok.optimal_size.where(typ_ok.optimal_computed)
             .replace(0, float("nan"))).dropna()
    vals = {
        "LlmModel": ", ".join(sorted(df.model.unique())).replace("_", "\\_"),
        "LlmParams": str(meta.get("parameter_size") or "unknown"),
        "LlmQuant": str(meta.get("quantization") or "unknown").replace("_", "\\_"),
        "LlmRun": str(len(df)),
        "LlmTypCert": f"{int(typ.certified.sum())}/{len(typ)}",
        "LlmAdaptCert": f"{int(cert_adapt.certified.sum())}/{len(cert_adapt)}",
        "LlmUncertStop": f"{int((uncert.stop_reason == 'agent_stop').sum())}/{len(uncert)}",
        "LlmUncertFalse": str(int(uncert.certified.sum())),
        "LlmInvalid": f"{df.invalid_actions.sum() / max(df.steps.sum(), 1) * 100:.1f}",
        "LlmTypRatio": f"{ratio.mean():.2f}" if len(ratio) else "n/a",
        "LlmUncertSteps": f"{uncert.steps.mean():.1f}" if len(uncert) else "n/a",
        "LlmAdaptCost": (f"{cert_adapt[cert_adapt.certified].cost_to_certify.mean():.1f}"
                         if cert_adapt.certified.any() else "none"),
    }
    out["range_llm_numbers.tex"] = "% Generated from data/llm_defender/*/summary.csv.\n" + "".join(
        "\\newcommand{\\" + k + "}{" + v + "}\n" for k, v in sorted(vals.items()))
    rows = []
    for (adv, eps, k), g in df.groupby(["adversary", "epsilon", "k"], sort=False):
        ok = g[g.certified]
        rows.append([adv, f"{eps:.2f}", str(k),
                     _gapcell(g.optimal_size.iloc[0], bool(g.optimal_computed.iloc[0]),
                              bool(g.certifiable.iloc[0])),
                     _cost(g.greedy_cost.iloc[0]),
                     f"{len(ok)}/{len(g)}",
                     f"{ok.cost_to_certify.mean():.1f}" if len(ok) else "--",
                     f"{int((g.stop_reason == 'agent_stop').sum())}/{len(g)}",
                     f"{g.invalid_actions.mean():.1f}"])
    out["table_range_llm_rows.tex"] = "% Generated from data/llm_defender/*/summary.csv.\n" + "".join(
        " & ".join(r) + " \\\\\n" for r in rows)
    return out


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
