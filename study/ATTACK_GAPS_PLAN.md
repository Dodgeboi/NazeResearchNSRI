# Uncoverable by design: ATT&CK mitigation gaps, the risk floor, and minimal repair

Date: 2026-09-23. Branch: `claude/stoic-galileo-81yrtm`.
Code: `src/grrc/coverage_evolution.py`; fetch `scripts/fetch_attack_history.py`;
analysis `scripts/analyze_attack_history.py`; tests `tests/test_coverage_evolution.py`.

## Question

MITRE ATT&CK is the reference model for threat-informed defense, and many
control-selection tools read its `mitigates` relationships to decide which controls
counter which techniques. How much of the ransomware kill chain does ATT&CK leave
*without any mitigation*, how has that changed across seven years of releases, what
lower bound on worst-case residual risk does it force on any defense built from
ATT&CK mitigations, and what is the smallest set of techniques that would need a
mitigation for a provable bound to become attainable?

## Data

Enterprise ATT&CK, latest patch of every major release v1.0 (2018-01) to v19.2
(2026-08), from the official `mitre-attack/attack-stix-data` repository. Raw bundles
are hash-verified and cached outside git; compact per-release extracts (active
techniques with tactics and sub-technique flag, active mitigations, active
`mitigates` edges) and `source_manifest.json` (URL, SHA-256, release date) are
committed, so every number reproduces offline.

## Definitions

- **Kill chain.** The post-compromise ransomware stages of
  `grrc.attack_graph.RANSOMWARE_STAGES` (initial access through impact).
  A *kill-chain technique* is an active technique with at least one such tactic.
- **Real mitigation.** Any active mitigation except the placeholders
  `M1055 Do Not Mitigate` and `M1056 Pre-compromise` (matched by id or name). These
  record that no preventive control applies; counting them as controls, as the earlier
  studies in this repository did, understates the gap. Both variants are reported.
- **Uncovered technique.** A kill-chain technique with no real mitigation.
- **Comparability.** A release is analysed if (i) at least 90% of its mitigations use
  the generalised `M####` identifiers, (ii) every kill-chain stage is populated, and
  (iii) T1486 (Data Encrypted for Impact) is active. Releases v1.0–v4.0 fail (i): their
  mitigations were technique-specific objects, one per technique, so "uncovered" is not
  defined on the same basis. They are listed with the reason, not silently dropped.
- **Structural breaks.** Sub-techniques arrive in v7 (technique counts jump); a
  parent-technique series is reported alongside. ATT&CK v19 splits Defense Evasion into
  Stealth and Defense Impairment; the crosswalk maps both to the defense-evasion stage
  so the kill-chain model is constant across releases, and v19.2 is also reported with
  the two as separate stages.

## Risk floor

Adaptive adversary at the worst interval corner (base rate 0.9; every mitigation's
effectiveness at its low end, 0.20, except the evidence-tightened MFA control M1032 at
0.85 — the conventions of the certificate studies). Technique residual
`r_t = base * prod_{m mitigates t} (1 - e_m)`; stage factor `f_s = max_{t in s} r_t`;
clinical reachability `F = prod_{non-impact s} f_s * f_impact`, where the impact stage
takes the clinical-impact techniques T1486/T1490/T1489/T1485. The catastrophic floor
is the sharp distribution-free bound on P(at least k of the four clinical services in
sustained outage) evaluated at marginals `F * d_high` (the closed form of
`study/KOFN_THEOREM.md`).

**Proposition 1 (floor).** Over all portfolios of real ATT&CK mitigations, the
adaptive reachability is minimised by deploying every mitigation, and any stage that
contains an uncovered technique has factor exactly `base`.
*Proof.* Deploying a mitigation multiplies each residual it touches by `1 - e_m <= 1`
and leaves the others unchanged, so every residual, every stage maximum and their
product are non-increasing in the portfolio; the full portfolio is therefore a
minimiser. An uncovered technique has no factor to multiply, so its residual is `base`
for every portfolio; since every residual is at most `base`, the stage maximum is
exactly `base`. ∎

Consequently certification at `(epsilon, k)` is possible with ATT&CK mitigations only
if the catastrophic floor is at most `epsilon`. The floor is monotone in `F`, so this is
equivalent to `F <= F*(epsilon, k)`, computed by bisection.

**Proposition 3 (base-rate factorisation).** For fixed effectiveness values the floor
reachability is `F(b) = b^n * C`, with `n` the number of stages (12) and `C` depending
only on coverage and effectiveness. *Proof.* Every residual is `b` times a product of
`(1 - e_m)` factors, so every stage maximum is `b` times the maximum of those products.
The sharp k-of-n bound is a minimum of linear functions of the marginals and 1, so it is
positively homogeneous in `F` until it reaches 1. ∎ Consequence: the ratio of floors of
two releases (same stages) is free of `b`, so the growth of the floor across releases
is not an artefact of the base-rate interval, while its level is.

