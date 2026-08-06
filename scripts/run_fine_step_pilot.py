#!/usr/bin/env python3
"""Run the exploratory fine-time-step convergence pilot."""

from pathlib import Path

from grrc.config import load_config
from grrc.public_validation import run_fine_step_pilot

REPO = Path(__file__).resolve().parents[1]

if __name__ == "__main__":
    run_fine_step_pilot(load_config(
        REPO / "configs" / "public_evidence_validation.yaml"))
