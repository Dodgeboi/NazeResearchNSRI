# WP9 — Adversarial audit of the rebuilt study

**Object:** `Dodgeboi/NazeResearchNSRI`, branch `rebuild/wp0-wp2`
**Baseline audited:** commit `3b734df`
**Confirmatory protocol:** `multiobjective_confirmatory_v2`, SHA-256
`9cb7e835446a…`, frozen 2026-09-04T01:53:46Z and committed to git **before**
any v2 output existed. Protocol v1 is superseded rather than edited: the WP3
mechanism repairs and the addition of parameter uncertainty changed what the
model is, so v1 no longer describes a study anyone would run. The freezing
machinery refused to overwrite it.
**Method:** `python scripts/run_full_audit.py`, plus the manual falsification
attempts recorded below.

This report tries to break the rebuilt study. It is written by the same agent
that performed the rebuild, which is a real limitation and is stated first:
an author auditing their own work will not find the defects their own
assumptions produced. What it can do is check the work against the
artifacts, and that is what follows.

---

## 1. Verification results

| Check | Result |
|---|---|
| Test suite | 179 passed, 0 xfail (the backup defect is repaired, so its pinning xfail became a passing test) |
| Behavioral validation | 12/12 |
| Archived sources: hashes, sizes, re-derived counts | pass |
| Frozen protocols verify against their own digests | pass |
| Run manifests describe the files on disk | pass |
| Manuscript claim audit | pass on all five checks |
| Manuscript numbers re-derive from raw trials | pass |
| External validation still reports its failures | pass |

The expected xfail is deliberate and is discussed in §4.

## 2. Attempts to falsify the study's own claims

Each of these is a claim the paper makes about itself, and an attempt to
break it.

### "The confirmatory protocol was frozen before the results existed"

**Attempted falsification:** edit the protocol file and see whether anything
notices; re-freeze under the same name; check whether the git history
actually orders the freeze before the outputs.

**Result: claim holds.** `load_frozen_protocol` recomputes the digest over
the canonical form and raises on any edit
(`tests/test_provenance.py::test_editing_a_frozen_protocol_is_detected`).
`freeze_protocol` refuses to overwrite. The protocol appears in commit
`463da77`; the confirmatory raw output appears in a later commit. The runner
also refuses to start if the resolved candidate space has changed since
freezing, so a protocol cannot be silently reused against a different study.

**Residual weakness:** the ordering is verifiable in *this* repository's
history. A reader who does not trust the repository's history has no
independent timestamp. A public timestamping service or a pre-registration
DOI would close that gap and is recommended before submission.

### "Every number in the manuscript comes from a results table"

**Attempted falsification:** hand-type a result number into a section file
and see whether the audit catches it; check whether the audit reads the
section files at all.

**Result: the claim initially failed, and the auditor was wrong.** The first
version of `audit_manuscript_claims.py` read only `main.tex`, so any number
— or red-line claim — written in `section_results.tex` would have gone
unexamined, and every macro used there was falsely reported as an orphan. A
second bug was worse: expanding `\input` naively inlined
`generated_numbers.tex`, which made every macro appear "used" and caused the
orphan check to pass **vacuously**. Both are fixed; the auditor now expands
inputs and excludes the generated definitions.

This is the single most instructive finding in this report. A verification
tool that reports "pass" because it is looking in the wrong place is worse
than no tool, and the failure mode is identical to the one that produced the
original defect: a green check that asserts nothing.

### "The full-space frontier is genuinely full-space"

**Attempted falsification:** check that the confirmatory bank contains every
resolved candidate; check that the candidate counts in the manuscript
re-derive from the raw trial file rather than from an intermediate.

**Result: claim holds.** `run_full_audit.py` re-derives 137,600 rows and 400
profile-candidates directly from the raw CSV and compares them against the
generated macros. The frozen protocol pins the candidate counts and the
runner refuses to proceed if they differ.

### "The endpoint is recomputable at any k"

**Attempted falsification:** recompute the endpoint from the persisted
per-service streaks and compare against the emitted indicator columns.

**Result: claim holds**
(`test_simulation_emits_every_column_the_endpoint_needs`). An external
auditor can recompute the endpoint at any k and any duration threshold from
committed raw output without running a simulation. This was impossible in
the pre-rebuild schema.

### "Capacity is exogenous"

**Attempted falsification:** search all 288 enumerated portfolios × 3
profiles for any combination that weakens a posture or is refunded.

**Result: claim holds**
(`test_no_candidate_can_weaken_any_profile_posture`,
`test_exactly_one_zero_cost_candidate_per_profile`,
`test_downgrade_attempt_is_never_refunded`).

### "Failures are reported rather than corrected"

**Attempted falsification:** check whether the validation registry was edited
after the comparison was run; check whether any benchmark was quietly
dropped.

**Result: claim holds, with one qualification.** The registry's targets and
criteria are frozen text and the runner exits zero on failure. `run_full_audit`
asserts that failures are still being reported, on the reasoning that a
single-facility, 72-hour, binary-availability model reporting zero failures
would indicate broken reporting rather than a good model.

