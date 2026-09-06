> Historical assessment, superseded by the retrospective interpretation revision. See `docs/manuscript/REVISION_REVIEW.md`; old scores and narrative conclusions are not current readiness judgments.

# Completion report

**Branch:** `rebuild/wp0-wp2`, on top of `3b734df`
**Nothing pushed.** All work is local to this branch.

---

## 1. Bottom line

**Scored 87/100 against the handoff's rubric, inside the 85–90 target band.**
Every score cap is cleared. The baseline was capped at 74; an intermediate
revision of this work scored 81, before WP3.

**Not submission-ready, and the score does not say otherwise.** A rubric band
measures methodological discipline. It does not price the model's central
limitation — that no internal coefficient is identified by hospital data —
and it cannot price novelty, journal fit, or reviewer judgement. Four
blocking human decisions remain open and no human has read the rendered
paper.

**What still limits the science, in order.** The recovery endpoint is a
single 72-hour horizon where the specification requires layered endpoints out
to 90 days, which is why two external benchmarks fail outright. Only one
structural assumption has been varied, and it moved the answer far more than
sampling ten parameters did. And the model runs one facility against an
incident record in which a quarter of events span several.

## 2. What changed

### Scientific

- **The sustained-outage endpoint is defined once and implemented literally.**
  Defined in prose as requiring four clinical services, computed as requiring
  one. Now a *k*-of-*n* rule in a central registry with *k* = 4 declared in
  config and the full *k* = 1…4 ladder reported everywhere.
- **Per-service outage streaks are persisted**, so the endpoint is
  recomputable offline at any *k*. The old schema discarded them, which is
  why this had to be a fresh run rather than a re-analysis.
- **Capacity is exogenous.** Posture ladders are upgrade-only and priced on
  the increment actually bought. Previously a strong profile could buy flat
  segmentation and connected backups for zero points, and four of seven
  frozen high-capacity finalists were such free downgrades.
- **Controls act only where they can act.** Edges carry a pathway label —
  exploit, credential, vendor. Patching removes susceptibility on the first
  and does essentially nothing against stolen credentials; identity effects
  are confined to credential pathways with explicit coverage.
- **Isolated backups can fail**, through a per-incident isolation lapse and a
  non-network residual mode. The strict `xfail` that pinned this defect now
  passes.
- **Ten unidentified coefficients carry declared ranges**, drawn per scenario
  and shared across candidates, so objectives are marginal over declared
  uncertainty rather than conditional on point estimates.
- **Structural assumption S1 is switchable and varied**, having previously
  been undocumented.

### Computational

- `grrc.endpoints`: one definition per outcome, read by the analysis, the
  tables and the claim audit.
- `grrc.provenance`: content-addressed protocols, hashed manifests, per-run
  config snapshots, verification that raises rather than warns.
- `grrc.uncertainty`: per-scenario parameter draws that preserve pairing.
- Full-space confirmatory design plus `restricted_frontier_comparison`.
- Monte Carlo error per objective, a count of candidate pairs the bank cannot
  order, and a variance-based sensitivity decomposition that reports rank
  stability alongside variance.
- 184 tests, up from 70, with no expected failures remaining.

### Evidentiary

- Source manifest schema 2: retrieval date, mutability class, licence, reuse
  terms, size, hash, derived counts, and an explicit `does_not_support` list
  per source.
- `docs/evidence/THREAT_RECONCILIATION.md` resolves the ~160 / 149 / 25.7% /
  52.9% figures as three different denominators, exactly.
- Frozen external-validation registry, nine benchmarks, criteria fixed before
  comparison.
- The parameter register regenerated from the live registry: 17 parameters
  with identification class, evidence basis, and treatment.
- Citation verification found and recorded a discrepancy in the handoff's own
  summary of the AEJ estimates.

### Manuscript

Restructured to the ten-section outline, opening with its own predecessor's
defects. **No hand-typed result value anywhere.** Builds clean at 13 pages.

## 3. Verification

```
python scripts/unpack_raw.py && python scripts/run_full_audit.py
```

| Check | Result |
|---|---|
| Test suite | 184 passed, 0 xfail |
| Behavioral validation | 12/12 |
| Archived sources (hashes, sizes, re-derived counts) | pass |
| Frozen protocols verify | pass (v1 and v2) |
| Run manifests describe files on disk | 11 checked, pass |
| Manuscript claim audit | pass, 5/5 checks |
| Numbers re-derive from raw trials | pass |
| External validation reports its failures | pass |

