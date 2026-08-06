#!/usr/bin/env python3
"""Run the frozen public-evidence validation phase without overwriting history."""

from pathlib import Path

from grrc.config import load_config
from grrc.public_validation import run_public_validation

REPO = Path(__file__).resolve().parents[1]
CONFIG = REPO / "configs" / "public_evidence_validation.yaml"

if __name__ == "__main__":
    run_public_validation(load_config(CONFIG), CONFIG)