**The qualification:** the registry was written by the same agent that knew
the model's shape. Marking a benchmark `not_addressable` is a judgement, and
a less scrupulous version of that judgement would quietly convert failures
into "not applicable". Each such verdict carries a written structural reason
that a reviewer can check, but the reader should read those reasons
sceptically rather than take the classification on trust.

### "Parameter uncertainty is inside the objectives, not beside them"

**Attempted falsification:** check that two candidates replaying one scenario
see identical parameters (otherwise pairing is silently broken and every
portfolio comparison is between different physics); check that draws land in
their declared ranges; check that a reordered config reproduces the same
draws; check that the shared config object is not mutated by workers.

**Result: claim holds** (`tests/test_uncertainty.py`, twelve tests). The
pairing property is the one that matters and it is asserted directly.

**A related defect this surfaced.** Four falsification tests pin a
coefficient and assert what the mechanism must then do. With sampling
enabled those pins are silently overridden, and the tests would have been
asserting properties of a random draw. They now disable sampling explicitly,
and a new test asserts the override itself so the interaction is pinned
rather than assumed.

### "The frozen protocol's rationale is correct"

**Result: it was not, and this is the most important finding in this
revision.**

Protocol v2's `trials_rationale` records that three of four high-capacity
objectives had an interquartile range of exactly zero across all sixteen
candidates, and concludes that "no scenario count resolves them at all --
that is a finding about the profile, not a budget problem."

The confirmatory data refute it. At 400 scenarios those sixteen candidates
take sixteen distinct values on mean disruption, spanning 13.07 to 15.02
weighted service-hours. The zero ranges were an artifact of the
thirty-scenario pilot: at that resolution the achievable outcome values are
coarse enough that candidates tie exactly, and a correlation-ratio estimator
asked to size a difference it cannot yet see returns an unattainable
requirement. **"This quantity cannot be resolved" and "this pilot cannot
resolve it" are easy to confuse, and we confused them.**

The protocol was not edited. A frozen protocol whose rationale turns out to
be wrong is corrected in the open, in the manuscript and in
`DEVIATIONS.md`, or freezing it means nothing. No result changed: 400
scenarios was the affordable maximum and would have been chosen either way.

## 3. Attempts to falsify the model itself

Beyond the frozen benchmark registry, `tests/test_falsification.py` runs
limiting-case and invariance checks. All pass: zero transmission produces no
secondary compromise; complete effective patching stops propagation;
saturating the spread rate produces finite, bounded, interpretable output;
recovery endpoints cannot occur in an impossible order; a longest continuous
outage never exceeds total downtime; identical seeds reproduce identical
results; candidate ordering does not change the frontier; adding a dominated
candidate removes no existing non-dominated candidate; duplicate points are
both retained.

The synthetic fixture in which a non-finalist dominates a finalist is
included precisely because it is the failure the previous design could not
detect. Notably, **the first version of that fixture was wrong** — a
candidate labelled "genuinely efficient" was in fact dominated — and the
test caught the test. That is the intended behaviour.

## 4. Unresolved risk register

Ordered by potential effect on the conclusions.

### R1 — The model is not calibrated to any recovery reference. **High.**

The restoration engine is simultaneously far too slow against the one
observed large-scale technical hospital outage (median 42.5 modeled hours
against 5.1 observed) and far too fast against the ransomware incident
record, which has most of its duration mass beyond a week. Every conclusion
involving the non-recovery objective, and every statement about how long
disruption lasts, inherits this. **Mitigation in place:** reported as a
failed external benchmark, and the objective is described in the manuscript
as a within-model ordering device. **Real fix:** layered recovery endpoints
over 72 h / 21 d / 90 d with a 180-day tail, and an interval-censored
recovery-class model. Not attempted here.

### R2 — Binary service availability drives a headline behaviour. **High.**

