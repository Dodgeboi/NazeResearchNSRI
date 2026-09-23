#!/usr/bin/env python3
"""Generate the k-of-n theorem note's numbers/tables from committed CSVs."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from grrc.provenance import verify_manifest

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/kofn_theorem"
PAPER = ROOT / "docs/kofn_theorem"
WORD = {1: "One", 2: "Two", 3: "Three", 4: "Four"}   # macro names cannot contain digits


def content():
    verify_manifest(DATA / "kofn_theorem_manifest.json")
    params = json.loads((DATA / "kofn_theorem_manifest.json").read_text())["parameters"]
    bounds = pd.read_csv(DATA / "worked_bounds.csv")
    n = int(params["n"])

    empty = bounds[bounds.portfolio == "empty"].set_index("k")
    max_err = bounds["lp_abs_error"].max()

    def pct(x):
        return f"{100 * float(x):.1f}"

    values = {
        "KofnAttackVersion": str(params["attack_version"]),
        "KofnServices": str(n),
        "KofnMaxLpError": f"{max_err:.1e}",
        "KofnEmptyUnion": pct(empty.loc[1, "union_bound"]),
    }
    for k in range(1, n + 1):
        values[f"KofnEmptyClosedK{WORD[k]}"] = pct(empty.loc[k, "closed_form"])
        values[f"KofnEmptyMarkovK{WORD[k]}"] = pct(empty.loc[k, "markov_bound"])
    generated = {"kofn_numbers.tex": "% Generated; do not edit. Closed-form k-of-n theorem worked example.\n"
                 + "".join("\\newcommand{\\" + k + "}{" + v + "}\n" for k, v in sorted(values.items()))}

    rows = []
    for _, r in empty.reset_index().iterrows():
        rows.append([str(int(r.k)), f"{100*r.closed_form:.2f}", f"{100*r.lp_oracle:.2f}",
                     f"{100*r.union_bound:.2f}", f"{100*r.markov_bound:.2f}"])
    generated["table_kofn_bounds_rows.tex"] = "% Generated from worked_bounds.csv (empty portfolio).\n" + "".join(
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
        print("k-of-n theorem paper values verified")
        return 0
    for name, value in generated.items():
        (PAPER / name).write_text(value, encoding="utf-8", newline="\n")
    print(f"wrote {len(generated)} generated files to {PAPER.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
