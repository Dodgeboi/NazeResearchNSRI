#!/usr/bin/env python3
"""Run every verification this repository knows how to run, and report.

This is the harness behind the adversarial audit: one command that tries to
falsify the repository's own claims about itself. It runs each check to
completion rather than stopping at the first failure, because the useful
output is the *set* of things that are wrong, and it exits non-zero if any
check fails.

Checks, in the order a sceptical reader would want them:

1. Test suite, including the falsification and invariant tests.
2. Behavioral validation checks.
3. Archived sources: hashes, sizes, and re-derived counts.
4. Frozen protocols: each must still match its own recorded digest.
5. Run manifests: every recorded input and output must still be on disk with
   the recorded hash.
6. Manuscript claim audit: no hand-typed numbers, no orphan macros, endpoint
   definitions agreeing with the code, no red-line claims, required
   disclosures present.
7. Cross-artifact consistency: the numbers in the generated macros must match
   the tables they were generated from, recomputed independently here.

Check 7 exists because the other six can all pass while the manuscript quotes
a table that no longer exists. It re-derives the headline counts straight
from the raw trial files rather than trusting any intermediate.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import pandas as pd

from grrc.provenance import ProvenanceError, load_frozen_protocol, verify_manifest
from grrc.utilities import REPO_ROOT


class Result:
    def __init__(self, name: str) -> None:
        self.name = name
        self.problems: list[str] = []
        self.notes: list[str] = []

    @property
    def ok(self) -> bool:
        return not self.problems

    def report(self) -> None:
        status = "PASS" if self.ok else f"FAIL ({len(self.problems)})"
        print(f"{status:12s} {self.name}")
        for note in self.notes:
            print(f"             {note}")
        for problem in self.problems:
            print(f"      -> {problem}")


def run_command(name: str, command: list[str]) -> Result:
    result = Result(name)
    try:
        completed = subprocess.run(
            command, cwd=REPO_ROOT, capture_output=True, text=True,
            timeout=3600)
    except subprocess.SubprocessError as error:
        result.problems.append(f"could not run: {error}")
        return result
    tail = (completed.stdout or completed.stderr or "").strip().splitlines()
    if tail:
        result.notes.append(tail[-1][:160])
    if completed.returncode != 0:
        for line in (completed.stdout + completed.stderr).splitlines():
            if any(token in line for token in
                   ("FAIL", "Error", "error:", "assert", "->")):
                result.problems.append(line.strip()[:200])
        if not result.problems:
            result.problems.append(
                f"exited {completed.returncode} with no parseable failure")
    return result


def check_protocols() -> Result:
    result = Result("frozen protocols verify")
    directory = REPO_ROOT / "study" / "protocols"
    protocols = sorted(directory.glob("*.protocol.json")) if directory.exists() else []
    if not protocols:
        result.notes.append("no frozen protocols committed")
        return result
    for path in protocols:
        name = path.name.removesuffix(".protocol.json")
        try:
            loaded = load_frozen_protocol(name)
        except ProvenanceError as error:
            result.problems.append(f"{name}: {error}")
        else:
            result.notes.append(
                f"{name}: {loaded['sha256'][:12]} frozen {loaded['frozen_at']}")
    return result


def check_manifests() -> Result:
    result = Result("run manifests describe the files on disk")
    checked = 0
    for path in sorted((REPO_ROOT / "data").rglob("*manifest*.json")):
        if path.name == "source_manifest.json":
            continue
        if "archive_pre_rebuild" in path.parts:
            continue
        checked += 1
        try:
            verify_manifest(path)
        except (ProvenanceError, KeyError, TypeError) as error:
            result.problems.append(
                f"{path.relative_to(REPO_ROOT)}: {str(error)[:180]}")
    result.notes.append(f"{checked} manifests checked")
    return result


def check_cross_artifact_consistency() -> Result:
    """Re-derive the headline counts from raw trials, trusting nothing."""
    result = Result("manuscript numbers re-derive from raw trials")
    generated = REPO_ROOT / "docs" / "manuscript" / "generated_numbers.tex"
    if not generated.exists():
        result.problems.append("generated_numbers.tex is missing")
        return result

    import re
    macros = dict(re.findall(
        r"\\newcommand\{\\([A-Za-z]+)\}\{([^}]*)\}",
        generated.read_text(encoding="utf-8")))

    def as_int(name: str) -> int | None:
        raw = macros.get(name)
        return int(raw.replace(",", "")) if raw else None

    stages = {
        "Discovery": REPO_ROOT / "data/multiobjective/discovery/discovery_results.csv",
        "Confirm": REPO_ROOT / ("data/multiobjective/confirmatory/"
                                "multiobjective_confirmatory_results.csv"),
    }
    for prefix, raw_path in stages.items():
        if not raw_path.exists():
            result.notes.append(f"{prefix}: no raw file, skipped")
            continue
        raw = pd.read_csv(raw_path, usecols=["profile", "portfolio",
                                             "scenario_id"])
        claimed = as_int(f"{prefix}Executions")
        if claimed is not None and claimed != len(raw):
            result.problems.append(
                f"{prefix}Executions = {claimed:,} but the raw file has "
                f"{len(raw):,} rows")
        claimed = as_int(f"{prefix}Candidates")
        actual = raw.groupby("profile")["portfolio"].nunique().sum()
        if claimed is not None and claimed != actual:
            result.problems.append(
                f"{prefix}Candidates = {claimed} but the raw file has "
                f"{actual} profile-candidates")
        result.notes.append(
            f"{prefix}: {len(raw):,} rows, {actual} profile-candidates")

    # The bimodality figures the manuscript leans on must add up.
    trials = as_int("BimodalTrials")
    none = as_int("BimodalNone")
    every = as_int("BimodalAll")
    between = as_int("BimodalBetween")
    if None not in (trials, none, every, between):
        if none + every + between != trials:
            result.problems.append(
                f"bimodality macros do not sum: {none:,} + {every:,} + "
                f"{between:,} != {trials:,}")
        else:
            result.notes.append(
                f"bimodality: {none:,} + {between:,} + {every:,} = {trials:,}")
    return result


def check_validation_reported() -> Result:
    """A validation report that hides its failures is worse than none."""
    result = Result("external validation reports its failures")
    path = REPO_ROOT / ("data/multiobjective/confirmatory/"
                        "external_validation.json")
    if not path.exists():
        result.notes.append("no external validation report yet")
        return result
    report = json.loads(path.read_text(encoding="utf-8"))
    counts = report.get("verdict_counts", {})
    result.notes.append(
        f"{report.get('benchmarks_total')} benchmarks: {counts}")
    if not any(key in counts for key in ("fail", "not_addressable",
                                         "not_scored")):
        result.problems.append(
            "no benchmark is recorded as failing or unaddressable, which for "
            "a single-facility 72-hour binary-availability model is not "
            "credible; check that failures are still being reported")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-tests", action="store_true")
    args = parser.parse_args()

    python = sys.executable
    results: list[Result] = []
    # Manifests hash uncompressed bytes; restore anything stored gzipped
    # before anything tries to verify it.
    results.append(run_command(
        "unpack compressed raw banks", [python, "scripts/unpack_raw.py"]))
    if not args.skip_tests:
        results.append(run_command("test suite", [python, "-m", "pytest", "-q"]))
        results.append(run_command(
            "behavioral validation",
            [python, "-m", "grrc.cli", "validate", "--no-report"]))
    results.append(run_command(
        "archived sources", [python, "scripts/verify_sources.py"]))
    results.append(check_protocols())
    results.append(check_manifests())
    results.append(run_command(
        "manuscript claim audit",
        [python, "scripts/audit_manuscript_claims.py"]))
    results.append(check_cross_artifact_consistency())
    results.append(check_validation_reported())

    print()
    for result in results:
        result.report()

    failures = sum(len(r.problems) for r in results)
    print()
    if failures:
        print(f"AUDIT FAILED: {failures} problems across "
              f"{sum(1 for r in results if not r.ok)} checks", file=sys.stderr)
        return 1
    print(f"all {len(results)} checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
