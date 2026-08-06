#!/usr/bin/env python3
"""Run the budget-constrained defense optimization + cost sensitivity.

Equivalent to:  python -m grrc.cli optimize --config <config>
"""
import sys

from grrc.cli import main

if __name__ == "__main__":
    sys.exit(main(["optimize"] + sys.argv[1:]))
