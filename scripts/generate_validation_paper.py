#!/usr/bin/env python3
"""Generate the clinical-validation note's numbers/tables from committed CSVs."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from grrc.provenance import verify_manifest

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/clinical_validation"
PAPER = ROOT / "docs/clinical_validation"


def content():
    verify_manifest(DATA / "clinical_validation_manifest.json")
    params = json.loads((DATA / "clinical_validation_manifest.json").read_text())["parameters"]
    tau = int(params["primary_tau"])
    gof = pd.read_csv(DATA / "goodness_of_fit.csv")
    prof = pd.read_csv(DATA / "profiles.csv")
    resid = pd.read_csv(DATA / "residuals.csv")
    sev = pd.read_csv(DATA / "overlay_severity.csv").set_index("service")

    g = gof[gof.tau == tau].set_index("profile")
    obs = prof[prof.profile == "observed_cipher"].iloc[0]

    def pct(x):
        return f"{100 * float(x):.1f}"

    def pp(x):
        return f"{100 * float(x):+.1f}"

    ra = resid[resid.profile == "assumed"].set_index("service")
    values = {
        "ValAttackVersion": str(params["attack_version"]),
        "ValTau": str(tau),
        "ValHighTotal": str(int(g.loc["uniform", "high_severity_total"])),
        "ValModelledRecords": str(int(g.loc["uniform", "modelled_service_records"])),
        "ValObsEhr": pct(obs["ehr"]), "ValObsLab": pct(obs["laboratory"]),
        "ValObsPharma": pct(obs["pharmacy"]), "ValObsImg": pct(obs["imaging"]),
        "ValUniformTV": pct(g.loc["uniform", "total_variation"]),
        "ValAssumedTV": pct(g.loc["assumed", "total_variation"]),
        "ValUniformP": f"{g.loc['uniform', 'mc_pvalue']:.3f}",
        "ValAssumedP": f"{g.loc['assumed', 'mc_pvalue']:.3f}",
        "ValUniformGamma": f"{g.loc['uniform', 'reconciling_gamma']:.2f}",
        "ValAssumedGamma": f"{g.loc['assumed', 'reconciling_gamma']:.2f}",
        "ValAssumedEhrResidual": pp(ra.loc["ehr", "residual"]),
        "ValAssumedPharmaResidual": pp(ra.loc["pharmacy", "residual"]),
    }
    generated = {"validation_numbers.tex": "% Generated; do not edit. Held-out validation vs CIPHER.\n"
                 + "".join("\\newcommand{\\" + k + "}{" + v + "}\n" for k, v in sorted(values.items()))}

    rows = []
    for name, disp in [("uniform", "Uniform (ATT\\&CK null)"), ("assumed", "Assumed (model)")]:
        r = g.loc[name]
        rows.append([disp, f"{100*r.total_variation:.1f}", f"{r.mc_pvalue:.3f}",
                     f"{r.chi2_pvalue:.3f}", f"{r.reconciling_gamma:.2f}"])
    generated["table_validation_gof_rows.tex"] = "% Generated from goodness_of_fit.csv.\n" + "".join(
        " & ".join(r) + " \\\\\n" for r in rows)

    rows = []
    for svc in ["ehr", "laboratory", "pharmacy", "imaging"]:
        r = ra.loc[svc]
        rows.append([svc, f"{100*r.predicted:.1f}", f"{100*r.observed:.1f}", f"{100*r.residual:+.1f}",
                     f"{sev.loc[svc, 'mean_impact']:.2f}"])
    generated["table_validation_residual_rows.tex"] = "% Generated from residuals/overlay_severity.\n" + "".join(
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
        print("clinical-validation paper values verified")
        return 0
    for name, value in generated.items():
        (PAPER / name).write_text(value, encoding="utf-8", newline="\n")
    print(f"wrote {len(generated)} generated files to {PAPER.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
