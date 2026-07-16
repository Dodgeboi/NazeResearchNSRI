# Limitations and Ethics

## Limitations of the model

1. **Synthetic topologies.** Networks are generated from documented
   proportions and access rules (A3–A4, A22); no real hospital network
   diagram was used or approximated. Real facilities differ in
   structure, scale, and heterogeneity.
2. **Abstract, normalized defense costs.** Costs are relative model
   points (A16), not dollar estimates; real prices vary by market,
   vendor, and existing infrastructure. We mitigate — but do not
   eliminate — this with ±25%/±50% cost-sensitivity analysis.
3. **Simplified lateral movement.** One multiplicative probability
   formula (A5) replaces the many distinct techniques real intrusions
   use. The model represents no specific ransomware family and cannot
   capture attacker adaptation, human operators, or zero-day dynamics.
4. **Simplified human behavior.** Clinician workarounds, incident-
   response staffing, decision fatigue, communication failures, and
   paper fallback procedures are not modeled.
5. **Not every ransomware technique.** Data exfiltration/extortion,
   supply-chain compromise, re-infection after restore, and multi-wave
   campaigns are out of scope.
6. **No real hospital is represented.** Outputs are model quantities;
   the simulation does not predict what would happen at any actual
   facility, and results must never be quoted as real-world incident
   statistics.
7. **No country-level conclusions.** Capacity profiles are neutral
   parameter bundles (A18). Mapping them to named countries, regions,
   or income groups would require evidence this study does not have.
8. **Simplified recovery.** Restoration capacity, duration, and
   backup-loss penalties (A15) are stylized; real recovery involves
   forensics, regulatory steps, and vendor dependencies that can take
   far longer than the 48-hour modeled horizon (long recoveries appear
   only as censored rows).
9. **Parameter-range dependence.** Conclusions are conditional on the
   assumptions registry; the sweep and cost-scaling analyses probe the
   most decision-relevant parameters, but a full global sensitivity
   analysis was outside the six-day scope.
10. **Security controls cost availability.** The model includes this
    tradeoff (false positives, isolation downtime, A10), but only
    crudely; real over-blocking harms are broader (e.g., delayed
    logins, broken integrations).
11. **What the results are.** The study identifies *modeled tradeoffs
    and rankings under stated assumptions* — not guaranteed real-world
    outcomes, and not a prescription that any specific hospital should
    follow without local assessment.

## Statistical and methodological notes

These concern how the Monte Carlo results are produced and analyzed.
The first group was tightened in the current version; the second is
disclosed as genuine caveats a reader should weigh.

**Addressed in this version.**

12. **Recovery is treated as censored data.** `recovery_step` encodes
    "never recovered within the horizon" as -1, so it is never averaged
    directly (a mean would rank the worst runs as best). Recovery is
    reported as a recovery probability plus the median time among trials
    that actually recovered (`*_recovery_summary.csv`,
    `statistics.recovery_summary`); the raw column and a clean
    `recovered_within_horizon` flag are retained for auditing.
13. **One channel per node pair.** Intra- and cross-zone edges are
    de-duplicated at generation time, so a repeated (source, target) pair
    can no longer multiply the transmission probability between two nodes.
    This removed a small, facility-size-dependent bias (smaller zones
    collided more often, inflating small-clinic spread).
14. **Optimizer search space.** The optimizer enumerates a 192-combination
    upgrade lattice (3 segmentation × 4 patch rungs × 2 detection × 2
    isolation × 2 backup × 2 identity) and evaluates, per profile, only
    the behaviorally-distinct configurations reachable from that profile's
    baseline (192 / 144 / 96 for the resource-constrained, intermediate,
    and high-capacity profiles). This (a) lets every profile reach the 90%
    patch ceiling the main experiment studies, and (b) stops two upgrade
    combinations that resolve identically (e.g. patch rungs that both cap
    at 90%) from being scored twice on different random networks, where
    noise rather than the defense could decide a "winner".
15. **Configured vs. realized patch coverage.** "Patch coverage" is the
    configured (policy) probability; legacy nodes receive half of it, so
    the realized patched fraction is lower and profile-dependent. Each
    trial now records `realized_patch_fraction` next to the target, and
    Figure 3's axis reads "target patch coverage".
16. **Reproducibility is pinned.** Dependencies are pinned to exact
    versions (`requirements.txt`) and every CSV is written with a fixed
    float format (`grrc.utilities.CSV_FLOAT_FORMAT`), so committed outputs
    regenerate byte-for-byte across machines — not only inside the exact
    library environment that first produced them.
17. **Catastrophic probabilities carry confidence intervals.** Each
    catastrophic probability is reported with a Wilson 95% interval, and
    "minimum budget to reach the 5% target" is given both as a point
    estimate and as a confidence-aware value (smallest budget whose best
    portfolio's 95% *upper* bound is <= 5%). At 25 trials per portfolio the
    two can differ sharply: even a 0/25 (0%) point estimate has a 95%
    upper bound near 13%, so a firm sub-5% claim is not supported at this
    sample size. Threshold claims should cite the confidence-aware column.

**Disclosed caveats (not changed).**

18. **No common random numbers.** Each trial draws its own network and
    entry node, so portfolios within a cell are compared on different
    random topologies. This is unbiased but less efficient than a paired
    design (same network, swap the defense); with heavy-tailed outcomes it
    widens intervals and makes the specific Pareto/best-portfolio picks
    noisier than a paired design would. A common-random-numbers redesign
    is the most valuable next methodological step.
19. **Selection over many candidates is optimistic.** "Best portfolio"
    and minimum-budget results take an extremum over many noisy estimates
    (up to 192 per profile) at n=25, so the selected winner's point
    estimate is biased low (a winner's-curse effect) and the exact winner
    can change between seeds. The reported confidence intervals are the
    honest guide; the single best portfolio should be read as "one of the
    strong portfolios", not an exact ranking.
20. **Cost-sensitivity "stability" is correlated.** The stability
    percentages reuse the same measured performance across 5 cost scales ×
    3 budgets and only rescale prices, so the 15 selections per profile
    are highly correlated — evidence a pick is insensitive to *price*, not
    15 independent confirmations.
21. **False-positive rate is posture-independent.** The false-positive
    isolation rate is a fixed per-node constant regardless of detection
    quality, adding a portfolio-independent downtime floor that can
    dominate very-low-damage cells.
22. **Small facilities are fragile by construction.** With a 2-node
    minimum per zone and a 0.60 service-functionality threshold, losing a
    single identity node (even to a false positive) can drop identity
    below threshold and cascade to dependent clinical services. Small-
    clinic results are a stylized worst case, not a size-calibrated
    prediction.
23. **Identity compromise is a tipping point.** The identity-breach spread
    multiplier is folded into edge probabilities, so once identity falls
    many edges saturate toward near-certain spread; outcomes in some cells
    are dominated by whether identity happens to fall.

## Ethics and safety

* Entirely defensive and simulated: no malware, encryption payloads,
  exploit code, credential tools, scanners, persistence mechanisms, or
  command-and-control functionality exists in this repository; a
  compromise is a boolean flag on a synthetic graph node.
* No confidential, patient, or personal data; no real IP addresses,
  systems, organizations, or network diagrams.
* The work aims to help defenders reason about resource allocation;
  it contains no information that meaningfully assists an attacker
  (the "insight" that flat networks and connected backups are weak is
  standard defensive guidance, e.g., CISA AA20-302A).
* Findings are framed as conditional model results to avoid alarmist
  or misleading claims about real hospitals or countries.
