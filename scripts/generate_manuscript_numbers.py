#!/usr/bin/env python3
"""Generate every number the manuscript quotes, as LaTeX macros.

The handoff requires that each numeric statement be generated from, or
checked against, a machine-readable results table, and that tables and
figures contain no manually transcribed values where generation is
practical. This script is the generation half; ``audit_manuscript_claims.py``
is the checking half.

It writes ``docs/manuscript/generated_numbers.tex`` containing one
``\\newcommand`` per reported quantity, sourced directly from the committed
result tables. The manuscript then contains no hand-typed result number at
all: if a run is repeated and a value moves, the manuscript moves with it,
and a value that no longer exists becomes a LaTeX compile error rather than
a stale sentence.

Macro naming: ``\\Num<Section><Quantity>``, alphabetic only, because LaTeX
command names cannot contain digits or underscores.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from grrc.config import load_config
from grrc.endpoints import SUSTAINED_OUTAGE_K_LADDER
from grrc.provenance import build_manifest, load_frozen_protocol, write_manifest

DISCOVERY = Path("data/multiobjective/discovery")
CONFIRM = Path("data/multiobjective/confirmatory")

#: LaTeX cannot use digits in command names, so profile keys are spelled out.
PROFILE_MACRO = {
    "resource_constrained": "ResourceConstrained",
    "intermediate_capacity": "Intermediate",
    "high_capacity": "HighCapacity",
}
K_WORD = {1: "One", 2: "Two", 3: "Three", 4: "Four"}

#: Filled from the config in main(); module-level so add_stage can see it.
_BUDGETS: dict[str, float] = {}


class Macros:
    """Collect macros, refusing duplicates so a typo cannot shadow a value."""

    def __init__(self) -> None:
        self._values: dict[str, str] = {}

    def add(self, name: str, value: object, fmt: str = "{}") -> None:
        if not name.isalpha():
            raise ValueError(f"macro name must be alphabetic: {name!r}")
        rendered = fmt.format(value)
        if name in self._values and self._values[name] != rendered:
            raise ValueError(
                f"macro {name} defined twice with different values: "
                f"{self._values[name]!r} then {rendered!r}")
        self._values[name] = rendered

    def integer(self, name: str, value: float) -> None:
        self.add(name, f"{int(round(value)):,}")

    def one_dp(self, name: str, value: float) -> None:
        self.add(name, f"{float(value):.1f}")

    def percent(self, name: str, value: float) -> None:
        """A proportion in [0,1] rendered as a percentage without the sign.

        The percent sign stays in the manuscript so the macro can also be
        used inside a table cell that formats it differently.
        """
        self.add(name, f"{100.0 * float(value):.1f}")

    def render(self) -> str:
        lines = [
            "% GENERATED FILE - DO NOT EDIT.",
            "% Written by scripts/generate_manuscript_numbers.py from the",
            "% committed result tables. Every number the manuscript quotes is",
            "% defined here, so no result value is hand-typed anywhere in",
            "% main.tex. Re-run the script after any new analysis; a value",
            "% that ceases to exist becomes a compile error, not a stale",
            "% sentence.",
            "",
        ]
        for name in sorted(self._values):
            lines.append(f"\\newcommand{{\\{name}}}{{{self._values[name]}}}")
        return "\n".join(lines) + "\n"

    def __len__(self) -> int:
        return len(self._values)


def add_stage(macros: Macros, prefix: str, directory: Path, cfg) -> list[Path]:
    """Add every macro for one analysed stage. Returns the files consumed."""
    summary = pd.read_csv(directory / "portfolio_objective_summary.csv")
    frontier = pd.read_csv(directory / "portfolio_pareto_frontier.csv")
    stability = pd.read_csv(directory / "portfolio_pareto_stability.csv")
    resolution = pd.read_csv(directory / "portfolio_frontier_resolution.csv")
    errors = pd.read_csv(directory / "portfolio_monte_carlo_error.csv")
    benchmarks = pd.read_csv(directory / "portfolio_benchmark_comparison.csv")
    consumed = [directory / name for name in (
        "portfolio_objective_summary.csv", "portfolio_pareto_frontier.csv",
        "portfolio_pareto_stability.csv", "portfolio_frontier_resolution.csv",
        "portfolio_monte_carlo_error.csv",
        "portfolio_benchmark_comparison.csv")]

    macros.integer(f"{prefix}Executions",
                   (summary["n_scenarios"] * 1).sum())
    macros.integer(f"{prefix}Candidates", len(summary))
    macros.integer(f"{prefix}NonDominated",
                   frontier["pareto_efficient"].sum())

    for profile, group in frontier.groupby("profile"):
        tag = PROFILE_MACRO[profile]
        macros.integer(f"{prefix}{tag}Candidates", len(group))
        macros.integer(f"{prefix}{tag}NonDominated",
                       group["pareto_efficient"].sum())
        macros.integer(f"{prefix}{tag}Scenarios",
                       group["n_scenarios"].iloc[0])

    for profile, group in summary.groupby("profile"):
        tag = PROFILE_MACRO[profile]
        macros.one_dp(f"{prefix}{tag}MeanLossMin", group["mean_hours_lost"].min())
        macros.one_dp(f"{prefix}{tag}MeanLossMax", group["mean_hours_lost"].max())
        for k in SUSTAINED_OUTAGE_K_LADDER:
            column = f"sustained_outage_probability_k{k}"
            if column in group:
                macros.percent(f"{prefix}{tag}OutageK{K_WORD[k]}Mean",
                               group[column].mean())
                macros.percent(f"{prefix}{tag}OutageK{K_WORD[k]}Max",
                               group[column].max())

    for _, row in resolution.iterrows():
        tag = PROFILE_MACRO[row["profile"]]
        macros.integer(f"{prefix}{tag}CandidatePairs", row["candidate_pairs"])
        macros.integer(f"{prefix}{tag}IndistinguishablePairs",
                       row["indistinguishable_pairs"])
        macros.percent(f"{prefix}{tag}IndistinguishableShare",
                       row["indistinguishable_fraction"])

    for profile, group in stability.groupby("profile"):
        tag = PROFILE_MACRO[profile]
        macros.integer(f"{prefix}{tag}StableAtEighty",
                       (group["pareto_inclusion_probability"] >= 0.80).sum())

    flat = benchmarks[benchmarks["benchmark_strategy"] == "flat_reference"]
    for _, row in flat.iterrows():
        tag = PROFILE_MACRO[row["profile"]]
        macros.one_dp(f"{prefix}{tag}FlatMeanLoss", row["mean_hours_lost"])
    maximum = benchmarks[benchmarks["benchmark_strategy"]
                         == "maximum_control_stack"]
    for _, row in maximum.iterrows():
        tag = PROFILE_MACRO[row["profile"]]
        macros.one_dp(f"{prefix}{tag}MaxStackMeanLoss", row["mean_hours_lost"])
        macros.integer(f"{prefix}{tag}MaxStackCost",
                       row["implementation_cost_points"])

    worst_se = errors["mean_hours_lost_se"].max()
    macros.one_dp(f"{prefix}WorstMeanLossStandardError", worst_se)
    for profile, group in errors.groupby("profile"):
        tag = PROFILE_MACRO[profile]
        macros.one_dp(f"{prefix}{tag}WorstMeanLossStandardError",
                      group["mean_hours_lost_se"].max())

    # The profile's own untouched posture: the single zero-cost candidate.
    for profile, group in summary.groupby("profile"):
        tag = PROFILE_MACRO[profile]
        free = group[group["implementation_cost_points"] == 0]
        if len(free) == 1:
            macros.one_dp(f"{prefix}{tag}FreeBaselineMeanLoss",
                          free["mean_hours_lost"].iloc[0])
            # The whole purchasable improvement available in this profile.
            macros.one_dp(
                f"{prefix}{tag}MaxPurchasableImprovement",
                free["mean_hours_lost"].iloc[0] - group["mean_hours_lost"].min())

    # Best affordable candidate under the declared budget, per profile.
    for profile, group in summary.groupby("profile"):
        tag = PROFILE_MACRO[profile]
        budget = _BUDGETS.get(profile)
        if budget is None:
            continue
        affordable = group[group["implementation_cost_points"] <= budget]
        if affordable.empty:
            continue
        best = affordable.loc[affordable["mean_hours_lost"].idxmin()]
        macros.one_dp(f"{prefix}{tag}BestAffordableMeanLoss",
                      best["mean_hours_lost"])
        macros.integer(f"{prefix}{tag}BestAffordableCost",
                       best["implementation_cost_points"])
        macros.percent(f"{prefix}{tag}BestAffordableOutage",
                       best["sustained_outage_probability"])
        macros.integer(f"{prefix}{tag}Budget", budget)
        macros.integer(f"{prefix}{tag}AffordableCandidates", len(affordable))
    return consumed


def add_full_space_comparison(macros: Macros, directory: Path) -> list[Path]:
    path = directory / "portfolio_full_space_vs_finalist.csv"
    if not path.exists():
        return []
    comparison = pd.read_csv(path)
    macros.integer("ConfirmFinalistLabelled",
                   comparison["is_frozen_finalist"].sum())
    macros.integer("ConfirmFinalistOnlyFrontier",
                   comparison["pareto_finalist_only"].sum())
    macros.integer("ConfirmFullSpaceFrontier",
                   comparison["pareto_full_space"].sum())
    macros.integer("ConfirmFinalistOnlyArtifacts",
                   comparison["finalist_only_artifact"].sum())
    for profile, group in comparison.groupby("profile"):
        tag = PROFILE_MACRO[profile]
        macros.integer(f"Confirm{tag}FinalistOnlyArtifacts",
                       group["finalist_only_artifact"].sum())
        macros.integer(f"Confirm{tag}FinalistOnlyFrontier",
                       group["pareto_finalist_only"].sum())
    survived = comparison[(comparison["is_frozen_finalist"] == 1)
                          & (comparison["pareto_full_space"] == 1)]
    macros.integer("ConfirmFinalistsSurviving", len(survived))
    macros.integer("ConfirmFinalistsDisplaced",
                   int(comparison["is_frozen_finalist"].sum()) - len(survived))
    # Candidates the previous design would never have evaluated at all, yet
    # which are non-dominated over the full space.
    unseen = comparison[(comparison["is_frozen_finalist"] == 0)
                        & (comparison["pareto_full_space"] == 1)]
    macros.integer("ConfirmNonFinalistsOnFrontier", len(unseen))
    return [path]


def add_bimodality(macros: Macros, raw_path: Path) -> list[Path]:
    """The clinical-outage bimodality that settles the choice of k."""
    from grrc.endpoints import max_streak_column
    from grrc.enums import CLINICAL_SERVICES

    raw = pd.read_csv(raw_path, usecols=[
        max_streak_column(s) for s in CLINICAL_SERVICES] + ["profile"])
    threshold = 24
    qualifying = sum(
        (raw[max_streak_column(s)] > threshold).astype(int)
        for s in CLINICAL_SERVICES)
    counts = qualifying.value_counts()
    total = int(len(raw))
    macros.integer("BimodalTrials", total)
    macros.integer("BimodalNone", counts.get(0, 0))
    macros.integer("BimodalAll", counts.get(len(CLINICAL_SERVICES), 0))
    between = total - counts.get(0, 0) - counts.get(len(CLINICAL_SERVICES), 0)
    macros.integer("BimodalBetween", between)
    macros.percent("BimodalBetweenShare", between / total if total else 0)
    return [raw_path]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config",
                        default="configs/multiobjective_portfolio.yaml")
    parser.add_argument("--protocol",
                        default="multiobjective_confirmatory_v1")
    parser.add_argument("--output",
                        default="docs/manuscript/generated_numbers.tex")
    args = parser.parse_args()

    cfg = load_config(args.config)
    _BUDGETS.update({name: profile.budget
                     for name, profile in cfg.profiles.items()})
    macros = Macros()
    consumed: list[Path] = []

    macros.integer("EnumeratedPortfolios", 288)
    macros.integer("PrimaryK", cfg.simulation.sustained_outage_min_services)
    macros.integer("OutageThresholdSteps",
                   cfg.simulation.sustained_outage_service_steps)
    macros.integer("OutageThresholdHours",
                   cfg.simulation.sustained_outage_service_steps
                   * cfg.simulation.step_minutes / 60)
    macros.integer("HorizonHours",
                   cfg.simulation.max_steps * cfg.simulation.step_minutes / 60)
    macros.integer("StepMinutes", cfg.simulation.step_minutes)
    macros.integer("ServiceFunctionalPercent",
                   round(100 * cfg.simulation.service_functional_fraction))
    # Horizons named in the prospective-work paragraph. They are declared
    # targets rather than settings of this run, so they are defined here
    # once and referenced, not retyped.
    macros.integer("AcuteHorizonHours", 72)
    macros.integer("MinimumViableHorizonDays", 21)
    macros.integer("FullRecoveryHorizonDays", 90)
    macros.integer("TailHorizonDays", 180)
    # The bootstrap-inclusion threshold the stability counts are reported at.
    macros.add("StabilityThreshold", "0.80")

    consumed += add_stage(macros, "Discovery", DISCOVERY, cfg)
    consumed += add_bimodality(
        macros, DISCOVERY / "discovery_results.csv")

    protocol = None
    if (CONFIRM / "portfolio_objective_summary.csv").exists():
        consumed += add_stage(macros, "Confirm", CONFIRM, cfg)
        consumed += add_full_space_comparison(macros, CONFIRM)
        protocol = load_frozen_protocol(args.protocol)
        macros.add("ProtocolDigest", protocol["sha256"][:12])
        macros.add("ProtocolFrozenAt", protocol["frozen_at"].replace("+00:00", "Z"))
        macros.integer("ConfirmTotalExecutions",
                       protocol["body"]["design"]["total_executions"])

    validation = CONFIRM / "external_validation.json"
    if validation.exists():
        report = json.loads(validation.read_text(encoding="utf-8"))
        macros.integer("ValidationBenchmarks", report["benchmarks_total"])
        scored = report.get("computed_verdicts_for_scored_benchmarks", {})
        macros.integer("ValidationScored", len(scored))
        counts = report.get("verdict_counts", {})
        macros.integer("ValidationNotAddressable",
                       counts.get("not_addressable", 0))
        macros.integer("ValidationNotScored", counts.get("not_scored", 0))
        macros.integer("ValidationFailed",
                       counts.get("fail", 0)
                       + sum(1 for v in scored.values() if v == "fail"))
        for entry in report["benchmarks"]:
            scoring = entry.get("scoring") or {}
            if entry["id"] == "crowdstrike_short_outage" and scoring:
                macros.one_dp("ValidationOutageModelMedianHours",
                              scoring["model_median_outage_hours"])
                macros.one_dp("ValidationOutageTargetMedianHours",
                              scoring["target_median_hours"])
                macros.percent("ValidationOutageModelSixHourShare",
                               scoring["model_share_within_six_hours"])
                macros.percent("ValidationOutageTargetSixHourShare",
                               scoring["target_share_within_six_hours"])
        consumed.append(validation)

    structural = Path("data/multiobjective/structural_sensitivity/"
                      "structural_frontier_agreement.csv")
    if structural.exists():
        frame = pd.read_csv(structural)
        macros.integer("StructuralCandidatesTested",
                       frame["candidates_tested"].sum())
        macros.integer("StructuralPreserved", frame["preserved"].sum())
        macros.integer("StructuralOnlyGated", frame["only_under_gated"].sum())
        macros.integer("StructuralOnlyParallel",
                       frame["only_under_parallel"].sum())
        macros.percent("StructuralWorstAgreement",
                       frame["jaccard_agreement"].min())
        macros.percent("StructuralBestAgreement",
                       frame["jaccard_agreement"].max())

        movement = Path("data/multiobjective/structural_sensitivity/"
                        "structural_objective_movement.csv")
        if movement.exists():
            moved = pd.read_csv(movement).set_index(
                ["structural_arm", "profile"])
            for profile, tag in PROFILE_MACRO.items():
                for arm, label in (("gated_primary", "Gated"),
                                   ("parallel_alternative", "Parallel")):
                    key = (arm, profile)
                    if key not in moved.index:
                        continue
                    row = moved.loc[key]
                    macros.one_dp(f"Structural{tag}{label}MeanLoss",
                                  row["mean_mean_hours_lost"])
                    macros.percent(f"Structural{tag}{label}NonRecovery",
                                   row["mean_nonrecovery_probability"])
            consumed.append(movement)
        consumed.append(structural)

    sensitivity = CONFIRM / "parameter_sensitivity_summary.json"
    if sensitivity.exists():
        report = json.loads(sensitivity.read_text(encoding="utf-8"))
        macros.integer("SampledParameters", report["parameters_sampled"])
        worst = report.get("worst_rank_stability")
        if worst is not None:
            macros.add("SensitivityWorstRankStability", f"{worst:.2f}")
        dominant = report.get("dominant_parameter_by_profile_objective", [])
        for entry in dominant:
            if entry["profile"] not in PROFILE_MACRO:
                continue
            tag = PROFILE_MACRO[entry["profile"]]
            if entry["objective"] != "mean_hours_lost":
                continue
            name = "".join(part.capitalize()
                           for part in entry["parameter"].split("_")
                           if part not in ("simulation", "network"))
            macros.add(f"Sensitivity{tag}DominantParameter", name)
            macros.percent(f"Sensitivity{tag}DominantEffect",
                           entry["first_order_effect"])
            if entry.get("rank_stability") is not None:
                macros.add(f"Sensitivity{tag}DominantRankStability",
                           f"{entry['rank_stability']:.2f}")
        consumed.append(sensitivity)

    precision = DISCOVERY / "precision_analysis.json"
    if precision.exists():
        report = json.loads(precision.read_text(encoding="utf-8"))
        binding = report["binding_requirement"]["paired_max"]
        if binding is not None:
            macros.integer("PrecisionBindingPaired", binding)
        # The two objectives the study cannot resolve, and the profile whose
        # candidates are literally identical on three of four objectives.
        degenerate = 0
        for profile, entry in report["profiles"].items():
            for stats in entry["objectives"].values():
                if stats["candidate_mean_iqr"] == 0.0:
                    degenerate += 1
            if profile == "high_capacity":
                macros.integer(
                    "PrecisionHighCapacityDegenerateObjectives",
                    sum(1 for stats in entry["objectives"].values()
                        if stats["candidate_mean_iqr"] == 0.0))
                mean = entry["objectives"]["mean_hours_lost"]
                macros.add("PrecisionHighCapacityMeanLossIQR",
                           f"{mean['candidate_mean_iqr']:.3f}")
                if mean["required_scenarios_paired"]:
                    macros.integer("PrecisionHighCapacityMeanLossRequired",
                                   mean["required_scenarios_paired"])
            if profile == "resource_constrained":
                outage = entry["objectives"]["sustained_outage_probability"]
                if outage["required_scenarios_paired"]:
                    macros.integer("PrecisionResourceConstrainedOutageRequired",
                                   outage["required_scenarios_paired"])
        macros.integer("PrecisionDegenerateObjectives", degenerate)
        consumed.append(precision)

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(macros.render(), encoding="utf-8")

    manifest = build_manifest(
        run_id="manuscript-numbers", stage="analysis",
        description="LaTeX macros for every number the manuscript quotes, "
                    "generated from committed result tables so that no "
                    "result value is hand-typed in the manuscript.",
        inputs=[args.config] + consumed,
        outputs=[out],
        parameters={"macros_defined": len(macros)},
        protocol=({key: protocol[key]
                   for key in ("name", "path", "sha256", "frozen_at")}
                  if protocol else None))
    write_manifest(manifest, out.parent / "generated_numbers_manifest.json")
    print(f"wrote {len(macros)} macros to {out}")


if __name__ == "__main__":
    main()
