# Model Assumptions Registry

Every numeric or structural assumption in the study, its default value,
where it is configured, and why it exists. **All values are modeling
choices, not real-world measurements.** Anything labeled `configs/*.yaml`
can be changed without touching code; the rest live as documented
defaults in `src/grrc/config.py` and can be overridden in YAML too.

| ID | Assumption | Default | Where |
|----|-----------|---------|-------|
| A1 | One simulation step represents 15 minutes of wall time. Used only to convert step counts into interpretable "hours"; the dynamics are unitless. | `step_minutes: 15` | `simulation` |
| A2 | Simulation horizon is 192 steps (48 modeled hours). Attacks and recovery beyond the horizon are censored and flagged (`recovery_step = -1`). | `max_steps: 192` | `simulation` |
| A3 | Facility sizes: small clinic 40–60 nodes, regional hospital 200–300, large hospital 750–1,000. These are simulation settings, not claims about real hospitals. | `facilities` | `configs/*.yaml` / defaults |
| A4 | Zone mix: workstations 40%, EHR 8%, lab 6%, pharmacy 5%, imaging 6%, medical devices 15%, admin 8%, identity 4%, backup 4%, internet-facing 4% (±10% jitter per trial, min 2 nodes/zone). | `zone_proportions` | `network` |
| A5 | Per-edge, per-step compromise probability = base_spread_rate × privilege(source) × edge access × edge strength × traversal modifier × vulnerability(target) × patch factor(target); every factor ∈ [0,1]. | formula | `propagation.py` |
| A6 | Patching is strong but imperfect: a patched node's susceptibility is multiplied by (1 − 0.85) = 0.15. The `patch_immunity` validation check verifies the limiting case (effectiveness 1.0 ⇒ immune). | `patch_effectiveness: 0.85` | `simulation` |
| A7 | Base spread rate 0.35 per permitted edge per step before modifiers. Chosen so an undefended flat network is overwhelmed within the horizon (consistent with the qualitative behavior of fast ransomware campaigns) while defended networks are not; the patch×detection sweep and validation suite probe sensitivity. | `base_spread_rate: 0.35` | `simulation` |
| A8 | Detection is geometric: each compromised node is detected each step with probability detect_capability / mean_delay (deterministic `fixed` model available for tests). Medical devices (capability 0.5) and legacy nodes (0.7) are harder to monitor. | `detection_model` | `simulation`, `network` |
| A9 | Isolation of a detected node succeeds each step with the profile's `isolation_success`; rapid automated isolation raises this to 0.95 and attempts isolation in the detection step itself. | profiles / `RAPID_ISOLATION_SUCCESS` | YAML / `defenses.py` |
| A10 | Compromised nodes stop providing service immediately; isolated nodes (including false-positive isolations, rate 0.002/node/step for 8 steps) also stop providing service. This creates the security-vs-availability tradeoff. | `false_positive_*` | `simulation` |
| A11 | A service is available iff its core node is functional AND ≥60% of its zone's nodes are functional AND (for EHR, lab, pharmacy, imaging, scheduling) the identity service is available. | `service_functional_fraction: 0.6` | `simulation` |
| A12 | Service criticality weights for weighted service-hours: EHR 1.0, pharmacy 0.9, identity 0.9, lab 0.8, imaging 0.7, backup 0.6, scheduling 0.4. | `service_weights` | config |
| A13 | If any identity-zone node is compromised, all spread probabilities are multiplied by 1.5 (capped at 1) — an abstraction of credential abuse. Identity controls halve traversal into the identity zone. | `identity_breach_multiplier: 1.5` | `simulation` |
| A14 | **Catastrophic disruption** (pre-registered definition): at least one clinical service (EHR, lab, pharmacy, imaging) unavailable for **more than 8 consecutive steps** (2 modeled hours). Configurable. | `catastrophic_service_steps: 8` | `simulation` |
| A15 | Recovery begins only after containment (every compromised node isolated); restore capacity is max(1, 2% of nodes)/step, ×0.25 if backups were compromised; each node takes 2 steps to restore; core/critical nodes first. | `restore_*` | `simulation` |
| A16 | **Defense costs are normalized model points, not dollars** (basic segmentation 3, least-privilege 5, patch ladder step 2, detection tier 3, rapid isolation 5, protected backups 2, identity controls 4). Patch upgrades cost per ladder rung actually gained, so reaching 90% costs more from a lower baseline. All conclusions are re-tested at ±25% and ±50% cost scaling. | `configs/defense_costs.yaml` | YAML |
| A17 | Backup connectivity: `connected` = normal traversal into the backup zone; `periodic` = traversal ×0.30 (intermittent exposure); `isolated` = **no inbound network edges at all** (offline/immutable). | `backup_traversal` | `network` |
| A18 | Capacity profiles are neutral parameter bundles (patch 25/50/75%, detection delay 24/12/3 steps, isolation success 0.5/0.7/0.9, legacy fraction 35/15/5%, budgets 5/10/15). They are **not** labels for any country, region, or income group. | `profiles` | `configs/*.yaml` / defaults |
| A19 | Entry foothold always succeeds at t=0 in the chosen category (phishing/zero-day abstraction); the study conditions on "an attack has begun". | design | `simulation.py` |
| A20 | Privilege modifiers: admin 1.0, standard 0.8, low 0.55. Admin privilege exists in the admin/identity zones plus 3% of other nodes. | `privilege_modifiers` | `network` |
| A21 | If backups are compromised, ever-compromised nodes in data-bearing zones (EHR, lab, pharmacy, imaging, backup) count as simulated unrecoverable data. | rule | `propagation.py` |
| A22 | Cross-zone access rules per architecture are fixed allow-lists (`REQUIRED_PATHS`, `BASIC_EXTRA_PATHS` in `network_generator.py`); flat allows every pair. Cross-boundary traversal modifiers: flat 1.0, basic 0.5, least-privilege 0.25 (×0.6 extra into identity/backup). | `segmentation_modifiers` | `network` |

## How assumptions were chosen

Parameter values were selected to (a) reproduce *qualitative* behaviors
reported in public incident documentation — fast lateral movement on
flat networks, long dwell times without monitoring, backup destruction
preceding data loss (see `report/references.md`) — and (b) produce
non-degenerate dynamics (neither instant saturation nor no spread) at
the default settings, verified by the validation suite. No parameter is
calibrated to a specific real incident or hospital, and results are
reported as *model* outcomes conditional on this registry.
