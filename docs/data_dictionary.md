# Data Dictionary

## Raw result files (`data/raw/<mode>_*_results.csv`)

One row per Monte Carlo trial. `<mode>` ∈ {quick, standard, full}.
Files: `*_main_results.csv` (factorial experiment),
`*_sweep_results.csv` (patch × detection grid),
`*_optimization_results.csv` (deduplicated candidate-portfolio evaluation).
A `*_manifest.json` records trial counts, seed, and elapsed time.

### Identification & configuration (sufficient to reproduce the row)

| Column | Type | Meaning |
|---|---|---|
| `trial_id` | int | Unique trial index; with `master_seed` fully determines the RNG stream (main: 0+, sweep: 1,000,000+, optimization: 10,000,000+) |
| `experiment` | str | `main`, `sweep`, or `optimization` |
| `master_seed` | int | Study-level seed from the YAML config |
| `facility` | str | `small_clinic` / `regional_hospital` / `large_hospital` |
| `profile` | str | `resource_constrained` / `intermediate_capacity` / `high_capacity` |
| `portfolio` | str | Defense portfolio name (catalog name, or composable name like `seg-basic\|patch+1\|det1\|iso0\|bak-isolated\|idm0`) |
| `entry_point` | str | Entry category (workstation, internet_facing, privileged_system, medical_device, vendor_connection) |
| `entry_node` | int | Node id of the initial foothold |
| `n_nodes`, `n_edges` | int | Size of this trial's generated graph |
| `segmentation` | str | Effective architecture (flat / basic / least_privilege) |
| `patch_coverage` | float | **Configured (target) patch probability** in [0,1] — the policy knob, not the realized fraction |
| `realized_patch_fraction` | float | Fraction of this trial's nodes actually patched (lower than `patch_coverage` because legacy nodes get half the configured probability) |
| `detection_delay` | int | Effective mean detection delay (steps) |
| `isolation_success` | float | Per-step isolation success probability |
| `backup_strategy` | str | connected / periodic / isolated |
| `identity_controls` | 0/1 | Identity & access restrictions active |
| `rapid_isolation` | 0/1 | Same-step automated isolation active |
| `portfolio_cost` | float | Normalized cost points (NaN for sweep rows) |

### Technical outcome metrics

| Column | Type | Meaning |
|---|---|---|
| `total_compromised` | int | Nodes ever compromised (includes entry node) |
| `pct_compromised` | float | `total_compromised / n_nodes` |
| `peak_compromised` | int | Max simultaneously compromised (not yet restored) |
| `zones_reached` | int | Distinct zones (of 10) with ≥1 compromise |
| `lateral_movements` | int | Successful edge transmissions |
| `containment_step` | int | First step with every compromised node isolated; −1 if never within horizon |
| `backup_compromised` | 0/1 | Any backup-zone node compromised |
| `identity_compromised` | 0/1 | Any identity-zone node compromised |

### Healthcare-service metrics

| Column | Type | Meaning |
|---|---|---|
| `ehr_downtime_steps` … `backup_recovery_downtime_steps` | int | Steps each of the 7 services was unavailable (15 modeled min/step, A1) |
| `services_disrupted_count` | int | Services with any downtime (0–7) |
| `total_service_downtime_steps` | int | Sum of the 7 downtime columns |
| `weighted_service_hours_lost` | float | Σ weight(service) × downtime × 0.25 h (weights: A12) |
| `pct_clinical_capacity_lost` | float | Mean over the horizon of the weighted unavailable fraction of clinical services (EHR, lab, pharmacy, imaging) |
| `catastrophic` | 0/1 | ≥1 clinical service continuously down > 8 steps (pre-registered definition A14) |
| `defensive_isolation_node_steps` | int | Node-steps spent isolated while NOT compromised (availability cost of defense, incl. false positives) |

### Recovery metrics

| Column | Type | Meaning |
|---|---|---|
| `recovery_step` | int | First step after which all clinical services stayed available (0 = never disrupted; −1 = not recovered within horizon) |
| `recovered_within_horizon` | 0/1 | `recovery_step >= 0` |
| `pct_services_restored` | float | Fraction of the 7 services available at end of run |
| `unrecoverable_nodes` | int | Simulated unrecoverable-data proxy: ever-compromised data-zone nodes when backups were lost (A21); 0 otherwise |
| `backups_available` | 0/1 | Backups never compromised |
| `steps_simulated` | int | Steps actually simulated (early stop allowed once stable and fully available) |

## Processed files (`data/processed/`)

| File | Contents |
|---|---|
| `<mode>_summary_by_portfolio.csv` | Long format: facility × profile × portfolio × metric → n, mean, median, std, IQR, P90, P95, 95% bootstrap CI |
| `<mode>_summary_by_entry.csv` | Same, grouped by profile × portfolio × entry point |
| `<mode>_baseline_comparisons.csv` | Each portfolio vs. `baseline_flat` within facility × profile: relative reduction in mean weighted hours lost, absolute catastrophic-risk reduction, Cliff's delta, Mann–Whitney p (raw + Holm) |
| `<mode>_kruskal_profiles.csv` | Kruskal–Wallis across profiles per facility × portfolio |
| `<mode>_sweep_summary.csv` | Patch × delay grid: catastrophic probability, mean hours lost + CI (Figure 3 data) |
| `<mode>_portfolio_summary.csv` | Distinct candidate portfolios × profiles (192/144/96): cost, mean/median/P90 hours lost + CI, catastrophic prob + Wilson 95% CI, control indicators |
| `<mode>_recovery_summary.csv` | Censoring-aware recovery per facility × profile × portfolio: outage rate, recovery probability given outage, median/P90 recovery time among recovered |
| `<mode>_best_portfolios.csv` | Winner per profile × budget × cost-scale × criterion (4 criteria) |
| `<mode>_pareto_frontier.csv` | Cost-nondominated portfolios per profile |
| `<mode>_cost_sensitivity.csv` | Inclusion frequency of each control among winners across cost scales/budgets |
| `<mode>_minimum_budget.csv` | Smallest integer budget reaching P(catastrophic) ≤ target per profile |

## Figure data (`outputs/tables/fig*_data.csv`)

Each figure exports exactly the numbers it draws; see
`outputs/figures/captions.md` for captions.
