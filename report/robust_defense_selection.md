# Adversary-robust defense selection: the study's tight-budget advice is not robust

*Reproduce with `python scripts/discover_robust_defense.py` (regional
hospital, intermediate-capacity profile, 120 matched trials, targeting
strength α = 3). Data: `outputs/robust/`.*

## The idea

The main study selects a budget-constrained defense by minimizing expected
disruption **against the base (untargeted) attacker**. The adversary-robustness
experiment showed a value-targeting attacker erodes those defenses unevenly. So
this is a *selection* question: **is the portfolio the study recommends still
the best choice against a targeting attacker?** If not, selecting against that
attacker — *adversary-robust selection* — yields a different, more robust
defense at the same cost.

We evaluate the study's own deduplicated portfolio lattice against both the
naive and the targeting attacker, and for each budget compare the study's pick
(min damage vs naive) with the robust pick (min damage vs adaptive).

## The finding

| Budget | Study's pick (vs naive) | …vs targeting attacker | Robust pick | …vs targeting attacker | Picks differ? |
|---|---|---|---|---|---|
| **5** | least-priv segmentation + connected backups | **174.7 hrs, P(cat)=0.97** | flat + fast detection + **isolated backups** | **77.1 hrs, P(cat)=0.95** | **yes — regret 97.6 hrs** |
| 10 | least-priv + patch + fast detection + connected backups | 70.1 hrs, 0.71 | (same) | 70.1 hrs, 0.71 | no |
| 15 | least-priv + patch + fast detection + isolated backups | 36.7 hrs, 0.53 | (same) | 36.7 hrs, 0.53 | no |

**At the tightest budget the study's recommendation is 2.3× worse against a
targeting attacker than the robust choice at the same cost.** The study spends
its 5 points on least-privilege *segmentation* with connected backups; a
targeting attacker routes through permitted paths toward value and around the
zone boundaries, so that spend is largely wasted (174.7 weighted service-hours,
97% catastrophic). The robust choice reallocates the same 5 points to **fast
detection + isolated backups** — the two controls a value-seeker cannot route
around — halving the damage to 77.1 hours.

At budgets 10 and 15 the two criteria converge (the naive-optimal portfolio is
already robust), so the divergence is specific to the **tight-budget regime**.
See `outputs/robust/robust_selection.png`.

## Why this matters (and ties to the study's own thesis)

The tight budget is the **resource-constrained** tier — the low-resource
providers the study is fundamentally about. The result says those providers get
the *most* miscalibrated advice from an expected-damage optimizer: told to buy
segmentation, when against a realistic attacker their five points are far better
spent on detection speed and isolated backups. It is consistent with the
adversary-robustness finding (segmentation collapses under targeting) and gives
it an actionable form: **at low budgets, prefer controls a targeting attacker
cannot bypass (detection, isolated backups) over segmentation.**

## What this is, honestly

**Not a novel algorithm.** Robust / minimax and adversary-aware defense
selection are established ideas (robust optimization, security games). The
contribution is (a) the **domain-first application** — selecting healthcare
ransomware defenses against a targeting rather than untargeted adversary — and
(b) the **specific, non-obvious, reproducible finding** that the study's own
budget-optimizer is non-robust exactly at the tight budget, and how to fix the
allocation. It is a genuine result about this work; it is not a claim to have
invented robust selection.

## Limitations

One facility/profile, one targeting model (a value-weighted spread bias with
α = 3), and the named-lattice cost model. The divergence at budget 5 is large
and stable at 120 trials; the convergence at 10/15 is this parameterization's
result, not a general guarantee. The robust, honest claim is directional: an
expected-damage optimizer tuned to an untargeted attacker can badly misallocate
a tight budget against a targeting one, and detection + isolated backups are
the robust low-budget buys.
