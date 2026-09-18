# The study's resilience is adversary-dependent (a robustness finding)

*Reproduce with `python scripts/discover_adaptive_attacker.py` (main) and the
focus sweep in `outputs/attacker_sweep/`. Matched networks / entries / random
streams (master seed 20260713), regional hospital, intermediate-capacity
profile — the same setting as the study's headline. Data:
`outputs/attacker/`.*

## The question

The main study's central result — a full defense portfolio reduces weighted
service-hours lost by ~98% — is measured against the engine's **base
attacker**, whose lateral movement is a uniform, memoryless per-edge coin flip,
indifferent to what any node is worth. Real ransomware operators are not
memoryless: they work hands-on-keyboard toward the systems whose loss hurts
most (identity, EHR, backups). So: **does the reported resilience survive an
attacker that targets clinical value?**

We answer it with `AdaptiveAttackerSimulation`, which biases lateral movement
toward nodes of high *downstream clinical value* (the reverse-BFS service value
from `grrc.vgri`). A single knob, `focus` (α), sets sophistication: α = 0 is
exactly the base attacker; larger α concentrates movement on high-value targets.
Nothing else changes, so a matched-seed comparison isolates attacker targeting.

## The finding

First, a validation: at α = 0 our harness reproduces the study, a **97.9%**
full-defense reduction (3% catastrophic). Now raise α to a moderate 3 (200
matched trials):

| Portfolio | naive attacker | adaptive attacker | naive P(catastrophic) | adaptive P(catastrophic) |
|---|---|---|---|---|
| baseline_flat | 179.4 | 197.9 | 0.89 | 1.00 |
| patch_90 | 153.8 | 192.5 | 0.74 | 0.96 |
| isolated_backups | 131.1 | 140.5 | 0.89 | 0.99 |
| fast_detection | 84.8 | 126.6 | 0.68 | 0.96 |
| **least_privilege** | **67.8** | **169.7** | 0.52 | 0.94 |
| **full_defense** | **3.7** | **13.6** | **0.03** | **0.30** |

(weighted service-hours lost, means over 200 matched trials.)

Two results stand out, both material to the paper's conclusions:

1. **Full defense is far less bulletproof than reported.** Its catastrophic
   probability rises from **3% to 30%** and its damage nearly quadruples. The
   headline reduction falls from 97.9% to **93.1%** — still large, but the
   "near-immunity" framing does not survive.

2. **Network segmentation — the study's strongest *single* control — is almost
   neutralized.** Least-privilege segmentation goes from 67.8 to 169.7 weighted
   service-hours (catastrophic 0.52 → 0.94), i.e. nearly back to the 197.9
   no-defense baseline. A targeting attacker routes through the permitted paths
   toward value, so zone boundaries buy little. The study ranks segmentation as
   the top single defense; against a smart adversary that ranking collapses.

**It is a dose-response, not an artifact of one α.** Sweeping the targeting
strength (60 trials each) shows monotonic erosion:

| focus α | full-defense reduction | full-defense P(catastrophic) | least_privilege (adaptive) |
|---|---|---|---|
| 0 | 98.0% | 0.03 | 74.3 (= naive) |
| 1 | 96.3% | 0.12 | 133.7 |
| 2 | 96.1% | 0.15 | 171.6 |
| 4 | 89.9% | 0.30 | 177.5 |
| 6 | 85.1% | 0.50 | 178.7 |

The more the attacker targets clinical value, the more the reported resilience
erodes; at α = 6 the full portfolio is catastrophic **half** the time. See
`outputs/attacker/attacker_robustness.png`.

The mechanism is visible in the identity-compromise rate: under full defense it
rises from 6% (naive) to 23% (adaptive) — the attacker preferentially reaches
identity, whose loss cascades to every dependent service and multiplies spread.

## What this is, honestly

**Not a novel attack.** Targeted / crown-jewel lateral movement is standard
adversary behaviour and well documented. The contribution is the **robustness
finding**: the study's headline numbers are contingent on an untargeted
attacker, and a realistic targeting adversary erodes them substantially —
most sharply for segmentation. This is exactly the adversarial check a
pre-submission review should demand, and it materially qualifies the paper's
claims rather than adding a new defense.

## Recommended framing for the paper

State the ~98% result as *best-case, against an untargeted adversary*, and add
this adversary-robustness analysis as a limitation/sensitivity section:
resilience degrades gracefully for the full portfolio (to ~93% at moderate
targeting) but the single-control rankings — segmentation especially — are not
robust to a value-seeking attacker.

## Limitations

One facility/profile and one abstract targeting model (a value-weighted spread
bias, not a planning adversary); the exact percentages depend on α and the
model's mechanics. The robust, honest claim is directional and monotonic:
targeting erodes the reported resilience, and segmentation's single-control
benefit is the least robust to it.