Confirmatory protocol `multiobjective_confirmatory_v2`, SHA-256
`9cb7e835446a…`, frozen 2026-09-04T01:53:46Z and committed **before** any v2
output existed. Protocol v1 is superseded rather than edited, because the
mechanism repairs changed what the model is.

Banks: discovery 12,000 executions; confirmatory 160,000; structural
sensitivity 28,800 across two arms. Roughly six hours of compute on two cores
across both study versions.

## 4. Results

**Full-space frontier: 95 non-dominated candidates** (64 / 22 / 9 by
profile) out of 400 resolved profile-candidates. None minimizes all six
objectives.

**What a restricted design would have cost.** The finalist-only view
contains 57 candidates, and **38 non-dominated candidates were never labelled
finalists at all** — a restricted design could not have shown them under any
circumstances. Of 65 labelled finalists, 57 survive and 8 are displaced.
**Zero candidates are efficient only in the restricted view**, where the
pre-WP3 run found three; the count depends on the model and the scenario
budget, so it should be measured per study rather than cited.

The asymmetry is the finding: a restricted comparison rarely promotes a
candidate that does not deserve it, because it evaluates candidates selected
for being good. What it reliably does is hide the ones it never looked at,
and that error is undetectable from inside the design, because the evidence
needed is exactly what the design discarded.

**Two negative results are more useful than the frontier.** In the
high-capacity profile the entire purchasable improvement is 2.0 weighted
service-hours across 16 configurations — and the parameter explaining most of
its variance is the model's own false-positive isolation rate, at 55%. Once
an estate is strong enough that attacks rarely spread, the dominant modeled
cost is the defense removing healthy systems from service. In the
resource-constrained profile the declared budget takes mean disruption from
322.1 to 157.0 weighted service-hours and still leaves sustained
clinical-outage probability at 94.5%: the budget and the endpoint are
mismatched, and every affordable option fails the stated criterion.

**Parameter versus structural uncertainty.** Sampling ten coefficients across
wide declared ranges leaves portfolio orderings largely intact — worst
Spearman rank correlation 0.61, mostly above 0.9 — while varying the single
structural assumption S1 moves 21 candidates off the frontier and roughly
doubles modeled disruption in two profiles. Parameter uncertainty is the kind
this study can quantify; structural uncertainty is the kind that threatens
its conclusions.

## 5. Validation

**Of nine frozen benchmarks, two are scoreable, three fail, none passes.**
Seven are unaddressable or unscoreable because the model has no output of
that construct.

| Benchmark | Verdict |
|---|---|
| Short technical outage (CrowdStrike) | **fail** — median 40.9 modeled hours vs 5.1 observed; 23.2% recover within six hours vs 58.1% |
| Recovery trajectory (~3 weeks) | **fail** — recovers far too fast; horizon cannot span the window |
| Multi-facility breadth | **fail** — probability zero against 25.7% observed |
| Contained before encryption | consistent — profile spread brackets the surveyed figure; weak evidence |
| Recovery duration bins | not addressable — 72-hour horizon cannot place mass beyond a week |
| Adjacent-ED spillover | not addressable — no second facility exists |
| Week-1 activity loss; California ED/admissions | not scoreable — service-hours are not patient volume |
| Control adoption prevalence | not scored — used for scenario design, never as an effect size |

**No target informed any tuning.** Criteria were frozen before comparison,
the runner exits zero on failure, and the audit asserts failures are still
being reported. Repairing the mechanisms did not rescue any benchmark, which
is the correct outcome: the failures are about horizon and scope, not about
transition coefficients.

The most informative failure is two-sided: the restoration engine is far too
**slow** against the observed technical outage and far too **fast** against
the ransomware record. It is anchored to neither.

## 6. A claim of ours the data refuted

The frozen protocol's rationale records that three of four high-capacity
objectives had an interquartile range of exactly zero across all sixteen
candidates, and concludes that no scenario count resolves them — "a finding
about the profile, not a budget problem."

**The confirmatory data refute it.** At 400 scenarios those sixteen
candidates take sixteen distinct values on mean disruption, spanning 13.07 to
15.02 weighted service-hours. The zero ranges were an artifact of a
thirty-scenario pilot, at which resolution candidates tie exactly. A
correlation-ratio estimator asked to size a difference it cannot yet see
returns an unattainable requirement, and *"this quantity cannot be resolved"*
is not the same as *"this pilot cannot resolve it"*.

