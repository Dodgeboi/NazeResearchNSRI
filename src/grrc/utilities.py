"""Shared helpers: deterministic seeding, logging, and path handling."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd

#: Canonical float format for every CSV the study writes. Fixing the
#: precision here (10 significant figures) makes outputs byte-for-byte
#: identical across platforms and pandas versions, so reproducibility does
#: not depend on a library's default float repr (see docs/limitations.md).
CSV_FLOAT_FORMAT = "%.10g"

#: Repository root (two levels above this file's package directory).
REPO_ROOT = Path(__file__).resolve().parents[2]

LOG_FORMAT = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"


def setup_logging(log_dir: Path | None = None, name: str = "grrc",
                  level: int = logging.INFO) -> logging.Logger:
    """Configure a logger that writes to stderr and optionally a file."""
    logger = logging.getLogger(name)
    logger.setLevel(level)
    if not logger.handlers:
        stream = logging.StreamHandler(sys.stderr)
        stream.setFormatter(logging.Formatter(LOG_FORMAT))
        logger.addHandler(stream)
        if log_dir is not None:
            log_dir.mkdir(parents=True, exist_ok=True)
            fh = logging.FileHandler(log_dir / f"{name}.log")
            fh.setFormatter(logging.Formatter(LOG_FORMAT))
            logger.addHandler(fh)
    return logger


def trial_rng(master_seed: int, trial_id: int) -> np.random.Generator:
    """Return a reproducible, statistically independent RNG for one trial.

    Uses numpy's SeedSequence spawning so that (master_seed, trial_id)
    always maps to the same stream, while different trial_ids give
    independent streams. This is the backbone of reproducibility:
    every CSV row records its (master_seed, trial_id) pair.
    """
    seq = np.random.SeedSequence(entropy=master_seed, spawn_key=(trial_id,))
    return np.random.default_rng(seq)


def ensure_dirs(*paths: Path) -> None:
    """Create directories (and parents) if they do not exist."""
    for p in paths:
        p.mkdir(parents=True, exist_ok=True)


def resolve_path(path_str: str) -> Path:
    """Resolve a config path relative to the repository root."""
    p = Path(path_str)
    return p if p.is_absolute() else REPO_ROOT / p


def write_csv(df: "pd.DataFrame", path: Path) -> Path:
    """Write a DataFrame to CSV with the study's canonical float format.

    Using a fixed ``float_format`` (rather than pandas' default repr) is
    what makes the committed CSVs reproduce byte-for-byte on any machine
    or library version, so the "bit-identical" reproducibility claim holds
    beyond the exact environment that first generated them.
    """
    path = Path(path)
    df.to_csv(path, index=False, float_format=CSV_FLOAT_FORMAT)
    return path
