#!/usr/bin/env python3
"""Run sensitivity, capacity-ablation, and imperfect-backup experiments."""

from pathlib import Path

from grrc.advanced_experiments import run_all_advanced
from grrc.config import load_config

REPO = Path(__file__).resolve().parents[1]

if __name__ == "__main__":
    run_all_advanced(load_config(REPO / "configs" / "confirmatory.yaml"))