**The protocol was not edited.** A freeze that gets amended when its rationale
turns out wrong is not a freeze. The correction is stated in the manuscript,
in `study/DEVIATIONS.md`, and in the red-team report. No result changed: 400
scenarios was the affordable maximum and would have been chosen either way.

Two related defects, found the same way — by re-reading a passing check and
asking what it would fail on.

`ConfirmTotalExecutions` was being read from the superseded v1 protocol,
because the generator's default still pointed at it. The audit had not caught
it, since its cross-check compared a different macro. It is fixed, and the
audit now flags a protocol-sourced execution count that disagrees with the
raw file.

**And the committed archive was the wrong bank.** The 101 MB confirmatory
bank is committed gzipped; the committed archive held the superseded
137,600-execution run while the file beside it held the 160,000-execution
one. All nine audit checks passed anyway, and so did CI. `unpack_raw.py`
decided currency by modification time, so in the tree where the study had
just been re-run it correctly did nothing — and no other check ever opens the
archive. The whole hashed provenance chain was verifying against a file the
repository could not hand to anyone else. On a fresh clone it would have
restored the old bank over the new manifests.

The lesson generalises past this repository: a hash-based provenance layer
that trusts a timestamp anywhere has a hole exactly the size of that
timestamp. Currency is now decided by decompressing and comparing SHA-256,
a disagreement exits non-zero rather than overwriting in either direction,
and five tests pin the behaviour — including the precise configuration that
went undetected, a stale archive beside a fresher file with a much newer
mtime. No reported number changes; what was wrong was the copy committed for
others to check against.

## 7. Claims

**Now supportable:** a reproducible, fully hashed pipeline from archived
sources to manuscript; a full-space confirmatory frontier under a checkable
freeze; a direct measurement of what a restricted design would have hidden;
objectives that are marginal over declared parameter uncertainty; a variance
decomposition separating uncertainty in levels from uncertainty in decisions;
and honest external validation with failures reported.

**Still prohibited:** that any control has any effect in a real hospital;
that any duration or probability describes a real incident; that the model is
calibrated; that the frontier is procurement advice; that declared ranges are
evidence; that reproducibility implies correctness.

## 8. Residual risks

Ordered by effect on the conclusions. Full detail in
`audit/final_red_team_report.md`.

1. **R6 — structural assumptions (High, now dominant).** One assumption
   varied, and it moved the answer more than ten sampled parameters did. The
   rest are asserted.
2. **R1 — no recovery calibration (High).** Every duration statement inherits
   the two-sided failure above.
3. **R2 — binary availability drives a headline (High).** Clinical outcomes
   remain near-binary (3.1% of trials fall between none and all four), which
   is why *k* barely matters — an artifact, not robustness.
4. **R4 — single facility (High for external validity).**
5. **R7 — high-capacity ordering near the noise floor (Medium).** A sixth of
   candidate pairs still cannot be ordered at 400 scenarios.
6. **R8 — undefended cost and burden weights (Medium).** Two of six
   objectives.
7. **New — declared ranges are ours (Medium).** Objectives are marginal over
   ranges we chose, with no elicitation protocol behind them.
8. **R9 — THREAT preview export (Low).**
9. **R10 — self-audit (unquantifiable).** The rebuild, the ledger, the
   benchmark classifications and this report share an author. The archive
   defect in §6 is the concrete demonstration: nine automated checks and a CI
   pipeline all passed while the repository could not reproduce itself, and
   the only thing that found it was reading a passing check and asking what
   it would fail on. Assume more of that class remain.

Resolved in WP3: R3 (isolated backups could not fail) and R5 (misapplied
patch and identity scalars).

## 9. Human decisions

Four blocking, in `audit/human_decisions_required.md`: target journal;
authorship, CRediT and corresponding author; AI-use disclosure against the
target journal's policy; and **whether to add multi-facility structure or
explicitly narrow the paper's scope** — the draft reports the failure
honestly but still frames the work at hospital level, which is not a stable
position.

Strongly recommended: clinical review of the three declared thresholds, and
domain review of the cost and burden tables.

## 10. What would move this higher

Concentrated, and only two items are things this agent could supply: layered
recovery endpoints out to 90 days (+2–3, and it converts two failed
benchmarks into scoreable ones); varying more than one structural assumption
(+2, now the highest-value uncertainty work); multi-facility structure or an
explicit narrowing (+1–2); a confirmatory cost-scaling sensitivity (+1);
structured elicitation for the declared ranges (+1, needs domain experts);
and independent review (+1–2, needs a human who did not write this).
