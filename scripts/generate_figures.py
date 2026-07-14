#!/usr/bin/env python3
"""Generate every publication figure (PNG + PDF + underlying data CSVs).

Equivalent to:  python -m grrc.cli plot --config <config>
"""
import sys

from grrc.cli import main

if __name__ == "__main__":
    sys.exit(main(["plot"] + sys.argv[1:]))
