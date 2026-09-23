#!/usr/bin/env python3
"""Generate the CIPHER-inference note's numbers and tables from committed CSVs.

Verifies the manifest first; generated-only macros and rows. --check re-derives.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from grrc.provenance import verify_manifest

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/cipher_inference"
PAPER = ROOT / "docs/cipher_inference"


def content():
    verify_manifest(DATA / "cipher_inference_manifest.json")
    params = json.loads((DATA / "cipher_inference_manifest.json").read_text())["parameters"]
    observed = pd.read_csv(DATA / "observed_shares.csv").set_index("service")
    gamma = pd.read_csv(DATA / "gamma_bounds.csv")
    cmp = pd.read_csv(DATA / "certificate_comparison.csv").set_index("degradation")
    prof = pd.read_csv(DATA / "time_profile.csv").set_index("time_point")["fraction"]

    def pct(x):
        return f"{100 * float(x):.1f}"

    values = {
        "CipherRecords": str(int(params["records"])),
        "CipherHighTotal": str(int(params["high_severity_total"])),
        "CipherTau": str(int(params["tau"])),
        "CipherGamma": str(int(params["integration_gamma"])),
        "CipherPharmaShare": pct(observed.loc["pharmacy", "observed_share"]),
        "CipherLabShare": pct(observed.loc["laboratory", "observed_share"]),
        "CipherEhrShare": pct(observed.loc["ehr", "observed_share"]),
        "CipherImgShare": pct(observed.loc["imaging", "observed_share"]),
        "CipherResidualShare": pct(observed.loc["unmodelled_residual", "observed_share"]),
        "CipherWeekTwoPlus": pct(prof.get("Week 2", 0) + prof.get("First Month", 0)),
        "CipherEmptyAssumedPct": pct(cmp.loc["assumed", "empty_union_outage"]),
        "CipherEmptyRealPct": pct(cmp.loc["cipher_gamma1", "empty_union_outage"]),
        "CipherCoreAssumedPct": pct(cmp.loc["assumed", "hospital_core_worst_union"]),
        "CipherCoreRealPct": pct(cmp.loc["cipher_gamma1", "hospital_core_worst_union"]),
        "CipherCoreAssumedGuar": "yes" if bool(cmp.loc["assumed", "hospital_core_guaranteed_05"]) else "no",
        "CipherCoreRealGuar": "yes" if bool(cmp.loc["cipher_gamma1", "hospital_core_guaranteed_05"]) else "no",
    }
    generated = {"cipher_numbers.tex": "% Generated; do not edit. Real corpus, partial identification.\n"
                 + "".join("\\newcommand{\\" + k + "}{" + v + "}\n" for k, v in sorted(values.items()))}

    rows = []
    at1 = gamma[gamma.gamma == 1.0].set_index("service")
    for svc in ["ehr", "laboratory", "pharmacy", "imaging"]:
        rows.append([svc, str(int(observed.loc[svc, "high_severity_records"])),
                     f"{100*observed.loc[svc, 'observed_share']:.1f}",
                     f"{100*at1.loc[svc, 'share_low']:.1f}--{100*at1.loc[svc, 'share_high']:.1f}"])
    generated["table_cipher_shares_rows.tex"] = "% Generated from observed_shares/gamma_bounds.\n" + "".join(
        " & ".join(r) + " \\\\\n" for r in rows)

    rows = []
    for label, disp in [("assumed", "Assumed"), ("cipher_gamma1", "CIPHER (gamma=1)")]:
        rows.append([disp, f"{100*cmp.loc[label,'empty_union_outage']:.1f}",
                     f"{100*cmp.loc[label,'hospital_core_worst_union']:.1f}",
                     "yes" if cmp.loc[label, "hospital_core_guaranteed_05"] else "no"])
    generated["table_cipher_compare_rows.tex"] = "% Generated from certificate_comparison.\n" + "".join(
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
        print("cipher-inference paper values verified")
        return 0
    for name, value in generated.items():
        (PAPER / name).write_text(value, encoding="utf-8", newline="\n")
    print(f"wrote {len(generated)} generated files to {PAPER.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
