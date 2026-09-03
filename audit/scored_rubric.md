# Scored rubric, with evidence for every awarded point

Scored against the rubric in the rebuild handoff. **The target was 85–90.
This work scores 81.** The gap is not diffuse; it is one work package that
was not attempted, and it is named in §Uncertainty and §What would move this.

Scoring rule applied throughout: a defect that is *disclosed* earns less than
a defect that is *fixed*, and more than a defect that is hidden. Several
areas below sit in the middle band for exactly that reason.

---

## Score caps: all cleared

The handoff sets caps that bind regardless of the rubric total. Each is
checked against evidence rather than asserted.

| Cap trigger | Cap | Status | Evidence |
|---|---:|---|---|
| Unresolved semantic mismatch | 74 | **cleared** | Endpoint defined once in `grrc.endpoints`, implemented literally, asserted by 41 tests; `audit_manuscript_claims.py` fails the build if prose and registry diverge |
| Unverifiable full-space / holdout claim | 78 | **cleared** | Every resolved candidate evaluated; `run_full_audit.py` re-derives 137,600 rows and 400 profile-candidates from the raw file |
| Incomplete source / result provenance | 82 | **cleared** | Every input and output hashed; `verify_sources.py` re-derives every recorded count; manifests raise on mismatch |
| "Calibrated hospital model" without telemetry | 79 | **never triggered** | The word never appears; red-line pattern audit passes |
| No external validation or no failure reporting | 82 | **cleared** | Nine frozen benchmarks; three fail, none passes, all reported |
| Manuscript not reproducible from recorded inputs | 80 | **cleared** | No hand-typed result value; every number generated from a committed table |

**Binding cap: none.** The baseline audit put the pre-rebuild work at a
binding cap of 74.

---

## Area scores

### Scientific and semantic correctness — 15 / 20

**Earned.** Definitions, code, configs, outputs and prose agree, and the
agreement is enforced rather than inspected. The endpoint registry is the
single source of truth and the optimizer reads its objective list from it.
Boundary behaviour is tested at every *k* from 0 to 4 qualifying services,
at the exact threshold and one step past it, and for the non-clinical
services that must never contribute. Capacity precedence is asserted across
all 288 portfolios × 3 profiles. Deduplication resolves under the study
config rather than library defaults, and representatives are named for what
they run.

**Withheld (5 points).** Three parameters are still used in ways the paper's
own framework does not sanction: a single patch-effectiveness scalar applied
to pathways where patching is mechanically irrelevant, a whole-network
identity multiplier, and an isolated-backup traversal of exactly zero that
makes protected backups unfalsifiable. These are *disclosed as defects* in
the manuscript and tracked in the ledger, and one is pinned by a deliberately
failing test — but disclosure is not repair. The handoff's falsification list
requires that an isolated backup retain non-network failure modes, and it
does not.

### Evidence and parameter identification — 12 / 15

**Earned.** Every reported quantity carries an identification class, declared
in a machine-readable registry that the analysis, the tables and the claim
audit all read. Sources carry retrieval date, mutability class, licence,
reuse terms, size, SHA-256, derived counts, and — the part that does the real
work — an explicit `does_not_support` list. The THREAT reconciliation
resolves the article's ~160 hospitals, the repository's 149 records and the
52.9% vs 25.7% multi-facility figures as three different denominators, and
`verify_sources.py` re-derives all of it. Citation verification found and
recorded a discrepancy in the handoff's own summary of the AEJ estimates.

**Withheld (3 points).** `study/PUBLIC_EVIDENCE_PARAMETER_REGISTER.csv` still
carries pre-rebuild content and was not regenerated against the new registry.
The evidence work is complete in `grrc.endpoints` and the source manifest;
that CSV is now a stale third copy.

### Study design and validation — 13 / 15

**Earned.** Discovery, confirmation and validation are separated by
artifacts, not discipline. The confirmatory protocol is content-addressed,
refuses overwrite, fails to load if edited, and was committed before any
confirmatory output existed. The runner refuses to start under a changed
candidate space and stamps the digest into every raw row. Benchmark targets
and criteria were frozen before comparison, and failures are reported as
results. The pre-rebuild freeze is described as retrospective because it
cannot be established from the public record.

**Withheld (2 points).** The `not_addressable` verdicts — seven of nine
benchmarks — are judgements made by the same agent that knew the model's
shape. Each carries a written structural reason a reviewer can check, but the
classification is not independent. And the freeze ordering is verifiable only
within this repository's history; an external timestamp would close that.

### Uncertainty and robustness — 6 / 10

**Earned.** Monte Carlo standard error is reported for every stochastic
objective, alongside the count of candidate pairs the scenario bank cannot
reliably order — 33% in the high-capacity profile even at 800 paired
scenarios. Scenario counts are justified by a pilot precision analysis and
allocated per profile, because the requirement varies by more than a factor
of four. Bootstrap Pareto stability resamples whole scenarios, preserving
cross-portfolio correlation. Structural assumption S1 is varied and the
frontier agreement reported.

**Withheld (4 points), and this is the largest single gap.** *Parameter*
uncertainty is not represented at all. The unidentified coefficients — spread
rate, patch effectiveness, isolation success, identity multiplier,
restoration rate — are fixed point values, not the prespecified uncertainty
ranges the handoff requires and the evidence memorandum recommends. The paper
labels them as declared assumptions, which is honest, but a declared
assumption with no distribution over it cannot propagate into the results. No
global or scenario sensitivity over those parameters was run. Only one
structural alternative of several was varied.

