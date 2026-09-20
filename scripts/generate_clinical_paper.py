#!/usr/bin/env python3
"""Generate the clinical-certificate note's numbers and tables from committed CSVs.

Verifies the manifest first; emits generated-only macros and table rows. --check
re-derives without writing.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from grrc.provenance import verify_manifest

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/clinical_certificate"
PAPER = ROOT / "docs/clinical_certificate"
FRONTIER_SHOWN = 8


def content():
    verify_manifest(DATA / "clinical_certificate_manifest.json")
    params = json.loads((DATA / "clinical_certificate_manifest.json").read_text())["parameters"]
    frontier = pd.read_csv(DATA / "clinical_frontier.csv")
    named = pd.read_csv(DATA / "clinical_named.csv").set_index("portfolio")
    summary = pd.read_csv(DATA / "clinical_summary.csv").set_index("epsilon")
    sens = pd.read_csv(DATA / "clinical_sensitivity.csv").set_index("prior")

    def pct(x):
        return f"{100 * float(x):.1f}"

    values = {
        "ClinAttackVersion": str(params["attack_version"]),
        "ClinServices": str(len(params["services"])),
        "ClinEmptyUnionPct": pct(summary["empty_union_outage"].iloc[0]),
        "ClinMinGuardTen": str(int(summary.loc[0.10, "min_guaranteed_size"])),
        "ClinMinGuardFive": str(int(summary.loc[0.05, "min_guaranteed_size"])),
        "ClinMinGuardOne": str(int(summary.loc[0.01, "min_guaranteed_size"])),
        "ClinNamedGuardFive": str(int(summary.loc[0.05, "named_guaranteed"])),
        "ClinIdentityUnionPct": pct(named.loc["identity", "worst_union"]),
        "ClinCoreUnionPct": pct(named.loc["hospital_core", "worst_union"]),
        "ClinBackupUnionPct": pct(named.loc["backup", "worst_union"]),
        "ClinMinGuardNarrow": str(int(sens.loc["narrow", "min_guaranteed_size_at_05"])),
        "ClinMinGuardWide": str(int(sens.loc["wide", "min_guaranteed_size_at_05"])),
    }
    generated = {"clinical_numbers.tex": "% Generated; do not edit. Interval-robust, within-model.\n"
                 + "".join("\\newcommand{\\" + k + "}{" + v + "}\n" for k, v in sorted(values.items()))}

    rows = []
    for r in frontier.head(FRONTIER_SHOWN).itertuples():
        rows.append([str(r.size), r.added, r.added_name[:26], f"{100*r.worst_union:.1f}"])
    generated["table_clinical_frontier_rows.tex"] = "% Generated from clinical_frontier.csv.\n" + "".join(
        " & ".join(row) + " \\\\\n" for row in rows)

    rows = []
    for name, r in named.iterrows():
        rows.append([name.replace("_", " "), str(int(r["size"])), f"{100*r.worst_union:.1f}",
                     "yes" if r.guaranteed_10 else "no", "yes" if r.guaranteed_05 else "no"])
    generated["table_clinical_named_rows.tex"] = "% Generated from clinical_named.csv.\n" + "".join(
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
        print("clinical-certificate paper values verified")
        return 0
    for name, value in generated.items():
        (PAPER / name).write_text(value, encoding="utf-8", newline="\n")
    print(f"wrote {len(generated)} generated files to {PAPER.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
