#!/usr/bin/env python3
"""Run the main + sweep Monte Carlo experiments.

Equivalent to:  python -m grrc.cli simulate --config <config>
"""
import sys

from grrc.cli import main

if __name__ == "__main__":
    sys.exit(main(["simulate"] + sys.argv[1:]))
