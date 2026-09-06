# Model specification, version 1 (frozen)

**Status:** frozen 2026-09-03, before the confirmatory run.
**Supersedes:** the implicit specification embedded in the code at commit
`3b734df`, which contradicted the manuscript on two endpoints.
**Authority:** where this document and the code disagree, this document is
the specification and the code is the defect. Where this document and the
manuscript disagree, the manuscript is the defect.

The machine-readable half of this specification is
[`src/grrc/endpoints.py`](../src/grrc/endpoints.py). Prose here, executable
definitions there, and `tests/test_endpoint_registry.py` asserts they agree.

---

## 0. What this model is, and what it is not

It is a **synthetic, partially calibrated, externally validated decision
model**. It exists to expose trade-offs between defense portfolios under
declared assumptions, and to be falsified against public operational
patterns.

It is **not** an estimate of any hospital's ransomware risk, nor of any
control's real-world effectiveness. No internal transition coefficient in
this model is identified by hospital data, and the specification says so at
each parameter rather than once in a limitations paragraph.

Three claims this specification forbids, because the model cannot support
them: that the model is calibrated to U.S. hospitals; that any reported
percentage is a control's effectiveness; and that any threshold in it is a
clinical threshold.

---

## 1. Entities and state

### 1.1 Network

A single synthetic facility per run. A directed graph of 200–300 nodes
representing permitted access paths among functional zones: workstations,
EHR, laboratory, pharmacy, imaging, medical devices, administration,
identity, backup, and internet-facing/vendor gateways.

Node attributes: zone, privilege class (low / standard / admin), baseline
vulnerability, legacy flag, patched flag, detection capability, clinical
criticality.

Edge attributes: access weight, strength, traversal modifier. Cross-zone
edges exist only where the segmentation architecture permits them.

**Non-identifiability, stated once and inherited by everything downstream:**
no public source gives a representative internal hospital network degree
distribution, zone topology, or per-edge access structure. The generated
graph is a declared structure, not a measured one. Node counts are *not* a
function of hospital beds; CMS facility variables may stratify scenarios but
are never mapped onto node counts without a measured correspondence.

### 1.2 Node state machine

```
HEALTHY / VULNERABLE → COMPROMISED → DETECTED → ISOLATED → RESTORING → RESTORED
```

A node is **functional** when it is neither compromised nor isolated. False-
positive isolation removes a healthy node from service for a bounded number
of steps and then returns it; this is a modeled operational cost of
aggressive automated response, not an error.

### 1.3 Services

Seven modeled services: EHR, laboratory, pharmacy, imaging, scheduling,
identity, backup/recovery.

**Clinical services** are exactly four: EHR, laboratory, pharmacy, imaging.
Scheduling, identity and backup are supporting services and never contribute
to a clinical endpoint.

A service is available at a step when at least
`simulation.service_functional_fraction` (0.60) of its supporting nodes are
functional. Availability is **binary per step**. The model therefore cannot
represent degraded-capacity operation, downtime procedures, manual
workarounds, or partial service — a limitation that must be stated wherever
service-hours are reported.

> The 0.60 fraction is a **declared assumption**. It has had no clinical
> validation. It is not a clinical catastrophe threshold and must never be
> described as one.

---

## 2. Time and transition order

One step is `simulation.step_minutes` (5 minutes in the primary study). The
horizon is `simulation.max_steps` (864 steps = 72 hours).

Within each step, in this exact order:

1. **Spread.** Each edge from an active (compromised, not isolated) node to a
   susceptible node succeeds with probability
   `base_spread_rate × privilege_modifier(source) × edge_access ×
   edge_strength × edge_traversal_modifier × vulnerability(target) ×
   patch_factor(target)`, clipped to [0, 1]. If any identity-zone node is
   compromised, every probability is multiplied by
   `identity_breach_multiplier` and re-clipped.
2. **Detect.** Undetected compromised nodes are detected with per-step
   probability `detect_capability / detection_delay` (geometric model).
3. **Isolate.** Detected nodes are isolated with probability
   `isolation_success`. Under rapid isolation, a node may be isolated in the
   same step it is detected; otherwise the first attempt is the next step.
4. **False positives.** Expired false-positive isolations are released;
   healthy nodes are falsely isolated at `false_positive_rate`.
