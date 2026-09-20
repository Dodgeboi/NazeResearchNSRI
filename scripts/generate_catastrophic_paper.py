#!/usr/bin/env python3
"""Generate the catastrophic-certificate note's numbers/tables from committed CSVs."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from grrc.provenance import verify_manifest

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/catastrophic_certificate"
PAPER = ROOT / "docs/catastrophic_certificate"


def content():
    verify_manifest(DATA / "catastrophic_certificate_manifest.json")
    params = json.loads((DATA / "catastrophic_certificate_manifest.json").read_text())["parameters"]
    summ = pd.read_csv(DATA / "catastrophic_summary.csv")
    named = pd.read_csv(DATA / "catastrophic_named.csv")

    def guard(label, k):
        row = summ[(summ.degradation == label) & (summ.k == k)].iloc[0]
        return int(row.min_guaranteed_size)

    def empty(label, k):
        return summ[(summ.degradation == label) & (summ.k == k)].iloc[0].empty_worst

    values = {
        "CatAttackVersion": str(params["attack_version"]),
        "CatEpsilon": str(int(round(params["epsilon"] * 100))),
        "CatEmptyKOnePct": f"{100*empty('assumed',1):.1f}",
        "CatEmptyKFourPct": f"{100*empty('assumed',4):.1f}",
    }
    word = {1: "One", 2: "Two", 3: "Three", 4: "Four"}  # macro names cannot contain digits
    for k in (1, 2, 3, 4):
        values[f"CatMinGuardK{word[k]}"] = str(guard("assumed", k))
        values[f"CatMinGuardK{word[k]}Cipher"] = str(guard("cipher_gamma1", k))
    core = named[(named.degradation == "assumed") & (named.portfolio == "hospital_core")].iloc[0]
    for k in (1, 2, 3, 4):
        values[f"CatCoreK{word[k]}Guar"] = "yes" if bool(core[f"guaranteed_k{k}"]) else "no"
    generated = {"catastrophic_numbers.tex": "% Generated; do not edit. Sharp k-of-n, interval-robust.\n"
                 + "".join("\\newcommand{\\" + k + "}{" + v + "}\n" for k, v in sorted(values.items()))}

    rows = []
    for k in (1, 2, 3, 4):
        rows.append([str(k), f"{100*empty('assumed',k):.1f}", str(guard("assumed", k)),
                     f"{100*empty('cipher_gamma1',k):.1f}", str(guard("cipher_gamma1", k))])
    generated["table_catastrophic_summary_rows.tex"] = "% Generated from catastrophic_summary.csv.\n" + "".join(
        " & ".join(r) + " \\\\\n" for r in rows)

    rows = []
    for _, r in named[named.degradation == "assumed"].iterrows():
        rows.append([r.portfolio.replace("_", " "), str(int(r["size"]))]
                    + ["yes" if r[f"guaranteed_k{k}"] else "no" for k in (1, 2, 3, 4)])
    generated["table_catastrophic_named_rows.tex"] = "% Generated from catastrophic_named.csv.\n" + "".join(
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
        print("catastrophic-certificate paper values verified")
        return 0
    for name, value in generated.items():
        (PAPER / name).write_text(value, encoding="utf-8", newline="\n")
    print(f"wrote {len(generated)} generated files to {PAPER.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
