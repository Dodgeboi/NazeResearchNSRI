# A certified cyber-range benchmark for automated defenders

Date: 2026-09-21. Status: design note for a new study (WIP-grade, extensible).
Branch: `claude/stoic-galileo-81yrtm`.

## Motivation and scope

Autonomous cyber-defense systems are evaluated almost entirely by *empirical*
outcomes -- attack-success rate on a range, tasks solved, flags captured. Those
scores are averages over the scenarios that happened to be sampled; they say
nothing provable about the residual risk a defender leaves behind. This study
turns the repository's distribution-free residual-risk certificates on real MITRE
ATT&CK structure into a small **cyber range that scores automated defenders with a
provable guarantee**, not just an average: for any portfolio a defender proposes,
the range returns a distribution-free `guaranteed`/`possible` adequacy verdict
(worst-/best-corner reachability under interval uncertainty) and a catastrophic
k-of-n residual-risk bound, with finite-sample intervals where effectiveness rests
on counts.

**Honest tier.** This is a first-of-kind *evaluation-environment / benchmark*
contribution, realistically a workshop / work-in-progress paper. It is **not** a
new theorem (the certificate and the k-of-n closed form are prior work in this
repo) and **not** a validated real-world defense. The reference defenders are
simple automated policies. The hospital threat model is synthetic; MITRE ATT&CK
(v17.1) and the CIPHER harm corpus are real. Effectiveness/degradation values are
analyst-prior intervals anchored to published figures, never incident
measurements, and the certificate verdicts are conditional worst-case frequencies
under those intervals, not statistical confidence levels.