5. **Restore.** *Only while the estate is contained* (no compromised node is
   un-isolated), nodes begin restoring in order of clinical criticality, at
   `max(restore_rate_min, restore_rate_fraction × n_nodes)` nodes per step,
   each taking `restore_duration` steps. Without available backups the rate
   is multiplied by `no_backup_restore_penalty`.
6. **Score.** Service availability is evaluated and downtime, current run,
   and longest run are updated per service.

**Structural assumption S1 (containment-gated restoration).** Step 5 runs
only when containment is complete. Real incident response restores in
parallel with containment and prioritises clinical systems. This assumption
couples the detection and isolation controls to the recovery endpoint through
a modeling choice rather than a mechanism, so it must be (a) named in the
Methods, and (b) varied in the structural sensitivity analysis. It was
undocumented before the rebuild (audit ISSUE-007).

**Early stop.** When the estate is contained, no node is compromised or
falsely isolated, and all services are available, the run terminates; the
remaining steps would add no downtime. This is an optimization, not a
modeling choice, and `steps_simulated` records where it happened.

---

## 3. Exogenous capacity versus purchased controls

This is the distinction the whole study rests on, and it is the one the
pre-rebuild code did not maintain.

### 3.1 Capacity profiles are exogenous

A **capacity profile** describes the environment a decision-maker inherits:
starting patch coverage, detection delay, isolation success, legacy fraction,
baseline segmentation architecture, baseline backup architecture, and a
normalized budget.

Profile names (`resource_constrained`, `intermediate_capacity`,
`high_capacity`) are **neutral scenario labels**. They are not observed
hospital classes, and no claim is made that any real hospital occupies any of
them.

### 3.2 Portfolios are additive upgrades

A **portfolio** is a bundle of purchased decisions layered on top of a
profile. Six composable dimensions:

| Dimension | Options |
|---|---|
| Segmentation | flat → basic → least-privilege |
| Patch coverage | +0 to +3 rungs on the ladder 25% → 50% → 75% → 90% |
| Detection | baseline or improved |
| Isolation | baseline or rapid same-step |
| Backup architecture | connected → periodic → isolated |
| Identity controls | absent or present |

Cartesian product: 3 × 4 × 2 × 2 × 3 × 2 = **288 enumerated portfolios**.

### 3.3 Precedence rule (frozen)

> **Posture ladders are upgrade-only.** For segmentation, backup, patch
> coverage, detection delay and isolation success, the effective setting is
> the stronger of the profile's baseline and the portfolio's declared target.
> A portfolio can never move a profile down a ladder.

Explicit overrides (`patch_coverage_override`, `detection_delay_override`,
sweep overrides) are exempt, because they are analysis instruments — stress
tests and convergence checks — not purchasable decisions. **No enumerated
optimizer candidate uses them.**

**What this fixes.** Before the rebuild, every enumerated candidate set both
segmentation and backup, and the portfolio value won unconditionally. Since
the cost table charged nothing for the weakest rung of each ladder, a
high-capacity hospital could "buy" flat segmentation and connected backups
for **zero points**, and four of the seven frozen high-capacity finalists
were exactly such free downgrades. The intermediate profile's declared
`periodic` backup architecture was unreachable by any candidate and never
ran. Environmental capacity and purchased controls were not separated at all
(audit ISSUE-003, ISSUE-004, ISSUE-005).

### 3.4 Costing rule (frozen)

> **A portfolio is priced on the rungs it actually buys**, relative to the
> profile's baseline, on both the cost and the burden tables.

Absolute ladder points, with the weakest rung as origin:

| Ladder | Rungs and points |
|---|---|
| Segmentation | flat 0 → basic 3 → least-privilege 5 |
| Backup | connected 0 → periodic 1 → isolated 2 |
| Patch | 2 points per rung gained |
| Detection | 3 (flat) |
| Rapid isolation | 5 (flat) |
| Identity controls | 4 (flat) |

Increment = max(0, points[target] − points[baseline]). A downgrade therefore
costs zero rather than refunding, and a profile is never charged for a rung
it already has.

Consequences, all intended and all reported:

- Exactly **one zero-cost candidate per profile**: the profile's own
  untouched posture. This is asserted by
  `tests/test_capacity_precedence.py::test_exactly_one_zero_cost_candidate_per_profile`.
