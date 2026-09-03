#!/usr/bin/env python3
"""Decompress committed raw trial files so manifests can verify against them.

The confirmatory bank is 68 MB uncompressed and 4.8 MB gzipped, so the
repository stores the compressed copy. Nothing about the provenance chain is
weakened by this: manifests still hash the *uncompressed* bytes, and
verification still fails if a single value changed. This script only restores
the file the manifest describes.

Run it once after cloning, before `run_full_audit.py`. It is idempotent and
never overwrites a newer uncompressed file.
"""

from __future__ import annotations

import gzip
import shutil
import sys
from pathlib import Path

from grrc.utilities import REPO_ROOT


def main() -> int:
    archives = sorted(REPO_ROOT.glob("data/**/*.csv.gz"))
    if not archives:
        print("no compressed raw files found")
        return 0
    for archive in archives:
        target = archive.with_suffix("")  # strip .gz
        if target.exists() and target.stat().st_mtime >= archive.stat().st_mtime:
            print(f"ok      {target.relative_to(REPO_ROOT)} (already current)")
            continue
        with gzip.open(archive, "rb") as source, open(target, "wb") as sink:
            shutil.copyfileobj(source, sink)
        print(f"unpacked {target.relative_to(REPO_ROOT)} "
              f"({target.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
