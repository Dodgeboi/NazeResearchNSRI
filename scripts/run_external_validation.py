#!/usr/bin/env python3
"""Compare model outputs against the frozen external-validation registry.

Reads ``study/external_validation_benchmarks.json``, whose targets,
discrepancy measures and pass criteria were fixed before any comparison was
run, and reports the verdict for every benchmark including the ones the model
cannot address.

The design rule this script enforces is that **failures are results**. It
does not stop at the first failure, it does not omit benchmarks the model
does badly on, and it exits zero even when benchmarks fail — because a failed
external check is a finding to report, not a build error. It exits non-zero
only when the registry itself is inconsistent, for example when a benchmark
marked ``scored`` has no way to be computed.

Two benchmarks are numerically scored. Every other one is recorded as
``not_addressable`` or ``not_scored`` with the structural reason, because the
model has no output of that construct. That ratio — two scorable benchmarks
out of nine — is itself the headline validation result, and the manuscript
reports it as such rather than burying it.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from grrc.config import load_config
from grrc.endpoints import max_streak_column
from grrc.enums import CLINICAL_SERVICES
from grrc.provenance import build_manifest, write_manifest

REGISTRY = Path("study/external_validation_benchmarks.json")


def clinical_outage_streaks(raw: pd.DataFrame) -> pd.Series:
    """Longest clinical-service outage per trial, in steps."""
    columns = [max_streak_column(s) for s in CLINICAL_SERVICES]
    return raw[columns].max(axis=1)


def score_crowdstrike(raw: pd.DataFrame, cfg, target: dict) -> dict:
    """Short-duration technical outage: median hours and six-hour share."""
    step_hours = cfg.simulation.step_minutes / 60.0
    longest = clinical_outage_streaks(raw) * step_hours
    disrupted = longest[longest > 0]
    if disrupted.empty:
        return {"computable": False,
                "note": "no trial produced any clinical service outage"}
    median = float(disrupted.median())
    within_six = float((disrupted <= 6.0).mean())
    lower, upper = target["iqr_hours"]
    median_in_range = bool(lower <= median <= upper)
    return {
        "computable": True,
        "computed_verdict": "pass" if median_in_range else "fail",
        "model_median_outage_hours": round(median, 2),
        "target_median_hours": target["median_downtime_hours"],
        "target_iqr_hours": target["iqr_hours"],
        "median_within_target_iqr": bool(lower <= median <= upper),
        "model_share_within_six_hours": round(within_six, 4),
        "target_share_within_six_hours":
            target["share_recovered_within_six_hours"],
        "share_absolute_error": round(
            abs(within_six - target["share_recovered_within_six_hours"]), 4),
        "trials_with_any_clinical_outage": int(disrupted.size),
        "trials_total": int(len(raw)),
        "interpretation": (
            "Read alongside recovery_trajectory_three_weeks, this is a "
            "two-sided failure and the more informative for it. Against the "
            "one directly observed large-scale technical outage the model is "
            "far too SLOW: its median clinical outage is several times the "
            "observed median and its six-hour recovery share is well below "
            "the observed one. Against the ransomware incident record the "
            "same restoration engine is far too FAST, finishing within a "
            "72-hour horizon where the public distribution has most of its "
            "mass beyond a week. The model's recovery behaviour is therefore "
            "anchored to neither reference, and its non-recovery objective "
            "should be read as a within-model ordering device rather than a "
            "duration estimate."),
    }


def score_contained(raw: pd.DataFrame, cfg, target: dict) -> dict:
    """Share of trials with no qualifying sustained clinical outage."""
    threshold = cfg.simulation.sustained_outage_service_steps
    longest = clinical_outage_streaks(raw)
    by_profile = {}
    for profile, group in raw.groupby("profile"):
        group_longest = clinical_outage_streaks(group)
        by_profile[str(profile)] = round(
            float((group_longest <= threshold).mean()), 4)
    overall = float((longest <= threshold).mean())
    spread = [min(by_profile.values()), max(by_profile.values())]
    brackets = spread[0] <= target["share_stopped_before_encryption"] <= spread[1]
    return {
        "computable": True,
        "computed_verdict": "consistent" if brackets else "inconsistent",
        "profile_spread": spread,
        "model_share_contained_overall": round(overall, 4),
        "model_share_contained_by_profile": by_profile,
        "target_share": target["share_stopped_before_encryption"],
        "absolute_error": round(
            abs(overall - target["share_stopped_before_encryption"]), 4),
        "note": "The model's spread across profiles is far wider than a "
                "single survey figure, because the profiles are declared "
                "scenarios rather than a sample of hospitals. Only gross "
                "inconsistency would be informative here.",
    }


SCORERS = {
    "crowdstrike_short_outage": score_crowdstrike,
    "attack_stopped_before_encryption": score_contained,
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--raw",
        default="data/multiobjective/confirmatory/"
                "multiobjective_confirmatory_results.csv")
    parser.add_argument("--config",
                        default="configs/multiobjective_portfolio.yaml")
    parser.add_argument(
        "--output",
        default="data/multiobjective/confirmatory/external_validation.json")
    args = parser.parse_args()

    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    cfg = load_config(args.config)
    raw = pd.read_csv(args.raw)

    results = []
    inconsistent: list[str] = []
    for benchmark in registry["benchmarks"]:
        entry = {
            "id": benchmark["id"],
            "name": benchmark["name"],
            "used_for": benchmark["used_for"],
            "verdict": benchmark["verdict"],
            "population": benchmark["population"],
        }
        if benchmark["verdict"] == "scored":
            scorer = SCORERS.get(benchmark["id"])
            if scorer is None:
                inconsistent.append(
                    f"{benchmark['id']} is marked scored but has no scorer")
                entry["scoring"] = {"computable": False}
            else:
                entry["scoring"] = scorer(raw, cfg, benchmark["target"])
            entry["scoring_note"] = benchmark.get("scoring_note", "")
        else:
            entry["structural_reason"] = benchmark.get("structural_reason", "")
            entry["observed_model_behaviour"] = benchmark.get(
                "observed_model_behaviour", "")
        results.append(entry)

    counts: dict[str, int] = {}
    for entry in results:
        counts[entry["verdict"]] = counts.get(entry["verdict"], 0) + 1
    scored_verdicts = {
        entry["id"]: entry["scoring"].get("computed_verdict")
        for entry in results
        if entry.get("scoring", {}).get("computed_verdict")}

    report = {
        "registry_version": registry["registry_version"],
        "registry_frozen_at": registry["frozen_at"],
        "raw_results": args.raw,
        "benchmarks_total": len(results),
        "verdict_counts": counts,
        "computed_verdicts_for_scored_benchmarks": scored_verdicts,
        "headline": (
            f"Of {len(results)} frozen external benchmarks, "
            f"{counts.get('scored', 0)} could be scored numerically. The rest "
            "are unaddressable or unscoreable because the model has no output "
            "of that construct: it runs one facility, over a 72-hour horizon, "
            "with binary per-step service availability. That ratio is the "
            "validation result, and it bounds what any conclusion in this "
            "study can claim. Of the benchmarks that could be scored or "
            "compared at all, none passes cleanly: the model's recovery "
            "behaviour is anchored to neither the technical-outage reference "
            "nor the ransomware incident record, and it assigns probability "
            "zero to the quarter of observed events that affected more than "
            "one hospital."),
        "benchmarks": results,
    }

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")

    manifest = build_manifest(
        run_id="external-validation", stage="validation",
        description="Comparison against the frozen external benchmark "
                    "registry. Failures are reported, not corrected.",
        inputs=[REGISTRY, args.config, args.raw],
        outputs=[out],
        parameters={"verdict_counts": counts})
    write_manifest(manifest, out.parent / "external_validation_manifest.json")

    print(report["headline"])
    print()
    for entry in results:
        print(f"{entry['verdict']:16s} {entry['id']}")
        scoring = entry.get("scoring")
        if scoring and scoring.get("computable"):
            verdict = scoring.get("computed_verdict")
            if verdict:
                print(f"                   COMPUTED VERDICT: {verdict}")
            for key, value in scoring.items():
                if key == "computable":
                    continue
                print(f"                   {key}: {value}")
    print(f"\nwrote {out}")

    if inconsistent:
        print("\nREGISTRY INCONSISTENT", *inconsistent, sep="\n  ")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