**Certification, not typical risk.** The base-rate interval is [0.5, 0.9]; a certificate
must hold over the whole set, so it is decided at the worst corner b = 0.9. The floor is
therefore a floor on what can be *certified*, not on typical residual risk.

**Required tactics.** The model requires every kill-chain tactic. Requiring only a
subset removes factors at most 1 from the product, so the floor can only rise: the
reported floor is a lower bound for any subset of required tactics.

## Minimal repair

Suppose a set `R` of uncovered techniques each gains one new mitigation of worst-corner
effectiveness `e_new`. Find the smallest `|R|` with `F(R) <= F*(epsilon, k)`.

**Proposition 2 (whole-stage repair).** Let `U_s` be the uncovered techniques of stage
`s`. For any feasible `R`, the set `R' = union of U_s over {s : U_s ⊆ R}` is feasible,
has `|R'| <= |R|`, and yields the same floor. Hence an optimal repair is a union of
whole stage gap sets, and enumerating stage subsets (at most `2^12`) is exact.
*Proof.* By Proposition 1 applied stage by stage, a stage keeps factor `base` while any
technique of `U_s` is unrepaired, so only stages with `U_s ⊆ R` change. `R' ⊆ R`
repairs exactly those stages completely (a stage is fully repaired by `R'` iff it is by
`R`, since `R' ⊆ R` and `R'` contains every such `U_s`), and the extra techniques in
`R \ R'` sit in stages that stay at `base`; so `F(R') = F(R)`. ∎

Techniques shared by several stages (for example persistence and privilege escalation)
are counted once, which is why the enumeration is over stage subsets with the union
taken before costing, not a per-stage additive knapsack.

## Conventions and parameter sensitivity (added after an integrity review)

- **Sub-technique inheritance.** Default: each technique, including each
  sub-technique, is judged by its own mapping. Alternative: an unmapped sub-technique
  inherits its parent's mitigations (`inherit_parent_mitigations`). The direction of the
  gap trend holds under both; its size does not (reported side by side).
- **Parameters.** On the latest release, the floor and the 10% / 5% repairs are
  recomputed on a grid of base-rate upper ends {0.5, 0.7, 0.9} and effectiveness lower
  ends {0.10, 0.20, 0.35} (`parameter_sensitivity.csv`). The level of the floor is
  assumption-driven; by Proposition 3 its growth ratio is not.

## Prior work and search record

Searched September 2026 (web and arXiv search for ATT&CK with mitigation coverage,
mitigation gaps, unmitigated techniques, and control mapping). Closest work: Rahman &
Williams, "An investigation of security controls and MITRE ATT&CK techniques",
arXiv:2211.06500 (2022): NIST SP 800-53 controls over 188 techniques via the CTID
mapping, one snapshot. Surveys (arXiv:2304.07411; arXiv:2308.14016) track framework
growth and applications but not unmitigated techniques over releases. No longitudinal
measurement of unmitigated techniques, derived floor or exact repair was found; this is
an absence of evidence, not a proof of novelty.

## Outputs (`data/attack_history/`)

`coverage_by_release.csv`, `coverage_by_tactic.csv`, `floor_by_release.csv` (with the
counterfactual all-gaps-repaired floor), `minimal_repair.csv` (every comparable
release at `e_new = 0.20`; the latest release also at `e_new ∈ {0.10, 0.50}`),
`repair_list_latest.csv` (the prioritised techniques), `sensitivity.csv` (placeholders
counted; sub-techniques inheriting parent mitigations; the v19 split kept),
`floor_changes.csv` (every change of a binding technique), `parameter_sensitivity.csv`,
and `attack_history_manifest.json`.

## Verification

Tests: extract hashes match the source manifest; with placeholders counted, the
extract-based floor equals the audited `grrc.range.adversary.adaptive_floor` on the
pinned v17.1 bundle (1e-12); comparability rules; placeholder exclusion never shrinks
the gap; Proposition 1 on every comparable release; Proposition 2 (partial repair is
useless); the bisection inverts the catastrophic map; `minimal_repair` equals a brute
force over every subset of uncovered techniques on a synthetic release with a shared
technique; repair cost is monotone in `epsilon`; the repair's fast evaluator equals
the direct floor at non-default parameters; Proposition 3 (`F(0.5)/F(0.9) = (5/9)^n`);
parent inheritance only adds edges to unmapped sub-techniques of mapped parents. Inline gates in the analysis also
check that v17.1 reproduces the cyber-range study's per-stage gap counts.

## Scope

"No mitigation in ATT&CK" measures the knowledge base's mitigation *mapping*, not the
absence of any real-world defense — detections and vendor controls exist. That is the
point: every ATT&CK-driven control-selection tool inherits these gaps. The stage model,
the adaptive (worst-case routing) adversary and the effectiveness intervals are analyst
abstractions, and results are conditional on them. Novelty is claimed for the
longitudinal measurement, the floor it implies and the exact repair (a single-snapshot
control-gap study exists: Rahman & Williams 2022); the monotonicity argument is
classical and the repair is a small exact enumeration.
