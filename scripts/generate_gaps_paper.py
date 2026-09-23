#!/usr/bin/env python3
"""Generate the ATT&CK-gaps paper's numbers and tables from committed CSVs."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from grrc.provenance import verify_manifest

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/attack_history"
PAPER = ROOT / "docs/attack_gaps"


def _read(name):
    return pd.read_csv(DATA / name, dtype={"version": str})


def _pct(x, digits=1):
    return f"{100 * float(x):.{digits}f}"


def _ym(date):
    return str(date)[:7]


def content():
    verify_manifest(DATA / "attack_history_manifest.json")
    source = json.loads((DATA / "source_manifest.json").read_text())
    cov_all = _read("coverage_by_release.csv")
    cov = cov_all[cov_all.comparable].sort_values("release_date").reset_index(drop=True)
    tac = _read("coverage_by_tactic.csv")
    flo = _read("floor_by_release.csv").set_index("version")
    rep = _read("minimal_repair.csv")
    rlist = _read("repair_list_latest.csv")
    sens = _read("sensitivity.csv")
    ch = pd.read_csv(DATA / "floor_changes.csv", dtype={"version": str, "prev_version": str})
    par = _read("parameter_sensitivity.csv")

    first, last = cov.iloc[0], cov.iloc[-1]
    fv, lv = first.version, last.version
    sub = cov[cov.version == "7.2"].iloc[0]                    # parent series starts at v7
    min_share = cov.loc[cov.uncovered_share.idxmin()]
    tl = tac[tac.version == lv].copy()
    tl["share"] = tl.uncovered / tl.techniques
    worst_share = tl.loc[tl.share.idxmax()]
    worst_count = tl.loc[tl.uncovered.idxmax()]

    def repair(v, eps, k, e_new=0.2):
        r = rep[(rep.version == v) & (rep.epsilon == eps) & (rep.k == k) & (rep.e_new == e_new)]
        return r.iloc[0]

    hist = rep[(rep.e_new == 0.2) & (rep.epsilon == 0.10) & (rep.k == 1)]
    hist_max = hist.loc[hist.cost.idxmax()]
    r101, r051, r014, r011 = (repair(lv, 0.10, 1), repair(lv, 0.05, 1), repair(lv, 0.01, 4),
                              repair(lv, 0.01, 1))
    weak101, weak051 = repair(lv, 0.10, 1, 0.10), repair(lv, 0.05, 1, 0.10)
    ph = sens[(sens.version == lv) & (sens.variant == "placeholders_included")].iloc[0]
    split = sens[(sens.version == lv) & (sens.variant == "defense_evasion_split")].iloc[0]
    inh = sens[(sens.version == lv) & (sens.variant == "parent_inheritance")].iloc[0]
    inh_first = sens[(sens.version == fv) & (sens.variant == "parent_inheritance")].iloc[0]
    pre_sub = cov[cov.version == "6.3"].iloc[0]

    def par_row(base, eff):
        return par[(par.base == base) & (par.eff_low == eff)].iloc[0]

    def cost(x):
        return "infeasible" if int(x) < 0 else str(int(x))

    def yes(x):
        return "infeasible" if not bool(x.feasible) else str(int(x.cost))

    # The latest dip in the floor and the rise that followed it (rows are chronological).
    down = [i for i, r in ch.iterrows() if r.factor_after < r.factor_before]
    dip = ch.loc[down[-1]]
    rise = next(ch.loc[i] for i in range(down[-1] + 1, len(ch))
                if ch.loc[i].factor_after > ch.loc[i].factor_before)

    values = {
        "GapReleases": str(len(source["releases"])),
        "GapComparable": str(len(cov)),
        "GapFirstVersion": fv, "GapFirstDate": _ym(first.release_date),
        "GapLastVersion": lv, "GapLastDate": _ym(last.release_date),
        "GapFirstTech": str(int(first.kill_chain_techniques)),
        "GapLastTech": str(int(last.kill_chain_techniques)),
        "GapTechGrowthPct": f"{100 * (last.kill_chain_techniques / first.kill_chain_techniques - 1):.0f}",
        "GapFirstMit": str(int(first.real_mitigations)), "GapLastMit": str(int(last.real_mitigations)),
        "GapFirstUnc": str(int(first.uncovered)), "GapLastUnc": str(int(last.uncovered)),
        "GapUncGrowthPct": f"{100 * (last.uncovered / first.uncovered - 1):.0f}",
        "GapFirstShare": _pct(first.uncovered_share), "GapLastShare": _pct(last.uncovered_share),
        "GapMinShare": _pct(min_share.uncovered_share), "GapMinShareVersion": min_share.version,
        "GapFirstSingle": str(int(first.single_mitigation)),
        "GapLastSingle": str(int(last.single_mitigation)),
        "GapParentsUncSub": str(int(sub.parents_uncovered)),
        "GapParentsUncLast": str(int(last.parents_uncovered)),
        "GapFirstStages": str(int(first.gap_stages)), "GapLastStages": str(int(last.gap_stages)),
        "GapStages": str(int(len(tl))),
        "GapWorstShareStage": str(worst_share.stage), "GapWorstShareUnc": str(int(worst_share.uncovered)),
        "GapWorstShareTotal": str(int(worst_share.techniques)),
        "GapWorstSharePct": f"{100 * worst_share.share:.0f}",
        "GapWorstCountStage": str(worst_count.stage), "GapWorstCountUnc": str(int(worst_count.uncovered)),
        "GapFloorFirstKOne": _pct(flo.loc[fv, "catastrophic_floor_k1"]),
        "GapFloorLastKOne": _pct(flo.loc[lv, "catastrophic_floor_k1"]),
        "GapFloorLastKFour": _pct(flo.loc[lv, "catastrophic_floor_k4"]),
        "GapFloorRepairedLastKOne": _pct(flo.loc[lv, "repaired_catastrophic_floor_k1"]),
        "GapFloorRatio": f"{flo.loc[lv, 'catastrophic_floor_k1'] / flo.loc[lv, 'repaired_catastrophic_floor_k1']:.1f}",
        "GapRepTenOne": yes(r101), "GapRepTenOneStages": str(int(r101.repaired_stages)),
        "GapRepFiveOne": yes(r051), "GapRepFiveOneStages": str(int(r051.repaired_stages)),
        "GapRepOneFour": yes(r014), "GapRepOneOne": yes(r011),
        "GapRepHistFirst": str(int(hist[hist.version == fv].iloc[0].cost)),
        "GapRepHistMax": str(int(hist_max.cost)), "GapRepHistMaxVersion": hist_max.version,
        "GapRepWeakTenOne": yes(weak101), "GapRepWeakFiveOne": yes(weak051),
        "GapPlaceholderUnc": str(int(ph.uncovered)),
        "GapSplitStages": str(int(split.gap_stages)),
        "GapSplitFloorKOne": _pct(split.catastrophic_floor_k1),
        "GapFloorEvents": str(len(ch)),
        "GapDipVersion": dip.version, "GapDipStage": str(dip.stage),
        "GapDipTech": str(dip.binding_before), "GapDipTechName": str(dip.binding_before_name),
        "GapDipFloorBefore": _pct(flo.loc[dip.prev_version, "catastrophic_floor_k1"]),
        "GapDipFloor": _pct(flo.loc[dip.version, "catastrophic_floor_k1"]),
        "GapRiseVersion": rise.version, "GapRiseStage": str(rise.stage),
        "GapRiseTech": str(rise.binding_after), "GapRiseTechName": str(rise.binding_after_name),
        "GapRiseFloor": _pct(flo.loc[rise.version, "catastrophic_floor_k1"]),
        "GapPreSubShare": _pct(pre_sub.uncovered_share), "GapSubShare": _pct(sub.uncovered_share),
        "GapInhFirstUnc": str(int(inh_first.uncovered)), "GapInhUnc": str(int(inh.uncovered)),
        "GapInhGrowthPct": f"{100 * (inh.uncovered / inh_first.uncovered - 1):.0f}",
        "GapInhStages": str(int(inh.gap_stages)),
        "GapInhFloorFirst": _pct(inh_first.catastrophic_floor_k1),
        "GapInhFloor": _pct(inh.catastrophic_floor_k1),
        "GapInhFloorGrowth": f"{inh.catastrophic_floor_k1 / inh_first.catastrophic_floor_k1:.2f}",
        "GapInhRepTen": cost(inh.repair_10_k1), "GapInhRepFive": cost(inh.repair_05_k1),
        "GapParamMidFloor": _pct(par_row(0.7, 0.2).catastrophic_floor_k1),
        "GapParamLowFloor": _pct(par_row(0.5, 0.2).catastrophic_floor_k1, 2),
        "GapParamStrongFloor": _pct(par_row(0.9, 0.35).catastrophic_floor_k1),
        "GapParamStrongRep": cost(par_row(0.9, 0.35).repair_10_k1),
        "GapParamWeakFloor": _pct(par_row(0.9, 0.1).catastrophic_floor_k1),
        "GapParamWeakRep": cost(par_row(0.9, 0.1).repair_10_k1),
        "GapParamSubsetAll": "every" if bool(par.repair_10_k1_within_default.all()) else "not every",
        # The floor is b^12 times a coverage-only term, so its growth ratio is free of b.
        "GapFloorGrowth": f"{flo.loc[lv, 'clinical_floor'] / flo.loc[fv, 'clinical_floor']:.2f}",
    }
    generated = {"gaps_numbers.tex": "% Generated; do not edit. ATT&CK mitigation gaps.\n"
                 + "".join("\\newcommand{\\" + k + "}{" + v + "}\n" for k, v in sorted(values.items()))}

    rows = []
    for _, r in cov.iterrows():
        f = flo.loc[r.version]
        rows.append([r.version, _ym(r.release_date), str(int(r.kill_chain_techniques)),
                     str(int(r.real_mitigations)),
                     f"{int(r.uncovered)} ({_pct(r.uncovered_share)})",
                     str(int(r.single_mitigation)), str(int(r.gap_stages)),
                     _pct(f.catastrophic_floor_k1), yes(repair(r.version, 0.10, 1))])
    generated["table_gaps_release_rows.tex"] = "% Generated from coverage_by_release/floor/repair.\n" + "".join(
        " & ".join(r) + " \\\\\n" for r in rows)

    tf = tac[tac.version == fv].set_index("stage")
    rows = []
    for _, r in tl.iterrows():
        a = tf.loc[r.stage] if r.stage in tf.index else None
        rows.append([str(r.stage), "--" if a is None else f"{int(a.uncovered)}/{int(a.techniques)}",
                     f"{int(r.uncovered)}/{int(r.techniques)}", f"{100 * r.share:.0f}"])
    generated["table_gaps_tactic_rows.tex"] = "% Generated from coverage_by_tactic.csv.\n" + "".join(
        " & ".join(r) + " \\\\\n" for r in rows)

    rows = []
    for _, r in par.sort_values(["base", "eff_low"], ascending=[False, True]).iterrows():
        rows.append([f"{r.base:.1f}", f"{r.eff_low:.2f}", _pct(r.catastrophic_floor_k1, 2),
                     cost(r.repair_10_k1), cost(r.repair_05_k1)])
    generated["table_gaps_param_rows.tex"] = "% Generated from parameter_sensitivity.csv.\n" + "".join(
        " & ".join(r) + " \\\\\n" for r in rows)

    rows = []
    for _, r in ch.iterrows():
        rows.append([r.version, str(r.stage), f"{r.factor_before:.3f} $\\to$ {r.factor_after:.3f}",
                     f"{r.binding_before} {str(r.binding_before_name).replace('&', chr(92) + '&')}",
                     f"{r.binding_after} {str(r.binding_after_name).replace('&', chr(92) + '&')}"])
    generated["table_gaps_changes_rows.tex"] = "% Generated from floor_changes.csv.\n" + "".join(
        " & ".join(r) + " \\\\\n" for r in rows)

    rows = []
    for _, r in rlist[(rlist.epsilon == 0.10) & (rlist.k == 1)].iterrows():
        rows.append([r.technique, str(r["name"]).replace("&", "\\&"), str(r.stages)])
    generated["table_gaps_repair_rows.tex"] = "% Generated from repair_list_latest.csv (eps=0.10, k=1).\n" + "".join(
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
        print("ATT&CK-gaps paper values verified")
        return 0
    for name, value in generated.items():
        (PAPER / name).write_text(value, encoding="utf-8", newline="\n")
    print(f"wrote {len(generated)} generated files to {PAPER.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
