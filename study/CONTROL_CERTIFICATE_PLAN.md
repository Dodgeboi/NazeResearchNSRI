# Control-adequacy certificates on the MITRE ATT&CK kill chain

Recorded on 2026-09-20, before running the analysis below. This is a **new,
self-contained study**, separate from the synthetic hospital-ransomware
manuscript in this repository. It does not modify, replace, or depend on that
manuscript or its audit; it reuses only shared utilities (`grrc.provenance`,
`grrc.utilities`) and the interval-certificate / finite-sample-bound ideas from
`grrc.frontier_certificates` and `grrc.betting`.

## Motivation and what is (and is not) real

The hospital study was limited by a fully synthetic network. This study replaces
the synthetic substrate with **real, authoritative structure**: the MITRE ATT&CK
Enterprise knowledge base (pinned v17.1, fetched and hashed by
`scripts/fetch_attack.py`). ATT&CK supplies the techniques, the kill-chain tactic
ordering, the mitigations, and the real `mitigates` edges. It also supplies
technique **usage** counts (the number of `uses` edges from groups/malware/tools),
a real prevalence signal.

What ATT&CK does **not** supply is effect sizes: a `mitigates` edge asserts a
mitigation is relevant to a technique, not by how much. This study therefore
treats per-technique success and per-mitigation effectiveness as **uncertain
intervals**, never point values, and certifies conclusions that hold across the
whole interval. This is the honest core of the contribution: a defensible
guarantee under acknowledged ignorance, not a precise-looking point estimate.

Scope limits, stated plainly: the kill-chain progression is a modelling
abstraction; effectiveness intervals are analyst priors (with one evidence-tightened
exception, below), not measured on incidents; there is no real-incident validation.
The contribution is a **method** and its application to real ATT&CK **structure**.

## Reachability model

Model a ransomware operation as traversing the ordered post-compromise ATT&CK
tactics `initial-access ... exfiltration` and then the impact objective
**T1486 (Data Encrypted for Impact)**. A control portfolio is a set of ATT&CK
mitigations. Each technique's residual per-attempt success is
`base * prod_{m in portfolio, m mitigates t} (1 - eff_m)`. A stage's success is
the **usage-weighted mean** residual over its techniques (a typical adversary:
prevalent techniques weigh more, partial coverage helps proportionally). The impact
stage contributes the objective technique alone. Reachability `R` is the product of
stage successes. `R` is coordinatewise monotone (increasing in every `base`,
decreasing in every `eff_m`).

## The certificate

Given interval uncertainty `base in [b_lo, b_hi]` and per-mitigation
`eff_m in [e_lo, e_hi]`, monotonicity places the extremes of `R` at the box
corners. A portfolio is:
- **guaranteed** adequate at level `epsilon` if `R <= epsilon` at the worst corner
  (`base = b_hi`, every `eff_m = e_lo`) -- adequacy that holds for every parameter
  value in the set;
- **possible** if `R <= epsilon` only at the best corner.

This is the necessary/possible interval-efficiency argument of
`grrc.frontier_certificates`, applied to reachability. Where incident counts exist,
`grrc.betting` turns them into finite-sample effectiveness intervals feeding the
box; this study uses documented ranges and demonstrates one evidence-tightened
interval (multi-factor authentication), leaving the rest as wide analyst priors.

## Fixed design

- Pinned data: ATT&CK Enterprise v17.1 (`data/attack/raw/`, hashed).
- Stages: the twelve post-compromise tactics; objective T1486.
- Base prior: `[0.5, 0.9]` common across techniques.
- Effectiveness prior: `[0.20, 0.70]` per mitigation, except the multi-factor
  authentication mitigation (M1032), tightened to `[0.85, 0.99]` from the reported
  Microsoft account-compromise reduction -- an illustration of evidence narrowing
  the box, not a claim of transferability.
- Levels: `epsilon in {0.10, 0.05, 0.01}`.
- Portfolios: the empty portfolio; the greedy worst-case-reduction frontier over
  all 44 mitigations (unit cost, giving a size-vs-guaranteed-reachability curve);
  and a set of named realistic bundles built from real mitigation IDs
  (identity, backup, segmentation, patching, detection).
- Sensitivity: repeat the empty and greedy-frontier certification under a narrow
  `[0.35, 0.55]` and a wide `[0.10, 0.85]` effectiveness prior, to report how the
  minimum guaranteed portfolio size depends on the assumed uncertainty.

## Software and reporting

Pure-array kernel with no I/O, validated by an independent brute-force reachability
oracle, monotonicity and corner-extremality checks, and invalid-input rejection.
The analysis is deterministic: re-running reproduces every CSV byte for byte.
Record the pinned data hash and all inputs in a provenance manifest. Generate all
manuscript numbers from the committed tables. Report all outcomes, including the
honest one that with wide priors no small portfolio guarantees a low reachability.
Do not overstate: this is a methods-and-real-structure contribution, realistically
a security or methods workshop, not evidence about any specific hospital.
