#!/usr/bin/env python3
"""Render the ATT&CK-gaps figures from committed CSVs (no data computed here).

Figure 1 (two panels, release date on x):
  (A) kill-chain techniques, techniques with no real mitigation, and techniques with a
      single mitigation -- all counts of techniques, so one axis;
  (B) the provable catastrophic floor for k=1 (adaptive adversary, all mitigations
      deployed) versus the counterfactual with every gap repaired -- both in percent.
Figure 2: the minimal number of techniques needing a new mitigation for certification
to become possible, per release, at three targets.
Figure 3 (two panels): (A) Kaplan-Meier estimate that an uncovered technique is still
without a mitigation t years after it is first observed uncovered (three conventions);
(B) documented ransomware (entities using T1486) meeting the gaps, per release.

Structural breaks (sub-techniques at v7; the v19 Defense Evasion split) are marked.
Okabe-Ito colourblind-safe palette; deterministic PDFs; not manifest-tracked.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/attack_history"
OUT = ROOT / "docs/attack_gaps"
BLACK, BLUE, VERMILLION, GREEN, ORANGE = "#000000", "#0072B2", "#D55E00", "#009E73", "#E69F00"
BREAKS = {"7.2": "sub-techniques", "19.2": "Defense Evasion split"}


def _read(name):
    df = pd.read_csv(DATA / name, dtype={"version": str})
    df["date"] = pd.to_datetime(df["release_date"])
    return df


def _breaks(ax, cov):
    """Dotted vertical lines at the structural breaks (explained in the caption, so no
    in-plot text competes with the data or the legend)."""
    for v in BREAKS:
        d = cov.loc[cov.version == v, "date"]
        if len(d):
            ax.axvline(d.iloc[0], color="#999999", lw=0.8, ls=":")


def _style(ax):
    ax.grid(True, alpha=0.25, lw=0.6)
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))


def main():
    cov = _read("coverage_by_release.csv")
    cov = cov[cov.comparable].sort_values("date")
    flo = _read("floor_by_release.csv").sort_values("date")
    rep = _read("minimal_repair.csv")
    rep = rep[rep.e_new == 0.2].sort_values("date")
    OUT.mkdir(parents=True, exist_ok=True)

    fig, (axa, axb) = plt.subplots(1, 2, figsize=(7.4, 3.1))
    axa.plot(cov.date, cov.kill_chain_techniques, marker="o", ms=4, lw=2, color=BLACK,
             label="kill-chain techniques")
    axa.plot(cov.date, cov.single_mitigation, marker="s", ms=4, lw=2, color=ORANGE,
             label="one mitigation only")
    axa.plot(cov.date, cov.uncovered, marker="D", ms=4, lw=2, color=VERMILLION,
             label="no real mitigation")
    _breaks(axa, cov)
    axa.set_ylabel("techniques"); axa.set_title("ATT&CK kill-chain coverage", fontsize=10)
    axa.set_ylim(0, None); _style(axa)
    axa.legend(frameon=False, fontsize=7.5, loc="center right")

    axb.plot(flo.date, 100 * flo.catastrophic_floor_k1, marker="o", ms=4, lw=2, color=VERMILLION,
             label="floor, as published")
    axb.plot(flo.date, 100 * flo.repaired_catastrophic_floor_k1, marker="s", ms=4, lw=2,
             color=BLUE, label="floor, all gaps repaired")
    _breaks(axb, cov)
    axb.set_ylabel("worst-case residual risk (%)")
    axb.set_title("Certification floor, $k=1$ (any portfolio)", fontsize=10)
    axb.set_ylim(0, 26); _style(axb)
    axb.legend(frameon=False, fontsize=7.5, loc="center right")
    fig.autofmt_xdate(rotation=0, ha="center")
    fig.tight_layout()
    fig.savefig(OUT / "figure_coverage_floor.pdf", metadata={"CreationDate": None})

    fig, ax = plt.subplots(figsize=(4.6, 2.9))
    # (eps=0.05, k=2) coincides with (eps=0.10, k=1): the k-of-n bound roughly halves.
    top = 0.0
    for (eps, k), col, mk in [((0.10, 1), BLUE, "o"), ((0.05, 1), VERMILLION, "s"),
                              ((0.01, 4), GREEN, "^")]:
        s = rep[(rep.epsilon == eps) & (rep.k == k)]
        y = s.cost.where(s.feasible)
        top = max(top, float(y.max()))
        ax.plot(s.date, y, marker=mk, ms=4, lw=2, color=col,
                label=f"$\\varepsilon={eps:g}$, $k={k}$")
    top *= 1.35                                           # headroom for the legend
    _breaks(ax, cov)
    ax.set_ylabel("techniques needing a mitigation")
    ax.set_title("Minimal coverage repair", fontsize=10)
    ax.set_ylim(0, top); _style(ax)
    ax.legend(frameon=False, fontsize=7.5, loc="upper center", ncol=3, columnspacing=1.0)
    fig.autofmt_xdate(rotation=0, ha="center")
    fig.tight_layout()
    fig.savefig(OUT / "figure_repair.pdf", metadata={"CreationDate": None})

    surv = pd.read_csv(DATA / "gap_survival.csv")
    expo = _read("usage_exposure.csv")
    expo = expo[expo.variant == "default"].sort_values("date")
    fig, (axa, axb) = plt.subplots(1, 2, figsize=(7.4, 3.0))
    for variant, col, ls, label in [("default", VERMILLION, "-", "own mapping"),
                                    ("default_entrants_only", BLUE, "--", "own mapping, entrants"),
                                    ("parent_inheritance", GREEN, ":", "parent inheritance")]:
        c = surv[surv.variant == variant].sort_values("years")
        axa.step(c.years, c.survival, where="post", lw=2, ls=ls, color=col, label=label)
    axa.set_xlabel("years since first observed uncovered")
    axa.set_ylabel("share still without a mitigation")
    axa.set_title("Gaps rarely close (Kaplan-Meier)", fontsize=10)
    axa.set_ylim(0, 1.02); axa.set_xlim(0, None)
    axa.grid(True, alpha=0.25, lw=0.6)
    axa.legend(frameon=False, fontsize=7.5, loc="lower left")
    axb.plot(expo.date, 100 * expo.exposed_share, marker="o", ms=4, lw=2, color=VERMILLION,
             label="entities using $\\geq$1 uncovered technique")
    axb.plot(expo.date, 100 * expo.uncovered_use_share, marker="s", ms=4, lw=2, color=BLUE,
             label="their kill-chain uses on uncovered ones")
    _breaks(axb, cov)
    axb.set_ylabel("% of documented ransomware")
    axb.set_title("Documented ransomware uses the gaps", fontsize=10)
    axb.set_ylim(0, 105); _style(axb)
    axb.legend(frameon=False, fontsize=7.5, loc="center right")
    fig.autofmt_xdate(rotation=0, ha="center")
    fig.tight_layout()
    fig.savefig(OUT / "figure_persistence_usage.pdf", metadata={"CreationDate": None})
    print(f"wrote figures to {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