- Resolved candidate counts fall to **288 / 96 / 16** for the three profiles.
  The high-capacity count is small because that profile already owns
  least-privilege segmentation and isolated backups; only patch, detection,
  isolation and identity remain as decisions. That is the honest size of its
  decision space.
- **Cost and burden are normalized scenario points.** Not dollars, not staff
  hours, not comparable across studies. Every output column, table and figure
  caption says so.

---

## 4. Endpoint registry

Definitions are authoritative in `src/grrc/endpoints.py`. Summarized:

| Endpoint | Direction | Identification class |
|---|---|---|
| Mean weighted service-hours lost | minimize | model-internal |
| Tail disruption (CVaR90) | minimize | model-internal |
| Sustained clinical outage | minimize | declared-assumption |
| Non-recovery at horizon | minimize | model-internal |
| Implementation cost points | minimize | normalized-scenario-unit |
| Operational burden points | minimize | normalized-scenario-unit |
| Defensive isolation node-hours per node | diagnostic | model-internal |

The first six are the Pareto objectives. The seventh is reported but is not a
dominance dimension.

### 4.1 Sustained clinical outage — the frozen decision

**Definition.** A trial meets the endpoint when at least *k* of the four
clinical services each experienced a continuous unavailability run of **more
than** `sustained_outage_service_steps` steps (24 steps × 5 min = 2 hours in
the primary study).

**Primary k = 4, matching the definition the manuscript always stated. The
full ladder k = 1, 2, 3, 4 is reported in every results table.**

Two properties of the rule, both deliberate:

- The comparison is **strict**, so the threshold is the longest outage that
  does *not* qualify. This matches "more than two modeled hours".
- Qualifying runs are **not required to be concurrent**. Each service is
  scored on its own longest outage over the horizon. A concurrency
  requirement would need per-step service states retained for every trial,
  which the raw schema does not carry. The weaker reading is used and is
  stated wherever the endpoint appears.

**What went wrong before.** The manuscript defined the endpoint as "more than
two modeled hours of continuous unavailability in at least four clinical
services". Because the clinical set has exactly four members, that is *all
four*. The implementation used `any()` — *k* = 1. The endpoint was one of six
Pareto objectives, so the inversion propagated into the frontier, the
bootstrap stability estimates, the finalist rule, the preference selections,
and every reported outage percentage. The 70-test suite passed before and
after the definition was corrected (audit ISSUE-001, ISSUE-020).

**Why k = 4, and a withdrawn justification.** An earlier draft of this
specification set the primary k to 2, arguing that k = 1 would saturate near
0.95 and k = 4 would be too rare to estimate. **The rebuilt discovery bank
does not support that reasoning, and it is withdrawn.**

The subsequent claim that k has uniformly small effects is also withdrawn.
The candidate-average confirmation frequency changes from k=1 to k=4 by
3.87, 12.60 and 14.34 percentage points in the resource-constrained,
intermediate and high-capacity profiles. Their frontier membership responds
differently: both stronger profiles retain the same estimated frontier.

For identical observations and weights, the k=1 minus k=4 frequency equals
the fraction with one to three qualifying services. Pooled discovery values
cannot establish profile-specific confirmation behavior. See
`data/interpretation/endpoint_by_stage_profile.csv`,
`data/interpretation/pooling_comparison.csv` and the revised manuscript.

Primary k=4 remains a declared construct choice, not a clinically validated
threshold. Binary service availability and shared dependencies limit what
the endpoint can represent, separately from its sensitivity to k.

**Where the endpoint has no discriminating power.** In the high-capacity
profile the endpoint is identically zero at every k ≥ 2 across all 16
resolved candidates, and 0.067 for every candidate at k = 1. It contributes
nothing to dominance in that profile, and the manuscript must say so rather
than presenting six live objectives everywhere.

**Recomputability requirement.** Per-service longest outage runs are
persisted in raw output (`<service>_max_outage_streak_steps`), together with
the indicator at every k. An auditor can recompute the endpoint at any k and
any duration threshold without rerunning a single simulation. The pre-rebuild
schema discarded the streak entirely, so the endpoint could not be checked at
all (audit ISSUE-002).

### 4.2 Recovery — known inadequacy, scheduled for WP3