### Multi-objective methodology — 8 / 10

**Earned.** Exact enumeration with behaviour-based deduplication; candidate
counts reported at every stage; dominance evaluated in all six objectives
with exact float comparison; increment-based costing so a profile is never
charged for a rung it holds; paired common random numbers throughout;
bootstrap frontier stability; and the full-space versus finalist-only
comparison that quantifies what a restricted design would have distorted.

**Withheld (2 points).** The preference weight sets are declared but
undefended, and the cost-scaling sensitivity that the discovery stage
supports was not re-run confirmatorily, so the frontier's dependence on the
cost table is unquantified at the confirmatory stage.

### Reproducibility and provenance — 10 / 10

**Earned in full.** Every run and analysis writes a manifest hashing each
input and output with code commit, dirty-tree state, environment and
timestamp; verification raises rather than warns. Runs archive the exact
configuration bytes they used, so a manifest cannot be invalidated by an
unrelated later edit — a mechanism added *because* the verifier caught this
work's own discovery manifest and the failure is recorded in `DEVIATIONS.md`
rather than quietly repaired. Protocols are content-addressed. The manuscript
contains no hand-typed result value. CI runs tests, source verification,
protocol verification, manifest verification and the claim audit. A clean
staged reproduction path is documented, including the two TeX packages whose
absence produces an error that does not name them.

### Manuscript argument and restraint — 9 / 10

**Earned.** A narrow, stated contribution. The parameter-identification
framework precedes any result. Every red-line claim is absent, checked by
pattern so paraphrases are caught. Six kinds of validity are separated and
the weakest is named as the weakest. The limitations cover reporting bias,
vendor surveys, transferability, denominators, censoring, absent telemetry,
elicited thresholds, cost, adaptive adversaries, cross-hospital dependence
and non-causal effects. The paper reports its own predecessor's defects and
states which numbers were withdrawn. It also records a justification that was
drafted and then withdrawn on the data.

**Withheld (1 point).** The manuscript reports that identity controls buy
nothing detectable while also declaring the identity mechanism misapplied.
Both statements are made, but a reader could take the first as a finding
about identity controls rather than about this model's treatment of them. The
red-team report flags it; the manuscript could be more explicit at the point
of the claim.

### Tests and adversarial audit — 4 / 5

**Earned.** 165 tests: regression tests for every repaired defect, invariants,
boundary and pathological cases, falsification checks, provenance tests, and
claim-to-artifact tests that assert the *manuscript's* definitions rather than
the code's behaviour. A one-command audit harness runs every verification to
completion and re-derives headline counts from raw trials, trusting no
intermediate. One strict xfail keeps a known model defect visible in every
run.

**Withheld (1 point).** The audit is a self-audit. Independent review by
someone who did not write the code has not happened, and no amount of
tooling substitutes for it.

### Presentation and journal readiness — 4 / 5

**Earned.** The document builds; figures use a palette validated for
all-pairs colour-vision separation and small multiples so identity is not
carried by colour alone; frontier points carry Monte Carlo error bars; tables
are generated. A misleading connecting line was caught during figure review
and replaced with a true lower envelope.

**Withheld (1 point).** No human has read the rendered paper. Reference
formatting, figure placement in the final two-column layout, and the target
journal's requirements are unchecked.

---

## Total: 81 / 100

| Area | Score | Max |
|---|---:|---:|
| Scientific and semantic correctness | 15 | 20 |
| Evidence and parameter identification | 12 | 15 |
| Study design and validation | 13 | 15 |
| Uncertainty and robustness | 6 | 10 |
| Multi-objective methodology | 8 | 10 |
| Reproducibility and provenance | 10 | 10 |
| Manuscript argument and restraint | 9 | 10 |
| Tests and adversarial audit | 4 | 5 |
| Presentation and journal readiness | 4 | 5 |
| **Total** | **81** | **100** |

## What would move this to 85–90

The gap is almost entirely one work package. In order of points recovered per
unit of effort:

1. **Parameter uncertainty (+3 to +4).** Give every unidentified coefficient
   a prespecified range and propagate it. This is the largest single deficit
   and needs no new evidence — only the discipline of declaring distributions
   instead of point values, and the compute to sample them.
2. **The three misapplied mechanisms (+3 to +4).** Nonzero residual failure
   for isolated backups; exploit-specific rather than universal patching;
   coverage-dependent rather than network-wide identity effects. These are
   bounded code changes with tests already written to catch them.
3. **Layered recovery endpoints (+1 to +2, and it removes risk R1).** 72 h /
   21 d / 90 d with a 180-day tail, and an interval-censored recovery-class
   model. This is the change that would let the model be compared against the
   recovery evidence at all.
4. **Regenerate the stale parameter register (+1).** Cheap.
5. **Independent review (+1).** Not something this agent can supply.

Items 1–3 are WP3 of the handoff, which was not attempted. That is the honest
summary of the gap: the study's *method* was rebuilt to the target standard;
its *model* was not.

## What this score does not mean

It does not mean the paper is 81% likely to be accepted, that the conclusions
are 81% correct, or that 9 more points would make the model right. It is a
score against a methodological rubric supplied with the rebuild brief. Journal
fit, novelty, reviewer judgement and editorial decision are outside it, and
the model's central limitation — that no internal coefficient is identified
by hospital data — is not a defect the rubric can price.
