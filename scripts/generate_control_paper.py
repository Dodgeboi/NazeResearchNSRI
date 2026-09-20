#!/usr/bin/env python3
"""Generate the control-certificate note's numbers and tables from committed CSVs.

Verifies the analysis manifest first, then emits generated-only LaTeX macros and
table rows. No result number is hand-typed; --check re-derives without writing.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from grrc.provenance import verify_manifest

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/attack_certificate"
PAPER = ROOT / "docs/control_certificate"
FRONTIER_SHOWN = 8


def content():
    verify_manifest(DATA / "control_certificate_manifest.json")
    params = json.loads((DATA / "control_certificate_manifest.json").read_text())["parameters"]
    frontier = pd.read_csv(DATA / "greedy_frontier.csv")
    named = pd.read_csv(DATA / "named_portfolios.csv")
    summary = pd.read_csv(DATA / "certificate_summary.csv").set_index("epsilon")
    sens = pd.read_csv(DATA / "prior_sensitivity.csv").set_index("prior")

    def pct(x):
        return f"{100 * float(x):.1f}"

    values = {
        "CertAttackVersion": str(params["attack_version"]),
        "CertTechniques": str(int(params["n_techniques"])),
        "CertMitigations": str(int(params["n_mitigations"])),
        "CertEmptyWorstPct": pct(summary["empty_worst_reachability"].iloc[0]),
        "CertMinGuardTen": str(int(summary.loc[0.10, "min_guaranteed_portfolio_size"])),
        "CertMinGuardFive": str(int(summary.loc[0.05, "min_guaranteed_portfolio_size"])),
        "CertMinGuardOne": str(int(summary.loc[0.01, "min_guaranteed_portfolio_size"])),
        "CertNamedGuardFive": str(int(summary.loc[0.05, "named_guaranteed"])),
        "CertNamedTotal": str(int(summary.loc[0.05, "named_total"])),
        "CertIdentityWorstPct": pct(named.set_index("portfolio").loc["identity", "worst_reachability"]),
        "CertCoreWorstPct": pct(named.set_index("portfolio").loc["hospital_core", "worst_reachability"]),
        "CertBackupWorstPct": pct(named.set_index("portfolio").loc["backup", "worst_reachability"]),
        "CertMinGuardNarrow": str(int(sens.loc["narrow", "min_guaranteed_size_at_05"])),
        "CertMinGuardWide": str(int(sens.loc["wide", "min_guaranteed_size_at_05"])),
        "CertWideEmptyPct": pct(sens.loc["wide", "empty_worst_reachability"]),
    }
    generated = {"control_numbers.tex": "% Generated; do not edit. Within-model, interval-robust.\n"
                 + "".join("\\newcommand{\\" + k + "}{" + v + "}\n" for k, v in sorted(values.items()))}

    rows = []
    for r in frontier.head(FRONTIER_SHOWN).itertuples():
        rows.append([str(r.size), r.added, r.added_name[:30], f"{100*r.worst_reachability:.1f}"])
    generated["table_control_frontier_rows.tex"] = "% Generated from greedy_frontier.csv.\n" + "".join(
        " & ".join(row) + " \\\\\n" for row in rows)

    rows = []
    for r in named.itertuples():
        rows.append([r.portfolio.replace("_", " "), str(r.size), f"{100*r.worst_reachability:.1f}",
                     "yes" if r.guaranteed_10 else "no", "yes" if r.guaranteed_05 else "no"])
    generated["table_control_named_rows.tex"] = "% Generated from named_portfolios.csv.\n" + "".join(
        " & ".join(row) + " \\\\\n" for row in rows)
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
        print("control-certificate paper values verified")
        return 0
    for name, value in generated.items():
        (PAPER / name).write_text(value, encoding="utf-8", newline="\n")
    print(f"wrote {len(generated)} generated files to {PAPER.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