`nonrecovery_probability` is right-censored technical recovery at 72 hours.
It is **not** organizational recovery and **not** return to normal clinical
operations.

The current restore rate (`restore_rate_fraction` 0.0067 × ~250 nodes ≈ 1.67
nodes/step, floor 0.333) implies a ~250-node estate restores in roughly 12.5
hours once contained. The public record has a substantial weeks-to-months
tail: mean reported disruption of 15.8 days in the THREAT cohort, with 16 of
374 events exceeding four weeks. **A 72-hour horizon with this rate cannot
express the observed tail at all**, so non-recovery is currently an artifact
of the horizon rather than a recovery estimate (audit ISSUE-008).

The specification therefore requires, and WP3 will implement, separate
observable recovery layers: acute service availability over 0–72 hours,
minimum viable operations over 0–21 days, full organizational recovery over
0–90 days, and a prespecified tail scenario to 180 days, with incident-level
recovery represented as an interval-censored class model rather than inferred
from a constant per-node restore rate. Until then, every reported
non-recovery figure carries the horizon caveat explicitly.

---

## 5. Parameter identification

Every parameter carries an identification class. The full register is
`study/PUBLIC_EVIDENCE_PARAMETER_REGISTER.csv`.

### 5.1 Evidence-constrained or externally validated

Incident-level disruption and recovery classes; multi-facility breadth; entry-
vector families as named scenarios; facility context; control **adoption**
prevalence; backup outcome classes; patient-flow trajectories used as
external validation targets.

### 5.2 Not publicly identifiable — declared assumptions or stress ranges

Per-edge internal transmission; universal patch effectiveness; representative
internal degree and topology; segmentation multiplier; isolation success per
step; identity-compromise spread multiplier; isolated-backup traversal; node
restoration throughput; clinical service thresholds and weights; false-
positive isolation incidence and duration; control-specific capital and
workflow costs.

CISA KEV, NIST, HHS and CISA guidance may justify a **mechanism** or a
scenario structure. They are never cited as estimating any of these values.

### 5.3 Known misuses in the current implementation, scheduled for WP3

| Parameter | Defect | Required treatment |
|---|---|---|
| `patch_effectiveness` = 0.85 | A single scalar reduces compromise probability by 85% on every patched node against **every** pathway, including credential and vendor origins where patching is mechanically irrelevant. On the red-line list; unsupported by any cited source (ISSUE-009). | Exploit-specific susceptibility removal, or a deliberately broad uncertainty distribution explicitly labeled an assumption. |
| `identity_breach_multiplier` = 1.5 | Applied as a whole-network scalar on every edge (ISSUE-010). | Confine identity effects to eligible authentication pathways with explicit coverage, unenrolled accounts, service accounts, legacy protocols, and token/session theft. |
| `backup_traversal["isolated"]` = 0.0 | Isolated backups **cannot fail by any modeled mechanism**. On the red-line list ("backup isolation eliminates compromise"). Sophos 2024 reports backup compromise attempted in 95% of healthcare victims and succeeding in 66% of attempts (ISSUE-006). | Nonzero residual failure with a prespecified uncertainty range; non-network failure modes remain possible; isolation is a rung, not a guarantee. |

Until WP3 lands, these are reported as declared assumptions with the defect
named, not as calibrated values.

---

## 6. Invariants

Asserted by the test suite; a violation is a defect, not a finding.

**Endpoint invariants**
1. The sustained-outage indicator is monotone non-increasing in k.
2. A run of exactly the threshold does not qualify; one step more does.
3. Non-clinical services never contribute to a clinical endpoint.
4. A per-service longest run never exceeds the steps actually simulated.
5. The deprecated `catastrophic` alias equals the indicator at the primary k.

**Capacity invariants**
6. No candidate weakens any profile posture on any ladder.
7. Exactly one zero-cost candidate exists per profile: the profile's own.
8. A zero-cost portfolio contains no positive-cost control.
9. Cost is monotone in ladder position; a downgrade is never refunded.
10. A candidate's label matches the posture it actually resolves to.
11. Deduplication resolves under the study config, not library defaults.

