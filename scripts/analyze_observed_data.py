"""Build empirical summaries and the observed-to-simulation bridge."""

from __future__ import annotations

from pathlib import Path

from grrc.observed_data import analyze_observed_data


if __name__ == "__main__":
    repository_root = Path(__file__).resolve().parents[1]
    outputs = analyze_observed_data(repository_root)
    for label, path in outputs.items():
        print(f"{label}: {path.relative_to(repository_root)}")
