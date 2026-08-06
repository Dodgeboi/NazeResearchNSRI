#!/usr/bin/env python3
"""Analyze all confirmatory and robustness outputs."""

from pathlib import Path

from grrc.advanced_analysis import analyze_all
from grrc.config import load_config

REPO = Path(__file__).resolve().parents[1]

if __name__ == "__main__":
    analyze_all(load_config(REPO / "configs" / "confirmatory.yaml"))
