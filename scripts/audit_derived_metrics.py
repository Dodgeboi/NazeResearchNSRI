"""Independently recompute derived ratios from archived raw CSV fields.

This audit intentionally avoids the simulator's metric formulas. It verifies
that the two historical ratios that can be reconstructed from every archived
row agree to CSV precision. New runs also contain terminal availability flags,
which make the formerly ambiguous terminal-service ratio row-auditable.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd


CLINICAL = ("ehr", "laboratory", "pharmacy", "imaging")
WEIGHT_VARIANTS = {
    "reference": {"ehr": 1.0, "laboratory": 0.8,
                  "pharmacy": 0.9, "imaging": 0.7},
    "equal": {name: 1.0 for name in CLINICAL},
    "clinical": {"ehr": 1.2, "laboratory": 1.0,
                 "pharmacy": 1.1, "imaging": 1.0},
    # The recovery-priority variant changes identity and backup weights only.
    "recovery": {"ehr": 1.0, "laboratory": 0.8,
                 "pharmacy": 0.9, "imaging": 0.7},
}
SERVICES = ("ehr", "laboratory", "pharmacy", "imaging", "scheduling",
            "identity", "backup_recovery")


def _clinical_expected(df: pd.DataFrame) -> np.ndarray:
    expected = np.zeros(len(df), dtype=float)
    variants = (df["service_weight_variant"].fillna("reference")
                if "service_weight_variant" in df
                else pd.Series("reference", index=df.index))
    horizons = (df["horizon_steps"] if "horizon_steps" in df
                else df["horizon_steps_variant"]
                if "horizon_steps_variant" in df
                else pd.Series(192.0, index=df.index))
    for variant in variants.unique():
        key = str(variant)
        weights = WEIGHT_VARIANTS.get(key)
        if weights is None:
            raise ValueError(f"unknown service-weight variant: {key}")
        mask = variants == variant
        numerator = sum(
            weights[name] * df.loc[mask, f"{name}_downtime_steps"]
            for name in CLINICAL)
        expected[mask.to_numpy()] = (
            numerator / (sum(weights.values()) * horizons.loc[mask]))
    return expected


def audit_file(path: Path, tolerance: float) -> dict[str, object]:
    df = pd.read_csv(path)
    required = {"total_compromised", "n_nodes", "pct_compromised",
                "pct_clinical_capacity_lost"}
    if not required.issubset(df.columns):
        return {"file": path.name, "rows": len(df), "status": "skipped",
                "reason": "required historical metric columns absent"}

    compromise_expected = df["total_compromised"] / df["n_nodes"]
    compromise_diff = np.abs(
        df["pct_compromised"].to_numpy() - compromise_expected.to_numpy())
    clinical_expected = _clinical_expected(df)
    clinical_diff = np.abs(
        df["pct_clinical_capacity_lost"].to_numpy() - clinical_expected)

    final_cols = [f"{name}_available_final" for name in SERVICES]
    if set(final_cols).issubset(df.columns):
        final_expected = df[final_cols].mean(axis=1)
        terminal_diff = np.abs(
            df["pct_services_restored"].to_numpy()
            - final_expected.to_numpy())
        terminal_max: float | str = float(terminal_diff.max(initial=0.0))
        terminal_status = "row-recomputed"
    else:
        terminal_max = ""
        terminal_status = "legacy row lacks final-service flags"

    maximum = max(float(compromise_diff.max(initial=0.0)),
                  float(clinical_diff.max(initial=0.0)),
                  float(terminal_max) if terminal_max != "" else 0.0)
    return {
        "file": path.name,
        "rows": len(df),
        "max_abs_diff_ever_compromised_fraction":
            float(compromise_diff.max(initial=0.0)),
        "max_abs_diff_weighted_clinical_unavailability":
            float(clinical_diff.max(initial=0.0)),
        "max_abs_diff_final_service_availability": terminal_max,
        "terminal_metric_status": terminal_status,
        "status": "pass" if maximum <= tolerance else "fail",
        "tolerance": tolerance,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-dir", type=Path, default=Path("data/raw"))
    parser.add_argument("--output", type=Path,
                        default=Path("data/processed/derived_metric_audit.csv"))
    parser.add_argument("--tolerance", type=float, default=1e-9)
    args = parser.parse_args()

    rows = [audit_file(path, args.tolerance)
            for path in sorted(args.raw_dir.glob("*.csv"))]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(args.output, index=False, float_format="%.12g")
    failures = [row for row in rows if row["status"] == "fail"]
    print(f"audited {len(rows)} files; failures={len(failures)}")
    print(f"wrote {args.output}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
