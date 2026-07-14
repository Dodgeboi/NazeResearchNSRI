#!/usr/bin/env python3
"""Reproduce EVERY result of the study from a clean installation.

    python scripts/reproduce_all.py --profile quick     (~1-2 min)
    python scripts/reproduce_all.py --profile standard  (~10-30 min)
    python scripts/reproduce_all.py --profile full      (hours)

Pipeline: validate -> simulate -> optimize -> analyze -> plot -> report.
All outputs land in data/, outputs/ and report/ exactly as documented in
the README; identical seeds give identical CSVs.
"""
import argparse
import sys
from pathlib import Path

from grrc.cli import main

REPO = Path(__file__).resolve().parents[1]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=["quick", "standard", "full"],
                        default="quick")
    parser.add_argument("--workers", type=int, default=None)
    args = parser.parse_args()
    cli_args = ["reproduce", "--config",
                str(REPO / "configs" / f"{args.profile}.yaml")]
    if args.workers is not None:
        cli_args += ["--workers", str(args.workers)]
    sys.exit(main(cli_args))
