> Historical assessment, superseded by the retrospective interpretation revision. See `docs/manuscript/REVISION_REVIEW.md`; old scores and narrative conclusions are not current readiness judgments.

# Scored rubric, with evidence for every awarded point

Scored against the rubric in the rebuild handoff. **The target was 85–90.
After WP3 this work scores 87.** An earlier revision of this file scored the
same work at 81, before the mechanism repairs and parameter uncertainty; the
9-point rubric gap it identified was one work package, and this is the score
after that package was done.

Reaching a rubric band is not the same as being publishable. The rubric
prices methodological discipline. It does not price the model's central
limitation — that no internal coefficient is identified by hospital data —
and it cannot price novelty, journal fit, or reviewer judgement.

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

### Scientific and semantic correctness — 17 / 20

**Earned.** Definitions, code, configs, outputs and prose agree, and the
agreement is enforced rather than inspected. The endpoint registry is the
single source of truth and the optimizer reads its objective list from it.
Boundary behaviour is tested at every *k* from 0 to 4 qualifying services,
at the exact threshold and one step past it, and for the non-clinical
services that must never contribute. Capacity precedence is asserted across
all 288 portfolios × 3 profiles. Deduplication resolves under the study
config rather than library defaults, and representatives are named for what
they run.

**Repaired in WP3.** All three previously misapplied mechanisms now act only
where they can act. Edges carry a pathway label, so patching removes
susceptibility on exploit-mediated traversal and not against stolen
credentials; identity effects are confined to credential-mediated edges with
explicit coverage; and isolated backups fail through a per-incident isolation
lapse and a non-network residual mode. The strict `xfail` that pinned the
backup defect now passes.

The backup repair was wrong on the first attempt and the suite caught it: a
0.02 per-step traversal looked like a small residual and compounds to a 100%
failure rate over 864 steps. A per-step probability models delay, not rarity.
That is recorded in `DEVIATIONS.md` rather than silently corrected.

**Withheld (3 points).** The recovery endpoint is still a single 72-hour
horizon. The model specification requires layered endpoints over 72 hours, 21
days and 90 days with a 180-day tail, and without them the model cannot
represent the phenomenon its own evidence base describes — which is why the
recovery benchmarks fail. Repairing the transition mechanisms did not touch
this.

### Evidence and parameter identification — 14 / 15

**Earned.** Every reported quantity carries an identification class, declared
in a machine-readable registry that the analysis, the tables and the claim
audit all read. Sources carry retrieval date, mutability class, licence,
reuse terms, size, SHA-256, derived counts, and — the part that does the real
work — an explicit `does_not_support` list. The THREAT reconciliation
resolves the article's ~160 hospitals, the repository's 149 records and the
52.9% vs 25.7% multi-facility figures as three different denominators, and
`verify_sources.py` re-derives all of it. Citation verification found and
recorded a discrepancy in the handoff's own summary of the AEJ estimates.

The parameter register was regenerated from the live registry and config: 17
parameters, each with its identification class, evidence basis, whether it is
sampled, and how it is treated.

**Withheld (1 point).** The uncertainty ranges are declared by the authors
without an elicitation protocol. They are honest about being wide where
evidence is absent, but "we chose a wide range" is a weaker warrant than a
structured elicitation with calibration questions would be.

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

### Uncertainty and robustness — 8 / 10

**Earned.** Monte Carlo standard error is reported for every stochastic
objective, alongside the count of candidate pairs the scenario bank cannot
reliably order — 33% in the high-capacity profile even at 800 paired
scenarios. Scenario counts are justified by a pilot precision analysis and
allocated per profile, because the requirement varies by more than a factor
of four. Bootstrap Pareto stability resamples whole scenarios, preserving
cross-portfolio correlation. Structural assumption S1 is varied, and the
result earns its place: relaxing it moves 20-29% of frontier membership and
nearly doubles modeled disruption in the two weaker profiles, which is
reported rather than buried.

**Added in WP3.** Ten unidentified coefficients now carry prespecified
ranges, drawn once per scenario and shared by every candidate replaying it,
so parameter uncertainty is a latent dimension of the common-random-numbers
design rather than something reported beside the results. Every objective is
marginal over those ranges. Every draw is recorded per row, which makes a
variance-based global sensitivity free, and it reports rank stability
alongside variance — the distinction between "the level is uncertain" and
"the decision is uncertain", which turns out to matter here: sampling ten
coefficients across wide ranges leaves orderings largely intact (worst
Spearman 0.61, mostly above 0.9).

**Withheld (2 points).** Only one structural alternative has been varied, and
that result argues loudly for varying more: relaxing S1 alone moves up to 16
candidates off the frontier and roughly doubles modeled disruption in two
profiles, which dwarfs the effect of sampling ten parameters. Structural
uncertainty is the kind that threatens the conclusions, and it remains almost
entirely unquantified. The declared ranges are also the authors' own.

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

The manuscript also now reports a correction to its own frozen protocol: the
protocol's rationale claimed that three high-capacity objectives were
unresolvable at any scenario count, and the confirmatory data refuted it —
the zero interquartile ranges were an artifact of a thirty-scenario pilot.
The protocol was not edited; the correction is stated in the paper and in
`DEVIATIONS.md`.

**Withheld (1 point).** No human has read the rendered paper end to end, and
several judgement calls in it — the benchmark classifications above all —
would benefit from a reader who did not write them.

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

## Total: 87 / 100

| Area | Score | Max |
|---|---:|---:|
| Scientific and semantic correctness | 17 | 20 |
| Evidence and parameter identification | 14 | 15 |
| Study design and validation | 13 | 15 |
| Uncertainty and robustness | 8 | 10 |
| Multi-objective methodology | 8 | 10 |
| Reproducibility and provenance | 10 | 10 |
| Manuscript argument and restraint | 9 | 10 |
| Tests and adversarial audit | 4 | 5 |
| Presentation and journal readiness | 4 | 5 |
| **Total** | **87** | **100** |

## What would move this higher

The remaining 13 points are concentrated, and only two of them are things
this agent could supply.

1. **Layered recovery endpoints (+2 to +3).** 72 hours, 21 days, 90 days and
   a 180-day tail, with an interval-censored recovery-class model. This is
   the single change that would let the model be compared against the
   recovery evidence at all, and it is what turns two failed external
   benchmarks into scoreable ones. It is also the largest piece of work.
2. **Vary more than one structural assumption (+2).** The transition ordering
   within a step, the service dependency graph, the criticality-ordered
   restoration queue, the absence of an adaptive adversary. The S1 result
   makes this the highest-value uncertainty work remaining, because
   structural uncertainty moved the answer far more than parameter
   uncertainty did.
3. **Multi-facility structure, or an explicit narrowing (+1 to +2).**
   Currently a failed benchmark and an unaddressable one.
4. **Confirmatory cost-scaling sensitivity (+1).** Two of six objectives rest
   on an undefended cost table.
5. **Structured elicitation for the declared ranges (+1).** Requires domain
   experts.
6. **Independent review (+1 to +2).** Requires a human who did not write
   this. It is the only item that no amount of further work by this agent can
   substitute for.

## What this score does not mean

It does not mean the paper is 87% likely to be accepted, that the conclusions
are 87% correct, or that 13 more points would make the model right. It is a
score against a methodological rubric supplied with the rebuild brief. Journal
fit, novelty, reviewer judgement and editorial decision are outside it, and
the model's central limitation — that no internal coefficient is identified
by hospital data — is not a defect the rubric can price.
