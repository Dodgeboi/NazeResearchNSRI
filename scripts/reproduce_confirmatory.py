#!/usr/bin/env python3
"""Reproduce the complete v2 evidence package from repository inputs."""

from pathlib import Path

from grrc.advanced_analysis import analyze_all
from grrc.advanced_experiments import run_all_advanced
from grrc.config import load_config
from grrc.confirmatory import run_confirmatory, run_optimizer_holdout
from grrc.optimization import optimize
from grrc.validation import run_all_validations, write_validation_report

REPO = Path(__file__).resolve().parents[1]

if __name__ == "__main__":
    cfg = load_config(REPO / "configs" / "confirmatory.yaml")
    validation = run_all_validations()
    write_validation_report(validation)
    if not all(result.passed for result in validation):
        raise SystemExit("Behavioral validation failed")
    run_confirmatory(cfg)
    optimizer_input = (
        REPO / "data" / "raw" / "standard_optimization_results.csv"
    )
    if not optimizer_input.exists():
        standard_cfg = load_config(REPO / "configs" / "standard.yaml")
        optimize(standard_cfg)
    run_optimizer_holdout(cfg, optimizer_input)
    run_all_advanced(cfg)
    analyze_all(cfg)
