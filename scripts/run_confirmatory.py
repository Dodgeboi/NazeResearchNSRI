#!/usr/bin/env python3
"""Run the prespecified paired confirmatory main and sweep experiments."""

from pathlib import Path

from grrc.config import load_config
from grrc.confirmatory import run_confirmatory

REPO = Path(__file__).resolve().parents[1]

if __name__ == "__main__":
    run_confirmatory(load_config(REPO / "configs" / "confirmatory.yaml"))
