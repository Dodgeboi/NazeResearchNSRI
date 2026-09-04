#!/usr/bin/env python3
"""Decompress committed raw trial files so manifests can verify against them.

The confirmatory bank is 101 MB uncompressed and 5.7 MB gzipped, so the
repository stores the compressed copy. Nothing about the provenance chain is
weakened by this: manifests still hash the *uncompressed* bytes, and
verification still fails if a single value changed. This script only restores
the file the manifest describes.

Run it once after cloning, before `run_full_audit.py`.

**Why this compares content and not timestamps.** An earlier version treated
an uncompressed file as current whenever its mtime was newer than the
archive's. That is not a test of anything: it made the script a no-op in the
working tree where a study had just been re-run, so a *stale* archive beside a
fresh CSV went unnoticed here and would have been unpacked over the good data
on any fresh clone. It happened. The archive committed alongside the
160,000-execution confirmatory bank was the superseded 137,600-execution one,
and every check in the audit passed regardless, because none of them ever
opened the archive.

So the currency test is now the only one that means anything: decompress and
compare SHA-256. It costs a few seconds and it cannot be satisfied by a file
that merely looks recent.

A mismatch is an error, not something to repair quietly. Either the archive is
stale (a study was re-run and not re-committed) or the working copy is (an
edit nobody meant to make), and this script cannot tell which — overwriting on
a guess would throw away hours of compute in the first case. It exits non-zero
and names both hashes. `--restore` forces the archive to win, for the case
where you know it should.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import shutil
import sys
from pathlib import Path

from grrc.utilities import REPO_ROOT

CHUNK = 1 << 20


def _digest(stream) -> str:
    digest = hashlib.sha256()
    while chunk := stream.read(CHUNK):
        digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--restore", action="store_true",
        help="overwrite an uncompressed file that disagrees with its archive")
    args = parser.parse_args()

    archives = sorted(REPO_ROOT.glob("data/**/*.csv.gz"))
    if not archives:
        print("no compressed raw files found")
        return 0
    conflicts: list[str] = []
    for archive in archives:
        target = archive.with_suffix("")  # strip .gz
        with gzip.open(archive, "rb") as source:
            archived = _digest(source)
        if target.exists():
            with open(target, "rb") as existing:
                on_disk = _digest(existing)
            if on_disk == archived:
                print(f"ok       {target.relative_to(REPO_ROOT)} "
                      f"(matches archive, sha256 {archived[:12]})")
                continue
            if not args.restore:
                conflicts.append(
                    f"{target.relative_to(REPO_ROOT)}: on disk "
                    f"{on_disk[:12]}, archive {archived[:12]}. One of them is "
                    "stale and this script cannot tell which. Re-gzip the "
                    "file if the run is newer than the archive, or pass "
                    "--restore to take the archive.")
                continue
        with gzip.open(archive, "rb") as source, open(target, "wb") as sink:
            shutil.copyfileobj(source, sink, length=CHUNK)
        print(f"unpacked {target.relative_to(REPO_ROOT)} "
              f"({target.stat().st_size:,} bytes, sha256 {archived[:12]})")
    if conflicts:
        print("\ncompressed archives disagree with the files beside them:",
              file=sys.stderr)
        for conflict in conflicts:
            print(f"  {conflict}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
