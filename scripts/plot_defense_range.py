#!/usr/bin/env python3
"""Render the cyber-range figure from committed CSVs (no data computed here).

Two panels, assumed degradation:
  (A) typical adversary -- cost-to-certify vs k for each defender at epsilon=0.05
      (the optimality-gap ordering: optimal < greedy < coverage < random);
  (B) adaptive adversary -- the catastrophic reachability floor vs k against the
      epsilon thresholds, showing why most adaptive regimes are uncertifiable (the
      floor sits above epsilon until k is large).

Deterministic PDF (no timestamp). Colours are the Okabe-Ito colourblind-safe
categorical palette. This is a figure, regenerated on demand -- not manifest-tracked.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/defense_range"
OUT = ROOT / "docs/defense_range/figure_cost_vs_k.pdf"

# Okabe-Ito (colourblind-safe), assigned in fixed order to the four defenders.
COLOR = {"optimal": "#000000", "greedy": "#0072B2", "coverage": "#D55E00", "random": "#009E73"}
LABEL = {"optimal": "Optimal (exact)", "greedy": "Greedy (certificate)",
         "coverage": "Coverage (blind)", "random": "Random"}
EPS_PANEL = 0.05


def main():
    gap = pd.read_csv(DATA / "optimality_gap.csv")
    floor = pd.read_csv(DATA / "adaptive_floor.csv").sort_values("k")

    fig, (axa, axb) = plt.subplots(1, 2, figsize=(7.2, 3.1))

    # Panel A: typical adversary, cost-to-certify vs k at EPS_PANEL.
    ta = gap[(gap.adversary == "typical") & (gap.degradation_source == "assumed")
             & (gap.epsilon == EPS_PANEL)].sort_values("k")
    for pol, col in ("optimal", COLOR["optimal"]), ("greedy", COLOR["greedy"]), \
                    ("coverage", COLOR["coverage"]), ("random", COLOR["random"]):
        y = ta[f"{pol}_cost"] if pol != "optimal" else ta["optimal_size"]
        axa.plot(ta.k, y.mask(y < 0), marker="o", ms=5, lw=2, color=col, label=LABEL[pol])
    axa.set_title(f"Typical adversary ($\\varepsilon={EPS_PANEL:g}$)", fontsize=10)
    axa.set_xlabel("catastrophic threshold $k$"); axa.set_ylabel("controls to certify")
    axa.set_xticks([1, 2, 3, 4]); axa.grid(True, alpha=0.25, lw=0.6)
    axa.legend(frameon=False, fontsize=8, loc="upper right")

    # Panel B: adaptive reachability floor vs k against the epsilon thresholds.
    axb.plot(floor.k, 100 * floor.catastrophic_floor, marker="s", ms=5, lw=2,
             color="#CC79A7", label="adaptive floor (all controls)")
    for eps, style in [(0.10, ":"), (0.05, "--"), (0.01, "-.")]:
        axb.axhline(100 * eps, color="#666666", lw=1, ls=style)
        axb.text(4.02, 100 * eps, f"$\\varepsilon={eps:g}$", fontsize=7,
                 color="#666666", va="center", ha="left")
    axb.set_title("Adaptive adversary: no portfolio beats the floor", fontsize=10)
    axb.set_xlabel("catastrophic threshold $k$"); axb.set_ylabel("min. residual risk (%)")
    axb.set_xticks([1, 2, 3, 4]); axb.grid(True, alpha=0.25, lw=0.6)
    axb.legend(frameon=False, fontsize=8, loc="upper right")

    fig.tight_layout()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, metadata={"CreationDate": None})     # deterministic: no timestamp
    print(f"wrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
