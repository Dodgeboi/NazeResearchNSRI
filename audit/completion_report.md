# Completion report

**Branch:** `rebuild/wp0-wp2`, on top of `3b734df`
**Nothing pushed.** All work is local to this branch.

---

## 1. Bottom line

**Scored 87/100 against the handoff's rubric, inside the 85–90 target band.**
Every score cap is cleared. The baseline was capped at 74; an intermediate
revision of this work scored 81 before WP3.

**Not submission-ready, and the score does not say otherwise.** Reaching a
rubric band measures methodological discipline. It does not price the
model's central limitation — that no internal coefficient is identified by
hospital data — and it cannot price novelty, journal fit, or reviewer
judgement. Four blocking human decisions remain open and no human has read
the rendered paper.

**What still limits the science, in order:** the recovery endpoint is a
single 72-hour horizon where the specification requires layered endpoints to
90 days, which is why two external benchmarks fail; only one structural
assumption has been varied, and that one moved the answer far more than
sampling ten parameters did; and the model runs one facility against an
incident record where a quarter of events span several.

## 2. What changed

### Scientific

- **The sustained-outage endpoint is defined once and implemented literally.**
  It was defined in prose as requiring four clinical services and computed as
  requiring one. It is now a *k*-of-*n* rule in a central registry with
  *k* = 4 declared in config, and the full *k* = 1…4 ladder reported
  everywhere.
- **Per-service outage streaks are persisted**, so the endpoint is
  recomputable offline at any *k* and any threshold. The old schema discarded
  them, which is why this had to be a fresh run rather than a re-analysis.
- **Capacity is exogenous.** Posture ladders are upgrade-only and priced on
  the increment actually bought. Previously a strong profile could buy flat
  segmentation and connected backups for zero points, and four of seven
  frozen high-capacity finalists were such free downgrades.
- **The backup ladder is fully enumerated**, so the intermediate profile's own
  declared `periodic` architecture — previously unreachable by any candidate
  — now runs, and every candidate label matches what it resolves to.
- **Structural assumption S1 is switchable and varied**, having been
  undocumented before.

### Computational

- `grrc.endpoints`: one definition per outcome, read by the analysis, the
  tables and the claim audit.
- `grrc.provenance`: content-addressed protocols, hashed manifests,
  per-run config snapshots, verification that raises rather than warns.
- Full-space confirmatory design plus `restricted_frontier_comparison`, which
  measures what a restricted holdout would have distorted.
- Monte Carlo error per objective, and a count of candidate pairs the
  scenario bank cannot reliably order.
- Precision-justified, per-profile scenario allocation.
- 165 tests, up from 70, including one strict `xfail` that keeps a known
  model defect visible.

### Evidentiary

- Source manifest schema 2: retrieval date, mutability class, licence, reuse
  terms, size, hash, derived counts, and an explicit `does_not_support` list
  per source.
- `docs/evidence/THREAT_RECONCILIATION.md` resolves the ~160 / 149 / 25.7% /
  52.9% figures as three different denominators, exactly.
- Frozen external-validation registry with nine benchmarks, criteria fixed
  before comparison.
- Citation verification found and recorded a discrepancy in the handoff's own
  summary of the AEJ estimates.

### Manuscript

Restructured to the ten-section outline, opening with its own predecessor's
defects. **No hand-typed result value anywhere** — every number arrives
through a generated macro. Builds clean at 11 pages.

## 3. Verification

```
python scripts/unpack_raw.py && python scripts/run_full_audit.py
```

| Check | Result |
|---|---|
| Test suite | 179 passed, 0 xfail |
| Behavioral validation | 12/12 |
| Archived sources (hashes, sizes, re-derived counts) | pass |
| Frozen protocols verify | pass |
| Run manifests describe files on disk | 11 checked, pass |
| Manuscript claim audit | pass, 5/5 checks |
| Numbers re-derive from raw trials | pass |
| External validation reports its failures | pass |

Confirmatory protocol `multiobjective_confirmatory_v2`, SHA-256
`9cb7e835446a…`, frozen 2026-09-04T01:53:46Z and committed **before** any v2
output existed. Protocol v1 is superseded rather than edited, because the
mechanism repairs changed what the model is.

Banks: discovery 12,000 executions; confirmatory 160,000; structural
sensitivity 28,800 across two arms. Roughly six hours of compute on two
cores across both study versions.

