# Reactive ("just-in-time") segmentation: when it beats always-on segmentation

*A follow-on experiment using the GRRC simulator. All numbers below are
produced by `python scripts/discover_adaptive_segmentation.py --trials 150`
(master seed 20260713); the raw per-trial rows are in
`outputs/adaptive/adaptive_segmentation_raw.csv` and the cell summary with
bootstrap confidence intervals in
`outputs/adaptive/adaptive_segmentation_summary.csv`.*

## The idea

The main study treats network segmentation as a **static** posture chosen at
`t = 0`, and — importantly — its engine charges segmentation **no operational
cost**: lowering cross-zone spread never removes a node from service. Real
segmentation is not free. Cutting cross-zone paths breaks the cross-zone
clinical workflows that keep services usable, so a permanently locked-down
network pays an ongoing availability cost even when no attack is underway.

Once that cost is represented, a question the static model cannot answer
appears:

> Is it better to run **permanently segmented** (always protected, always
> paying the operational cost), or to run **open** and engage segmentation
> **reactively**, only once an intrusion is detected (paying the cost only
> during an incident, but risking that the attacker has already spread by the
> time you react)?

We call the second policy **reactive segmentation**. This note characterizes
exactly when it wins.

## Method (what is held equal)

Three postures are compared on **identical networks and identical random
streams** — the only difference between them is the segmentation policy:

* **open** — never segment (full cross-boundary spread, no operational cost).
* **static** — always segment (cross-boundary spread clamped to the
  least-privilege modifier `0.25` every step; operational cost paid every
  step).
* **reactive** — start open; engage segmentation when the number of *detected*
  active compromises reaches a trigger (the controller sees only detections,
  never ground truth); disengage after the incident has been observably quiet
  for 6 steps.

The operational cost is a single knob, `cost_frac` — the fraction of non-core
clinical supporting nodes whose cross-zone workflow is broken (treated as
unavailable) **while segmentation is engaged**. It flows through the engine's
normal service-availability accounting, so it lands directly in the study's
primary metric, weighted service-hours lost.

Grid: facility `regional_hospital`, profile `intermediate_capacity`,
detection delay ∈ {1, 2, 3, 6, 12, 24} steps, `cost_frac` ∈ {0, 0.15, 0.30,
0.45}, 150 matched trials per cell (10,800 simulations). The core engine is
untouched: the three extension seams added to `propagation.py` are exact
no-ops for the base class, and the 50 unit tests and 12 validation checks
still pass unchanged.

## Result: reactive wins only in a specific corner

Reactive segmentation is **not** a general improvement. Across the 24 cells it
is the point-estimate winner in 6, and it beats **both** other postures with a
95% bootstrap CI clear of zero in **3** — a narrow, well-defined region:

| detection delay | cost 0.45: open | static | reactive | reactive − best static (95% CI) |
|---|---|---|---|---|
| 1 | 10.3 | 55.0 | **6.5** | −2.4 [−4.4, −0.6] |
| 2 | 35.2 | 57.0 | **11.0** | −16.0 [−20.0, −11.7] |
| 3 | 58.5 | 62.1 | **26.7** | −15.0 [−20.7, −9.7] |

(Weighted service-hours lost, means over 150 matched trials.)

The win requires **two conditions at once**:

1. **Fast detection relative to spread.** Reactive only helps if it engages
   before the attack saturates. Engagement timing shows why: at delay 1 the
   controller engages at step ~2 and releases after ~10 steps; at delay 24 it
   engages at step ~7 but stays locked down ~177 of 192 steps — it reacts too
   late to contain, so it pays the full operational cost *and* still absorbs
   near-open damage. Beyond delay ~3, reactive loses to static in every cell.

2. **Operational cost high enough to actually degrade service.** Because a
   service stays available until fewer than 60% of its supporting nodes are
   functional (`service_functional_fraction = 0.60`), a `cost_frac` of 0.15 or
   0.30 is nearly invisible — static segmentation is almost free, so it wins.
   The static posture only becomes genuinely expensive at `cost_frac = 0.45`,
   which pushes services past the availability threshold (e.g. static's mean
   jumps to 55–62 hours at fast detection, worse even than staying open).
   That threshold crossing is where reactive's "pay only during incidents"
   advantage finally dominates.

In the winning corner, reactive captures most of segmentation's protection
(vs. `open`) while avoiding most of its standing operational cost (vs.
`static`): at delay 2 / cost 0.45 it loses 11.0 hours versus 35.2 for open and
57.0 for static.

See `outputs/adaptive/adaptive_segmentation_phase.png` for the full
blue-wins-red-loses map.

## Honest limitations

* **The result is conditional, not a universal recommendation.** In the
  baseline-plausible regime (segmentation cheap, detection not extremely fast)
  always-on segmentation is as good or better. Reactive segmentation is a
  situational tool, valuable specifically where permanent segmentation is
  operationally disruptive *and* detection is fast.
* **The cost model is threshold-shaped, by construction of the engine.** The
  0.60 availability rule makes segmentation's cost bite abruptly rather than
  smoothly; the exact `cost_frac` at which reactive overtakes is therefore a
  property of that rule, not a calibrated real-world value. The *shape* of the
  finding (a two-condition crossover) is robust; the precise numbers are not
  claims about any real hospital.
* **One facility/profile.** The crossover boundary will move with spread rate,
  network size, and isolation quality; those are natural next axes.
* **Reactive defense is gated by detection.** The controller can only act on
  what it detects, so everything here inherits the detection model's
  assumptions.

## Why this is a contribution

The main study concludes that segmentation is one of the strongest single
controls. This experiment adds a dimension it could not see: **the *timing* of
segmentation is itself a design choice with a quantifiable payoff boundary.**
Reactive segmentation is not free insurance — it is a specific bet that pays
off only when you can detect fast and when standing segmentation genuinely
hurts operations. Characterizing that boundary (and showing that outside it
the simple static posture wins) is a more actionable message than "segment
more."
