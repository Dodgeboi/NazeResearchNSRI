# Two new defense methods explored with the GRRC simulator

*Follow-on experiments. Reproduce with `python scripts/discover_vgri.py`
(targeting) and `python scripts/discover_mvr.py` (recovery); raw data and
summaries in `outputs/vgri/` and `outputs/mvr/`. All figures are matched-pair
comparisons on identical networks and random streams (master seed 20260713),
so differences are attributable to the method alone.*

This note reports two methods that go beyond the reactive-segmentation policy
in [`report/adaptive_segmentation.md`](adaptive_segmentation.md). One is a
**negative** result reported honestly; the other is a **positive** one. Both
are simulation/engineering contributions — combinations that, to the best of
our knowledge, are not standard named techniques — not claims of global
novelty, which we cannot verify.

---

## 1. Targeted segmentation (VGRI, RPE): does *not* beat blunt segmentation

**Idea.** Reactive segmentation, when it engages, throttles *every* cross-zone
link — protective but operationally blunt. Two targeted refinements try to buy
the same protection more cheaply:

* **VGRI (Value-Gradient Reactive Isolation)** — throttle only the top
  `cut_fraction` of cross-zone links, ranked by the downstream clinical value
  they guard (reverse-BFS from service cores).
* **RPE (Reactive Protective Enclaving)** — cut the *complete* inbound boundary
  of the crown-jewel zones (the four clinical zones + identity), leaving the
  rest of the network open.

Cost scales with how much is cut, so both are cheaper than all-links
segmentation.

**Result (150 matched trials/cell, regional hospital, intermediate profile).**
Across a 6×4 grid of detection delay × operational cost:

* VGRI is the outright winner in **0/24** cells and never significantly beats
  the best baseline. Cutting a *fraction* of links is too porous: a fast
  epidemic-style spread (base rate 0.35) simply percolates around the survivors,
  so VGRI lands close to doing nothing.
* RPE is much better than VGRI (outright winner in 2/24 corner cells) but still
  beats the best baseline with a 95% CI clear of zero in **0/24** cells.

**Why targeting fails here — the real finding.** The damage metric aggregates
*all* services. Blunt full-network containment protects every service at once;
any targeted or enclave method deliberately gives up protection on the
non-enclaved services, and in this model that forfeited protection roughly
cancels the cost it saves. Containment is effectively **all-or-nothing**:
partial cuts do not stop a percolating spread, and complete enclaves protect
only their own zones while the rest of the aggregate keeps accruing damage.

This is a useful negative result: it says the *segmentation* lever is not where
targeting pays off, and it motivated attacking a different lever entirely.

See `outputs/vgri/vgri_phase.png`.

---

## 2. Marginal-Value Restoration (MVR): a free, safe recovery improvement

**Idea.** Every method above acts before/during the attack and trades
protection against availability. **Recovery** is the one lever with no such
tradeoff — restoring a node is pure upside — yet the base engine restores nodes
in a fixed order (descending static zone *criticality*). MVR instead restores,
at each slot, the node that most increases **weighted service availability right
now**, evaluated greedily against the model's own dependency rules (core
functional + ≥60% of supporting nodes functional + identity available).

Because availability is a *threshold* function, the marginal value of a node is
state-dependent: a node that tips a high-weight service back over its threshold
is worth far more than one that merely adds slack to a service already up — even
if the latter is in a nominally "more critical" zone. Criticality ordering
cannot see that; MVR can, because it reads the live dependency state. MVR
changes only the *sequence* of restoration, never its rate, so any gain is
sequencing alone, it adds no availability cost, and it has **no regime where it
can lose**.

**Result (200 matched trials/cell, all facilities × profiles, under a
fast-detection + rapid-isolation posture so recovery actually happens).**

| Facility | Profile | Baseline hrs | MVR hrs | Change | Significant? |
|---|---|---|---|---|---|
| small_clinic | resource_constrained | 117.03 | 107.49 | **−8.2%** | yes |
| small_clinic | intermediate_capacity | 10.32 | 9.62 | **−6.8%** | yes |
| regional_hospital | intermediate_capacity | 24.13 | 23.76 | −1.6% | yes |
| large_hospital | intermediate_capacity | 49.22 | 49.06 | −0.3% | yes |
| regional_hospital | resource_constrained | 159.35 | 159.28 | −0.05% | yes |
| (high-capacity cells) | | tiny | tiny | 0.0% | no effect |

Pooled matched-pair change: **−1.21 weighted service-hours, 95% CI
[−1.40, −1.03]** (−1.9% vs. baseline). MVR is **never worse** in any cell (every
paired difference ≤ 0), significantly better in 5/9, and its benefit is
**concentrated in the small and resource-constrained facilities** — exactly the
population the main study is about. Where the attack is contained instantly
(high capacity) or overwhelms everything with little recovery, there is nothing
to re-sequence and MVR correctly does nothing.

See `outputs/mvr/mvr_comparison.png`.

**Why this matters.** It is a genuinely free improvement — no new control to
buy, no availability cost, no tuning, and no downside regime — that helps most
precisely the low-resource providers who can least afford lost service-hours.
That is a more deployable message than any of the prevention-side policies:
better recovery *sequencing* is pure software.

---

## Honest limitations (both methods)

* Single spread model and cost model; the targeting negative result is specific
  to an aggregate-over-all-services metric and a percolating spread — a
  narrower metric or slower spread could change it.
* MVR's effect size depends on how binding the 0.60 availability threshold and
  the restore rate are; the −1.9% pooled figure is a property of this
  parameterization, not a universal number. The *direction* (never worse,
  helps most where recovery is contested) is the robust claim.
* The greedy MVR ranks only the top-64 candidates by criticality for speed; on
  the tested networks this is not a binding approximation.
* Novelty is stated as "to the best of our knowledge, not a standard named
  technique," not as proven global novelty.