**Design invariants**
12. Identical seeds and configs reproduce identical raw results.
13. Relabeling portfolios does not change results.
14. Candidate ordering does not change the Pareto frontier.
15. Adding a dominated candidate removes no existing non-dominated candidate.
16. Paired comparisons share the underlying stochastic draws.
17. A frozen protocol cannot be rewritten by any runner.
18. Every consumed input and produced output is hashed in a manifest, and
    reproduction **fails** on mismatch rather than continuing.

**Falsification checks**
19. With transmission zero, no secondary compromise occurs.
20. Raising a control's coverage never applies it to ineligible assets.
21. Recovery endpoints cannot occur in an impossible order.
22. Full-space and finalist-only frontiers differ in a constructed fixture
    where they should.

---

## 7. Study design

### 7.1 Stage separation

| Stage | Purpose | May inform later stages? |
|---|---|---|
| Development | tests, pilots, debugging | yes |
| Discovery | precision estimation, sensitivity, candidate labels | yes, and it is labeled non-confirmatory everywhere |
| **Frozen protocol** | design fixed, content-addressed, before any confirmatory data exist | it *is* the commitment |
| Confirmation | full-space evaluation on a fresh paired bank | no; cells are never selectively rerun |
| External validation | comparison against frozen benchmark targets | no; targets are never tuned against |

### 7.2 Full-space confirmation (frozen)

> **The confirmatory frontier ranges over every resolved candidate in each
> profile, not over a discovery-selected subset.**

The pre-rebuild holdout evaluated 57 discovery-selected finalists and
presented the result as a frontier. A candidate that looked mediocre in
discovery and excellent on fresh scenarios was structurally unable to appear,
and "7 of 7 non-dominated" in the high-capacity profile was close to
arithmetically inevitable with seven points in six dimensions (ISSUE-012).

Measured throughput (162 ms/trial) makes the honest version affordable, so
the fix is to compute the true frontier rather than rename the restricted
one. Because the finalists are a subset, the finalist-only frontier is then a
**view of the same data**, and `restricted_frontier_comparison` reports
directly how many candidates appear efficient only because their dominator
was never evaluated — the quantity the earlier study could not report.

Candidate counts are stated at every stage: enumerated, resolved, evaluated,
non-dominated.

### 7.3 Protocol freezing

A protocol is written by `scripts/freeze_confirmatory_protocol.py` to
`study/protocols/<name>.protocol.json`. Its own SHA-256 is computed over its
canonical JSON and stored inside it. `freeze_protocol` **refuses to overwrite
an existing protocol**; `load_frozen_protocol` recomputes the digest and
raises if the file has been edited since. The confirmatory runner will not
start without a protocol that verifies, refuses to run if the resolved
candidate space has changed since freezing, and stamps the protocol digest
into every raw row and the run manifest.

**Honest statement about history.** The pre-rebuild holdout freeze cannot be
established from the public record, and this specification does not claim it
can. The earlier analysis is described as retrospective. Only the protocol
frozen under the mechanism above supports a prospective claim, and only from
its freeze timestamp and commit forward.

### 7.4 Uncertainty

Five sources are distinguished and reported separately: aleatory event
variation; parameter uncertainty; structural uncertainty (including S1);
evidence/source uncertainty; and Monte Carlo error.

Paired common random numbers are used for every portfolio comparison. Monte
Carlo standard error is reported for every objective. The number of scenarios
is justified by a pilot precision analysis, not by a round number; where a
round number is used, the manuscript says so plainly.

---

## 8. Human decisions this specification does not make

Flagged for the authors, per the handoff. These are not defaults Claude may
choose:

- target journal and fallback;
- author list, order, affiliations, CRediT contributions, corresponding
  author;
- availability of clinicians, hospital security experts, or non-public
  telemetry, which is the only route from partial to genuine calibration;
- whether to add multi-facility and regional modeling or to narrow the paper
  explicitly to a single synthetic facility;
- acceptable compute budget and deadline;
- licensing for new code and data artifacts;
- conflicts of interest, funding, ethics/IRB determination, and the AI-use
  disclosure required by the target journal;
- whether the paper stays purely methodological or makes a stronger applied
  claim, which would require external collaborators.

---

## 9. Change control

This is version 1. Any change to a definition in Section 4, a rule in
Section 3, or a design commitment in Section 7 requires a new version number,
an entry in `study/DEVIATIONS.md` stating what changed and why, and a new
frozen protocol under a new name. Results generated under version 1 are never
silently reinterpreted under a later version.
