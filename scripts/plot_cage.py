#!/usr/bin/env python3
"""Figures for the CAGE-2 certified-evaluation paper (from committed CSVs only).

Figure 1: per defender (rows) and attacker (marker/colour), the breach rate of the
operational server with its time-uniform 95% certified interval.
Figure 2: the certified breach-rate interval as episodes accumulate, for the challenge
winner against a seen attacker and against the delayed (unseen) attacker, with the
threshold the protocol resolves against.
Okabe-Ito palette (validated); deterministic PDFs.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from grrc.cage.certify import iid_bounds

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/cage"
OUT = ROOT / "docs/cage_certified"
ATTACKERS = [("b_line", "B_line (seen)", "#0072B2", "o"),
             ("meander", "Meander (seen)", "#009E73", "s"),
             ("delayed_b_line", "Delayed B_line (unseen)", "#D55E00", "D"),
             ("meander_then_b_line", "Meander→B_line (unseen)", "#CC79A7", "^")]
LABELS = {"sleep": "Sleep", "react-remove": "React-remove", "react-restore": "React-restore",
          "champion": "Challenge winner (PPO)", "champion+fallback": "Winner + 1-line fallback"}


def label(d):
    if d in LABELS:
        return LABELS[d]
    name = d.replace("-nothink", "")
    family = next((f for f in ("haiku", "sonnet", "opus") if f in name), None)
    if name.startswith("claude-") and family:
        version = name.split(family + "-", 1)[1].replace("-", ".")
        name = f"Claude {family.capitalize()} {version}"
    return name + (" (no thinking)" if d.endswith("-nothink") else " (thinking)" if d.startswith("claude-") else "")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    s = pd.read_csv(DATA / "certified_summary.csv")
    s = s[~s.adaptive]
    order = ["sleep", "react-remove", "react-restore", "champion", "champion+fallback"]
    order += sorted(d for d in s.defender.unique() if d not in order)
    fig, ax = plt.subplots(figsize=(7.2, 0.5 + 0.42 * len(order)))
    for j, (a, name, col, mk) in enumerate(ATTACKERS):
        g = s[s.attacker == a].set_index("defender")
        ys = np.arange(len(order)) + (j - 1.5) * 0.17
        for y, d in zip(ys, order):
            if d not in g.index:
                continue
            r = g.loc[d]
            ax.plot([r.breach_lower, r.breach_upper], [y, y], color=col, lw=2, solid_capstyle="round")
            ax.plot(r.breach_mean, y, marker=mk, ms=6, color=col, mec="white", mew=0.8,
                    label=name if d == order[0] else None, ls="none")
    ax.set_yticks(range(len(order)))
    ax.set_yticklabels([label(d) for d in order], fontsize=8)
    ax.invert_yaxis()
    ax.set_xlim(-0.02, 1.02)
    ax.set_xlabel("breach rate of the operational server (95% certified interval)")
    ax.grid(True, axis="x", alpha=0.25, lw=0.6)
    ax.legend(frameon=False, fontsize=7.5, ncol=2, loc="upper center",
              bbox_to_anchor=(0.5, -0.22 if len(order) < 7 else -0.16))
    fig.tight_layout()
    fig.savefig(OUT / "figure_breach_intervals.pdf", metadata={"CreationDate": None})

    e = pd.read_csv(DATA / "episodes.csv")
    fig, ax = plt.subplots(figsize=(4.6, 2.9))
    for a, name, col, ls in [("b_line", "vs B_line (seen)", "#0072B2", "-"),
                             ("delayed_b_line", "vs delayed B_line (unseen)", "#D55E00", "--")]:
        x = e[(e.defender == "champion") & (e.attacker == a)].sort_values("episode").breached.astype(float).values
        ns = np.arange(2, len(x) + 1)
        lo, hi = zip(*[iid_bounds(x[:n], 0, 1, 0.05) for n in ns])
        ax.fill_between(ns, lo, hi, color=col, alpha=0.18, lw=0)
        ax.plot(ns, hi, color=col, lw=1.6, ls=ls, label=name)
        ax.plot(ns, lo, color=col, lw=1.6, ls=ls)
    ax.axhline(0.2, color="#555555", lw=0.8, ls=":")
    ax.text(len(x), 0.21, "threshold 0.2", ha="right", va="bottom", fontsize=7, color="#555555")
    ax.set_xscale("log")
    ax.set_xlabel("episodes evaluated")
    ax.set_ylabel("breach rate (certified)")
    ax.set_ylim(0, 1)
    ax.grid(True, alpha=0.25, lw=0.6)
    ax.legend(frameon=False, fontsize=7.5, loc="center right")
    ax.set_title("Challenge winner: certified interval over time", fontsize=9)
    fig.tight_layout()
    fig.savefig(OUT / "figure_anytime.pdf", metadata={"CreationDate": None})
    print(f"wrote figures to {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