## 4. Validation

**Of nine frozen benchmarks, two are scoreable, three fail, none passes.**
Seven are unaddressable or unscoreable because the model has no output of
that construct.

| Benchmark | Verdict |
|---|---|
| Short technical outage (CrowdStrike) | **fail** — median 42.5 modeled hours vs 5.1 observed; 25.3% recover within six hours vs 58.1% |
| Recovery trajectory (~3 weeks) | **fail** — recovers far too fast; horizon cannot span the window |
| Multi-facility breadth | **fail** — probability zero against 25.7% observed |
| Contained before encryption | consistent — profile spread brackets the surveyed figure; weak evidence |
| Recovery duration bins | not addressable — 72-hour horizon cannot place mass beyond a week |
| Adjacent-ED spillover | not addressable — no second facility exists |
| Week-1 activity loss; California ED/admissions | not scoreable — service-hours are not patient volume |
| Control adoption prevalence | not scored — used for scenario design, never as an effect size |

**No target informed any tuning.** Criteria were frozen before comparison,
the runner exits zero on failure, and the audit asserts failures are still
being reported.

The most informative failure is two-sided: the restoration engine is far too
**slow** against the observed technical outage and far too **fast** against
the ransomware record. It is anchored to neither.

## 5. Claims

**Now supportable:** a reproducible, fully hashed pipeline from archived
sources to manuscript; a full-space confirmatory frontier under a
checkable freeze; a direct measurement of restricted-holdout distortion
(3 artifacts, 25 efficient candidates a restricted design could never have
shown, 12 of 59 finalists displaced); honest external validation with
failures reported; and an explicit identification framework.

**Still prohibited:** that any control has any effect in a real hospital;
that any duration or probability describes a real incident; that the model is
calibrated; that the frontier is procurement advice; that reproducibility
implies correctness.

**One claim needs care.** The paper reports that identity controls buy
nothing detectable *and* that the identity mechanism is misapplied. Both are
true; a reader could wrongly take the first as a finding about identity
controls in hospitals. Flagged in the red-team report.

## 6. Residual risks

Ordered by effect on the conclusions. Full detail in
`audit/final_red_team_report.md`.

1. **R1 — no recovery calibration (High).** Every duration statement inherits
   the two-sided failure above.
2. **R2 — binary availability drives a headline (High).** Clinical outcomes
   are near-binary (4.5% of trials fall between none and all four), which is
   why *k* barely matters — an artifact, not robustness.
3. **R3 — isolated backups cannot fail (High).** A deterministic win in the
   objective space; pinned by a failing test.
4. **R4 — single facility (High for external validity).**
5. **R6 — structural assumptions (High, raised).** Relaxing S1 alone moves
   20–29% of frontier membership and nearly doubles disruption in the two
   weaker profiles. It is the only structural assumption varied.
6. **R5 — misapplied patch and identity scalars (Medium).**
7. **R7 — high-capacity conclusions near the noise floor (Medium).**
8. **R8 — undefended cost and burden weights (Medium).**
9. **R9 — THREAT preview export (Low).**
10. **R10 — self-audit (unquantifiable).** The rebuild, the ledger, the
    benchmark classifications and the red-team report share an author.

## 7. Human decisions

Four blocking, in `audit/human_decisions_required.md`: target journal;
authorship, CRediT and corresponding author; AI-use disclosure against the
target journal's policy; and **whether to add multi-facility structure or
explicitly narrow the paper's scope** — the current draft reports the
failure honestly but still frames the work at hospital level, which is not a
stable position.

Strongly recommended: clinical review of the three declared thresholds, and
domain review of the cost and burden tables, which shape two of six
objectives and which nobody has defended.

Two decisions this rebuild made that the authors may overturn: *k* = 4 for
the outage endpoint (reversible at no cost — all four values are reported),
and the scoping decision to skip WP3.

## 8. What would move this to 85–90

In order of points per unit of effort: prespecified parameter uncertainty
propagated through the results (+3–4, the largest single deficit and it needs
no new evidence); repairing the three misapplied mechanisms (+3–4, bounded
changes with tests already written to catch them); layered recovery endpoints
(+1–2, and it removes R1); regenerating the stale parameter register (+1);
independent review (+1, not something this agent can supply).

Items one to three are WP3.
