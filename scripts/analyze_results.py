#!/usr/bin/env python3
"""Produce processed summary tables and statistics from raw CSVs.

Equivalent to:  python -m grrc.cli analyze --config <config>
"""
import sys

from grrc.cli import main

if __name__ == "__main__":
    sys.exit(main(["analyze"] + sys.argv[1:]))
