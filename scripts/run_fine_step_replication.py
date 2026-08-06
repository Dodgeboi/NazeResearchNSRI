#!/usr/bin/env python3
"""Run the frozen post-diagnostic five-minute replication."""

from pathlib import Path

from grrc.config import load_config
from grrc.fine_step_validation import run_fine_step_replication

REPO = Path(__file__).resolve().parents[1]
CONFIG = REPO / "configs" / "fine_step_replication.yaml"

if __name__ == "__main__":
    run_fine_step_replication(load_config(CONFIG), CONFIG)
