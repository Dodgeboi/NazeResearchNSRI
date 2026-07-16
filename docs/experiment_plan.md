# Experiment Plan

## Hypotheses (stated as predictions BEFORE running experiments)

These were written before any standard-mode results existed and are
labeled predictions; the Research Brief reports what the data actually
showed.

* **H1 (segmentation):** networks with basic or least-privilege
  segmentation will show lower compromise percentages and lower
  catastrophic-disruption probability than flat networks, with
  least-privilege strongest.
* **H2 (detection × patching):** detection delay and patch coverage
  will interact — fast detection will compensate for low patch coverage
  more than patching compensates for slow detection, because isolation
  halts propagation regardless of target susceptibility.
* **H3 (backups):** isolated backups will not reduce the probability of
  compromise but will sharply reduce unrecoverable data and shorten
  recovery, cutting weighted service-hours lost.
* **H4 (budget):** under small budgets (5 points), portfolios built on
  cheap controls (protected backups + a patch upgrade, or basic
  segmentation) will dominate; expensive controls (rapid isolation,
  least privilege) will enter at budget 10–15.
* **H5 (capacity gap):** the same portfolio will yield larger absolute
  damage reduction in the resource-constrained profile than in the
  high-capacity profile (more headroom), while the high-capacity
  profile keeps lower absolute damage throughout.

## Design matrix

| Dimension | Levels |
|---|---|
| Facility size | small_clinic, regional_hospital, large_hospital |
| Capacity profile | resource_constrained, intermediate_capacity, high_capacity |
| Defense portfolio (main) | 14 named conditions: baseline_flat, profile_baseline, basic_segmentation, least_privilege, patch_90, fast_detection, isolated_backups, identity_controls, seg_plus_patch, seg_plus_detection, detection_plus_backups, patch_plus_least_privilege, seg_detect_backup, full_defense |
| Entry point | workstation, internet_facing, privileged_system, medical_device, vendor_connection |
| Patch sweep | 25%, 50%, 75%, 90% coverage |
| Detection sweep | 1, 3, 6, 12, 24 steps mean delay |
| Optimizer space | 192-combination lattice (3 seg × 4 patch rungs × 2 det × 2 iso × 2 backup × 2 identity), deduplicated per profile to the distinct reachable configurations (192 / 144 / 96) |
| Budgets | 5, 10, 15 points |
| Cost scaling | ×0.50, ×0.75, ×1.00, ×1.25, ×1.50 |
| Random seed | master 20260713; per-trial streams via SeedSequence(master, trial_id) |

## Trial budgets by mode

| Mode | Main | Sweep | Optimizer | Total | Intended use |
|---|---|---|---|---|---|
| quick | 252 | 20 | 864 | ~1,100 | pipeline smoke test (~1–2 min) |
| standard | 15,750 | 1,000 | 10,800 | **27,550** | hackathon analysis (10–30 min, 4 cores) |
| full | 56,700 | 3,000 | 43,200 | **102,900** | expanded analysis (hours) |

## Analysis plan (fixed before the standard run)

1. Primary outcome: **weighted service-hours lost**; secondary:
   catastrophic probability (definition A14), % nodes compromised,
   backup compromise, recovery time.
2. Compare each portfolio to `baseline_flat` within facility × profile:
   relative reduction of the mean, absolute catastrophic-risk
   reduction, Cliff's delta, Mann–Whitney U with Holm correction
   across the whole comparison family.
3. Sweep: report the catastrophic-probability grid; identify whether
   delay or coverage dominates (H2) by comparing marginal changes.
4. Optimization: best portfolio per budget × profile under four
   criteria; Pareto frontier; minimum budget to reach P(catastrophic)
   ≤ 5%; control-inclusion frequency across the five cost scalings
   (stability check for H4).
5. Convergence: validation case 10 (100→1,000 trials) must show
   shrinking CIs before results are quoted.

## Deviations log

Any deviation from this plan must be recorded here with a reason.

* 2026-07-13 — none.
