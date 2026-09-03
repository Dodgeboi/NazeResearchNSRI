# Validation deviations and corrections

## 2026-08-03 - diagnostic scenario pairing and time conversion

After the primary, cross-setting, and joint-stress runs were complete, the
first summaries revealed a design error limited to two diagnostics:

1. time-step variants used different scenario identifiers, so their topologies
   and entry events were not shared; and
2. the fixed detection-improvement ladder did not preserve the intended
   90-minute detection delay at a 5-minute time step.

The recovery-horizon diagnostic also used different scenario identifiers by
horizon. That was valid for separate estimates but unnecessarily weakened the
comparison.

The original diagnostic files were renamed with the suffix
`initial_design_error.csv` and retained. The diagnostics were rerun with shared
scenario identifiers. The time-step run additionally used an explicit
90-minute detection delay for both rapid-response portfolios at every step
size. No primary, cross-setting, or joint-stress row was regenerated or
changed. The manifest records this correction.

## 2026-08-03 - exploratory fine-step pilot

The corrected 5-, 15-, and 30-minute diagnostic showed material variation in
absolute modeled loss for the layered portfolio. A new 1-, 2-, and 5-minute
pilot was therefore added after seeing that diagnostic. It is explicitly
exploratory and is used only to decide whether a finer-step fresh replication
is necessary. Its seeds and rows are not pooled with the frozen 15-minute
primary analysis.

## 2026-09-03 - methodological rebuild: endpoint, capacity, and confirmation

A full forensic audit at commit `3b734df`
(`audit/baseline_forensic_report.md`, ledger at `audit/issue_ledger.csv`)
found defects severe enough that the multi-objective results could not be
repaired by re-analysis. This entry records what changed, what was
superseded, and what was **not** carried forward.

### Why re-analysis was impossible

The sustained-outage endpoint was computed as `any()` over a four-member
clinical service set — *k* = 1 — while the manuscript defined it as "at least
four clinical services", i.e. *k* = 4. It was one of six Pareto objectives,
so the inversion propagated into the frontier, the bootstrap stability
estimates, the finalist rule, the preference selections, and every reported
outage percentage. Crucially, the per-service maximum outage streak was
never persisted to raw output, so **the endpoint could not be recomputed at
any other k from the committed data**. A fresh run was the only option.

### Changes to the specification

1. **Endpoint registry.** Every reported outcome is now defined once in
   `src/grrc/endpoints.py`, and the optimizer's objective list is read from
   it rather than kept privately. `study/MODEL_SPECIFICATION.md` is the prose
   half; `tests/test_endpoint_registry.py` asserts the two agree.

2. **Sustained clinical outage.** Implemented literally as a *k*-of-*n* rule
   with the primary *k* declared in config. **Primary k = 4**, restoring the
   definition the manuscript always stated, with the full k = 1..4 ladder
   reported in every results table. The endpoint was renamed away from
   "catastrophic" because no clinical validation of the threshold exists.

   *A justification was drafted and then withdrawn.* An earlier version of
   the specification set the primary k to 2, arguing that k = 1 would
   saturate and k = 4 would be too rare to estimate. The rebuilt discovery
   bank does not support that argument. The number of qualifying clinical
   services is almost perfectly bimodal — of 12,000 paired trials, 4,189 had
   none and 7,269 had all four, with 4.5 per cent anywhere in between — so
   candidate outage probabilities differ by about three percentage points
   between k = 1 and k = 4 and the interquartile spread is identical to
   three decimals. The k choice is not load-bearing, so it was settled on
   construct grounds alone and the strictest reading was taken. Choosing a
   looser k would have moved the science closer to where the defect
   happened to sit, with no evidence for it. The withdrawn rationale is
   recorded here rather than quietly replaced.

   The bimodality is itself a model artifact and is reported as one: binary
   per-step service availability over a shared network structure yields
   all-or-nothing clinical outcomes, whereas real incidents show partial and
   staggered service loss. That is a stronger caveat on this endpoint than
   the choice of k ever was.

3. **Raw schema.** Per-service maximum outage streaks and the indicator at
   every k are now persisted, so any auditor can recompute the endpoint at
   any k and any duration threshold without rerunning a simulation.

4. **Capacity precedence.** Posture ladders are upgrade-only: a portfolio can
   raise a profile's segmentation or backup architecture but never lower it.
   Previously every enumerated candidate overwrote both, and the weakest rung
   of each ladder was priced at zero, so a high-capacity hospital could "buy"
   flat segmentation and connected backups for **zero points**. Four of the
   seven frozen high-capacity finalists in the superseded study were exactly
   such free downgrades.