**Venue fit (AIDC @ ACSAC 2026, "Agentic AI in Offensive and Defensive Cyber
Operations").** Two of the workshop's stated topics are hit directly and without
any LLM: the range is an *adaptive evaluation environment / dynamic cyber range*,
and the reference policies are *automated defensive countermeasures*. The
defender-agent API is deliberately agent-agnostic (observation -> action ->
certified score), so an agentic/LLM defender drops in unchanged later; that is
named as future work, not built here.

## Design

The certificate is the deterministic, provable scorer. New around it:

1. **`DefenseRange` (`src/grrc/range/environment.py`).** Wraps a `HospitalModel`
   (`grrc.hospital_attack_model.build_model` over `grrc.attack_graph.build_graph`).
   - Observation: the current mitigation set plus static ATT&CK structure -- each
     mitigation's id, name, number of covered techniques, and stages touched.
   - Action: add / remove a mitigation by index (and a `set(portfolio)` reset).
   - `score()`: worst/best kill-chain reachability and `guaranteed`/`possible`
     adequacy at level `epsilon` (via `grrc.control_certificate.certify_portfolios`),
     the catastrophic k-of-n worst/best residual-risk bound and its guaranteed mask
     (via `grrc.hospital_attack_model.certify_catastrophic`), and cost = |portfolio|.
   - Deterministic and pure given a regime; no I/O.

2. **Reference automated defenders (`src/grrc/range/policies.py`), all non-LLM.**
   Each maps a regime to an ordered acquisition sequence and/or a final portfolio:
   - `greedy` -- thin wrapper over the existing
     `grrc.control_certificate.greedy_frontier` (order mitigations by worst-case
     reachability reduction); the strong baseline.
   - `optimal_small` -- **exact** minimum-cost portfolio that certifies at
     `epsilon` (for the clinical/reachability target), by budget-bounded
     best-first / branch-and-bound search with an admissible prune, feasible because
     adequacy is monotone in the portfolio; yields greedy's **optimality gap**.
   - `coverage` -- greedy by techniques-covered per unit cost (a structure-only
     heuristic that ignores the certificate, so its gap shows the certificate's
     value).
   - `random` (seeded), and the trivial `empty` / `all` references.

3. **Adaptive regime sweep (`src/grrc/range/regimes.py`).** A `Regime` bundles the
   adversary model, the base-rate and effectiveness interval bounds, the degradation
   bounds, `epsilon`, and the catastrophic `k`. The sweep varies: the adversary
   (below), assumed vs CIPHER-derived degradation
   (`grrc.cipher_bounds.degradation_bounds` at gamma=1 on the real corpus), an
   `epsilon` grid, and `k = 1..n`. Every defender is scored across the grid, so the
   benchmark reports cross-regime robustness rather than a single number.

3b. **Adaptive adversary (`src/grrc/range/adversary.py`, added).** Beyond the default
   *typical* adversary (usage-weighted mean residual per stage), an *adaptive*
   adversary best-responds to the current defense by routing through the easiest
   uncovered technique each stage — stage success is the `max` residual, the
   closed-form best response. It dominates the typical adversary pointwise (so the
   guarantee is strictly stronger) and stays monotone (so the interval corners are
   still exact); the audited certificate modules are untouched. Scoring against it
   makes the range genuinely dynamic and surfaces the headline finding: with no
   mitigation for some techniques, a worst-case adaptive attacker leaves most regimes
   uncertifiable by any portfolio — which only a provable score can reveal.

3c. **Reachability-floor mechanism (`adaptive_floor`, `stage_coverage_gaps`, added).**
   Adaptive reachability is monotone in the portfolio, so the full portfolio attains the
   global minimum — the reachability floor. A stage with a technique MITRE lists no
   mitigation for keeps that technique's residual at the base rate under any defense, so
   the floor is structural: 10 of 12 kill-chain stages carry such a technique (worst:
   discovery, 33 of 47), flooring the fully-defended catastrophic bound at ~23% for k=1.
   Certification under the adaptive adversary is possible only where the floor drops
   below epsilon, and even the most optimistic effectiveness prior leaves 7 of 12
   regimes uncertifiable — a coverage-gap fact, not a prior artifact. Reported in
   `coverage_gaps.csv`, `adaptive_floor.csv`, `prior_robustness.csv`, and a figure.

4. **Finite-sample scoring hook.** Where an effectiveness interval derives from
   counts, `grrc.betting.betting_margins` widens it to a finite-sample-valid
   interval before certification, so a "certified" verdict inherits finite-sample
   validity. Kept optional and explicit; the default regimes use the documented
   evidence intervals.

5. **Runner (`src/grrc/range/runner.py` + `scripts/run_defense_range.py`).** Runs
   every policy across the sweep on the real ATT&CK graph and emits the benchmark
   tables + a provenance manifest.

## Outputs (`data/defense_range/`)

- `leaderboard.csv` -- per (policy, regime): cost-to-certify (smallest portfolio
  size the policy reaches that is `guaranteed` adequate), whether it certifies at
  all, final worst-case reachability and catastrophic bound.
- `optimality_gap.csv` -- per regime: `optimal_small` cost vs `greedy` cost vs
  `coverage` cost (the certificate-blind heuristic), i.e. how far each heuristic is
  from the exact minimum.
- `regime_robustness.csv` -- per policy: fraction of regimes in which it certifies,
  and how its cost-to-certify moves from assumed to real (CIPHER) degradation and as
  `k` rises.

## Headline results (expected, reported not assumed)

(a) a leaderboard ranking the reference defenders by cost-to-certify and
cross-regime robustness; (b) greedy's measured optimality gap against the exact
`optimal_small` (and the larger gap of the certificate-blind `coverage`
heuristic); (c) the shift in certifiable control burden from assumed to real
(CIPHER) threat regimes and as the catastrophic threshold `k` rises.

## Verification

1. `pytest -q tests/test_range_environment.py tests/test_range_policies.py`, then
   full `pytest -q` (certificate modules unchanged in behavior).
   - env `score()` equals a direct `certify_portfolios` / `certify_catastrophic`
     call; `greedy` cost-to-certify equals the `greedy_frontier` curve;
     `optimal_small` is truly minimal on a tiny hand case (exhaustive oracle) and
     `greedy` cost >= `optimal_small` cost; regime monotonicity (fewer controls
     certify as `k` rises); input validation.
2. `python scripts/run_defense_range.py`; re-run -> byte-identical CSVs; manifest
   verifies; then regenerate from a clean tree so provenance records a clean state
   (the established clean-state-provenance pattern).
3. Compile `docs/defense_range/main.tex`; `scripts/run_full_audit.py` stays green
   (new manifest auto-verified).
4. Sanity gates inline in the runner: `optimal_small` cost <= `greedy` cost in
   every regime; k=1 catastrophic guaranteed mask agrees with the clinical union
   result; a policy that certifies at a strict `epsilon` also certifies at a looser
   one.

## Reuse (no new third-party dependency)

`grrc.attack_graph`, `grrc.hospital_attack_model` (`build_model`,
`certify_catastrophic`, `certify_clinical`), `grrc.control_certificate`
(`certify_portfolios`, `greedy_frontier`), `grrc.cipher_bounds.degradation_bounds`,
`grrc.betting`, `grrc.provenance`, `grrc.utilities.write_csv`. No `anthropic` /
`openai` / LLM packages.
