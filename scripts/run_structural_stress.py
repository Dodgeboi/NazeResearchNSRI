#!/usr/bin/env python3
"""Run structural timing, threshold, and service-weight alternatives."""

from pathlib import Path

from grrc.advanced_experiments import run_structural_stress
from grrc.config import load_config

REPO = Path(__file__).resolve().parents[1]

if __name__ == "__main__":
    run_structural_stress(
        load_config(REPO / "configs" / "confirmatory.yaml"))
