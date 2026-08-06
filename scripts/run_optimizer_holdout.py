#!/usr/bin/env python3
"""Confirm optimizer finalists on fresh paired seeds."""

from pathlib import Path

from grrc.config import load_config
from grrc.confirmatory import run_optimizer_holdout

REPO = Path(__file__).resolve().parents[1]

if __name__ == "__main__":
    cfg = load_config(REPO / "configs" / "confirmatory.yaml")
    run_optimizer_holdout(
        cfg, REPO / "data" / "raw" / "standard_optimization_results.csv")