Clinical outcomes are near-binary (only 4.5% of trials fall between "no
service qualifies" and "all four qualify"). This is why the choice of *k* is
immaterial — and it is an artifact of binary per-step availability over a
shared network, not a property of real incidents, which show partial and
staggered loss. A reader could mistake the *k*-insensitivity for robustness.
**Mitigation:** stated explicitly in the specification, the methods, the
results, the discussion, and the figure caption. **Real fix:** graded service
capacity. Not attempted here.

### R3 — Isolated backups cannot fail. **RESOLVED in WP3.**

Falsifiability now comes from a per-incident isolation lapse plus a
non-network residual failure mode, both drawn once per incident and shared
across candidates in a scenario. Isolated backups fail 8.3% of the time
against 100% for connected under the aggressive validation config. The
pinning `xfail` now passes.

*Residual concern:* the lapse and residual rates are declared assumptions
sampled from declared ranges. Isolation is no longer a guarantee, but how
often it lapses is still something we chose rather than measured.

### R4 — Single facility. **High for external validity, low for the internal comparison.**

The model assigns probability zero to roughly a quarter of publicly reported
hospital-linked events. It cannot address regional spillover at all.
**Mitigation:** reported as a failed and an unaddressable benchmark
respectively. **Real fix:** multi-facility structure, or an explicit
narrowing of the paper's scope.

### R5 — Patch effectiveness and identity effects are misapplied scalars. **RESOLVED in WP3.**

Edges carry a pathway label, so patching acts fully only on exploit-mediated
traversal and identity effects only on credential-mediated traversal, with
explicit coverage for identity controls. Both effectiveness values are now
sampled from declared ranges rather than fixed.

*Residual concern:* the pathway taxonomy is itself a modeling choice with
three categories, and real traversal does not partition that cleanly.

### R6 — Structural assumption S1, and the assumptions like it. **High.**

*Raised from Medium after the sensitivity analysis returned.* Relaxing S1
alone changes frontier membership by 20–29% depending on profile (Jaccard
agreement 0.71–0.80) and moves resource-constrained mean loss from 155.0 to
245.6 weighted service-hours, with non-recovery going from 14.4% to 73.5%.
S1 is not a scheduling convenience; it encodes the substantive claim that
responders never restore into an uncontained environment, and the model is
materially more optimistic for it.

The mechanism is worth understanding: a restored node re-enters susceptible,
so restoring during active propagation hands clean assets back to an
adversary with reach. That is a real property of the model, not an artifact
of the switch.

**Now the largest quantified threat to the conclusions.** With parameter
uncertainty in place the comparison is direct: sampling ten coefficients
across wide declared ranges leaves portfolio orderings largely intact (worst
Spearman 0.61, mostly above 0.9), while changing one structural assumption
moves up to 16 candidates off the frontier and roughly doubles modeled
disruption in two profiles. Structural uncertainty dominates parameter
uncertainty here by a wide margin, and S1 is the *only* structural
assumption that has been varied. If the one we tested moves the
answer this much, the untested ones — the transition ordering within a step,
the service-dependency graph, the criticality-ordered restoration queue, the
absence of an adaptive adversary — cannot be assumed gentler. The honest
position is that structural uncertainty in this model is large and mostly
unmeasured.

### R7 — High-capacity conclusions rest on differences near the noise floor. **Medium.**

A third of high-capacity candidate pairs remain statistically
indistinguishable even at 800 paired scenarios. The reported frontier
membership for that profile should be read as weak.
**Mitigation:** the indistinguishable-pair count is reported alongside the
frontier, and the manuscript states the conclusion as "no purchasable
control makes a detectable difference" rather than naming a winner.

### R8 — Cost and burden weights are undefended. **Medium for decision relevance.**

They are declared ordinal points with no procurement basis, and they enter
two of six objectives, so they materially shape the frontier.
**Mitigation:** labelled as normalized scenario units everywhere, in code,
outputs, captions and prose. **Real fix:** domain review, and cost-scaling
sensitivity reported alongside the main frontier.

### R9 — The THREAT source is a preview export. **Low.**

Its hash pins exactly what was analyzed and the reconciliation with the
published article is exact, but the original deposit should replace it
before submission.

### R10 — Self-audit. **Unquantifiable.**

This report, the issue ledger, the validation registry's
`not_addressable` classifications, and the rebuild itself share an author.
Independent review by someone who did not write the code is the only
mitigation, and it has not happened.

## 5. Things a reviewer should attack first

If we were reviewing this paper adversarially, these are where we would
start, in order:

0. **The declared uncertainty ranges.** Ten coefficients now carry ranges
   the authors chose, and every reported objective is marginal over them. A
   wide range honestly says "we do not know", but it does not make the
   resulting interval empirical, and a reader could mistake widened
   objectives for calibrated ones.
1. **The `not_addressable` classifications.** Seven of nine benchmarks are
   excluded from scoring on structural grounds. Are all seven genuinely
   unanswerable, or are some merely inconvenient? Each carries a written
   reason; check them.
2. **The claim that the frozen protocol is prospective.** Verified within
   this repository's history only.
3. **The cost and burden tables.** Two of six objectives rest on numbers
   nobody defended.
4. **The high-capacity conclusion.** Differences near the noise floor.
5. **Whether the identity-controls finding is a model artifact.** "Identity
   controls buy nothing detectable" is a conclusion about a whole-network
   multiplier that R5 says is misapplied. It may be an artifact of that
   defect rather than a finding.

Point 5 deserves emphasis: it is a case where a reported result and a
declared defect interact, and the manuscript should not be read as claiming
that identity controls are useless in real hospitals. It claims that within
this model, under a multiplier the paper itself says is misapplied, they
change nothing measurable.

## 6. Claims the rebuilt work is entitled to make

- A reproducible, fully hashed pipeline from archived sources to manuscript.
- A full-space confirmatory frontier under a protocol whose freeze is
  checkable from the repository.
- A direct measurement of how much a restricted-holdout design would have
  distorted the reported frontier.
- Honest external validation, with failures reported as results.
- An explicit parameter-identification framework in which unidentified
  quantities are labelled as declared assumptions.

## 7. Claims it is not entitled to make

- That any control has any effect in a real hospital.
- That any reported duration or probability describes a real incident.
- That the model is calibrated. It is partially calibrated at best, and its
  recovery behaviour is calibrated to nothing.
- That the frontier constitutes procurement advice.
- That reproducibility implies correctness.