5. **Costing.** Segmentation and backup are priced on the increment actually
   bought relative to the profile baseline, as patch upgrades already were.
   Exactly one zero-cost candidate now exists per profile: the profile's own
   untouched posture.

6. **Cost and burden tables gained a `periodic_backups` rung** (1 point on
   both tables). The backup ladder is now connected → periodic → isolated on
   both the mechanism and the pricing side. Without it the intermediate
   profile's own declared `periodic` architecture — which no candidate could
   name, and which therefore never ran — had no price.

7. **Enumeration.** The backup dimension enumerates all three rungs rather
   than only its endpoints, giving 288 enumerated portfolios instead of 192.
   This is what allows every resolved posture to be named honestly.

8. **Deduplication.** Candidates are now resolved under the study config
   rather than library defaults, and the surviving representative is the one
   whose declared posture matches what it actually runs. Resolved counts are
   288 / 96 / 16 for the three profiles.

### Changes to the study design

9. **Full-space confirmation.** The confirmatory frontier ranges over every
   resolved candidate, not over a discovery-selected subset. The superseded
   holdout evaluated 57 finalists and reported the result as a frontier; a
   candidate that looked mediocre in discovery could not appear, and "7 of 7
   non-dominated" in the high-capacity profile was near-inevitable with seven
   points in six dimensions. Measured throughput made the honest version
   affordable. The finalist-only frontier is retained as a *view of the same
   data*, and the number of candidates that appear efficient only because
   their dominator was never evaluated is now reported directly.

10. **Protocol freezing.** Confirmatory protocols are content-addressed
    artifacts under `study/protocols/`. A protocol's own SHA-256 is stored
    inside it, `freeze_protocol` refuses to overwrite an existing one, and
    loading recomputes the digest and raises if the file was edited. The
    runner will not start without a protocol that verifies, refuses to run if
    the resolved candidate space has changed since freezing, and stamps the
    digest into every raw row and the manifest. Previously the "frozen"
    protocol was rewritten by its own runner on every invocation and
    contained no hash, commit, or timestamp.

11. **Retrospective status of the earlier freeze.** The pre-rebuild holdout
    freeze **cannot be established from the public record**, and no claim
    that it was prospective is made anywhere in the rebuilt work. That
    analysis is described as retrospective. Only protocols frozen under the
    mechanism above support a prospective claim, and only from their freeze
    timestamp and commit forward.

12. **Provenance.** Every run and analysis writes a manifest hashing each
    consumed input and produced output, with the code commit, dirty-tree
    state, and environment. Verification recomputes hashes and **raises** on
    mismatch. Paths are recorded POSIX-relative; the superseded holdout
    manifest used Windows separators that the declared CI runner could not
    resolve.

13. **Monte Carlo error** is reported for every stochastic objective, along
    with the count of candidate pairs the scenario bank cannot reliably
    order. The scenario count is justified by a pilot precision analysis
    embedded in the frozen protocol.

### What was superseded, not deleted

All pre-rebuild multi-objective raw and processed data were moved to
`data/multiobjective/archive_pre_rebuild/` with a README stating why no
number in it may be cited. Nothing was removed.

### Known defects deliberately carried into this stage

These are named in the model specification and tracked in the ledger. They
are **not** fixed by this entry and are scheduled for WP3. Until then they
are reported as declared assumptions with the defect named:

- `patch_effectiveness` is a single 0.85 scalar applied to every pathway,
  including credential and vendor origins where patching is mechanically
  irrelevant (ISSUE-009);
- `identity_breach_multiplier` is a whole-network scalar rather than a
  coverage-dependent authentication effect (ISSUE-010);
- `backup_traversal["isolated"]` is exactly 0.0, so isolated backups cannot
  fail by any modeled mechanism (ISSUE-006). A deliberately failing test
  (`tests/test_falsification.py`, marked xfail) keeps this visible in every
  test run rather than only in a document;
- restoration is gated on complete containment, an undocumented structural
  assumption that couples the response controls to the recovery endpoint
  (ISSUE-007);
- the 72-hour horizon with the current restore rate cannot express the
  weeks-to-months recovery tail in the public record, so non-recovery is an
  artifact of the horizon rather than a recovery estimate (ISSUE-008).
