#!/usr/bin/env python3
"""Rerun the documented post-run correction to two diagnostics."""

from pathlib import Path

from grrc.config import load_config
from grrc.public_validation import run_corrected_diagnostics

REPO = Path(__file__).resolve().parents[1]

if __name__ == "__main__":
    run_corrected_diagnostics(load_config(
        REPO / "configs" / "public_evidence_validation.yaml"))
