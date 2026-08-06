#!/usr/bin/env python3
"""Analyze the fresh public-evidence validation outputs."""

from pathlib import Path

from grrc.config import load_config
from grrc.public_validation_analysis import analyze_public_validation

REPO = Path(__file__).resolve().parents[1]

if __name__ == "__main__":
    analyze_public_validation(load_config(
        REPO / "configs" / "public_evidence_validation.yaml"))
