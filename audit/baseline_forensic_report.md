# WP0 — Baseline forensic snapshot

**Audited object:** `Dodgeboi/NazeResearchNSRI`
**Commit:** `3b734df5df95c299c91a37470300e2aac7654f65` ("Add paired multi-objective portfolio study")
**Working tree at snapshot:** clean (`git status --porcelain` → 0 entries)
**Snapshot taken:** 2026-09-03
**Work branch:** `rebuild/wp0-wp2`

This report records the state of the repository *before* any rebuild edit. It
makes no changes to results. Every finding below was reproduced directly in
this environment; none is carried over on trust from the handoff document.

---

## 1. Environment

| Item | Value |
|---|---|
| OS | Ubuntu 24.04.4 LTS (x86_64) |
| CPU | 2 logical cores |
| Memory | 7 GiB |
| Python | 3.12.3 (`pyproject.toml` requires `>=3.12`) |
| Install | `python3.12 -m venv .venv; pip install -r requirements.txt; pip install -e .` |

Pinned dependency versions actually resolved:

```
numpy==2.5.1      pandas==3.0.3     scipy==1.18.0     networkx==3.6.1
matplotlib==3.11.0  PyYAML==6.0.3   pytest==9.1.1     tqdm==4.68.4
```

`requirements.txt` pins exact versions. `numpy==2.5.1` requires Python
`>=3.12`, so the stated Python floor is load-bearing and correct.

### Reproduction friction observed

Installing under the environment's default interpreter (Python 3.11) fails
with `No matching distribution found for numpy==2.5.1` and
`Package 'grrc' requires a different Python`. The README states the 3.12
requirement, so this is documented rather than defective, but the failure
mode is opaque. **Recorded as ISSUE-014.**

## 2. Test and validation baseline

| Command | Result |
|---|---|
| `pytest -q` | **70 passed**, 0 failed |
| README claim | "70 passing tests" |

The test count matches the README exactly. The suite runs in well under a
minute. Test files: `test_multiobjective.py`, `test_paired_design.py`,
`test_defenses.py`, `test_propagation.py`, `test_service_availability.py`,
`test_reproducibility.py`, `test_validation_cases.py`, `test_observed_data.py`,
`test_network_generator.py` (904 lines total).

**The suite passes and still misses every semantic defect in Section 4.** This
is the single most important fact in this report: a green test run is not
evidence of correctness here, because no test asserts the *manuscript's*
definition of any endpoint. The tests verify that the code does what the code
does.

## 3. Computational scale and feasibility

Measured on this hardware, single-threaded, using the worst case
(`seg-flat|patch+0|det0|iso0|bak-connected|idm0` in `resource_constrained`,
which never triggers the `early_stop` path):

```
20 trials in 3.23 s  →  162 ms/trial
```

| Workload | Trials | Projected wall time (2 workers) |
|---|---:|---|
| Existing discovery bank | 12,960 | ≈ 18 min |
| Existing finalist holdout | 8,550 | ≈ 12 min |
| **Full-space holdout, all resolved candidates × 150** | ≈ 52,000 | **≈ 70 min** |

This is the decisive scheduling finding: **a true full-space confirmatory
frontier is computationally affordable on this hardware.** Blocker 3 does not
have to be resolved by renaming the result; it can be resolved by actually
computing it. Most candidates carry controls and terminate early, so the
projection above is an upper bound.

## 4. Confirmed defects

Each defect below was verified by reading the implementation and, where
possible, by recomputing against committed artifacts. Handoff blocker numbers
are given for cross-reference.

### 4.1 Sustained-outage definition inversion — *handoff blocker 1* — **CONFIRMED, severe**

`src/grrc/enums.py:97` defines exactly four clinical services:

```python
CLINICAL_SERVICES: tuple[Service, ...] = (
    Service.EHR, Service.LABORATORY, Service.PHARMACY, Service.IMAGING,
)
```

`src/grrc/propagation.py:332`:

```python
catastrophic = any(
    rec.max_streak[s] > sim.catastrophic_service_steps
    for s in CLINICAL_SERVICES)
```

`docs/manuscript/main.tex:199` (Table 1, "Sustained outage"):

> Fraction of trials with more than two modeled hours of continuous
> unavailability **in at least four clinical services**

Because the clinical set has exactly four members, "at least four" means **all
four**. The implementation fires when **any one** qualifies. The manuscript
describes an endpoint requiring *k = 4*; the code computes *k = 1*.

This is not a wording quibble. `catastrophic_probability` is one of the six
Pareto objectives, so the inversion propagates into the frontier, the bootstrap
stability estimates, the finalist selection rule, the preference-scenario
choices, and every sustained-outage number in the manuscript — including the
headline 95.3%, 97.3%, 54.7%, 31.3%, 15.3% and 2.7% in Table 2.

**Aggravating finding (not in the handoff).** The raw result CSVs persist
per-service *total* downtime (`ehr_downtime_steps`, …) but **not** per-service
maximum continuous streak. `rec.max_streak` is consumed inside
`propagation.py` and discarded. The endpoint therefore **cannot be recomputed
from the committed raw outputs at any k**. An external auditor cannot check
this objective at all without rerunning the simulation. Recorded separately as
ISSUE-002.

A second-order semantic point: `max_streak` is a per-service maximum over the
whole horizon, so a *k*-of-4 rule counts services that each had a long outage
at *some* time, not necessarily concurrently. The manuscript's phrasing implies
neither reading explicitly. The specification must state which is intended.

### 4.2 Capacity profile is overwritten by portfolio at zero cost — *handoff blocker 2* — **CONFIRMED, severe**

`src/grrc/defenses.py`, `effective_settings()`:

```python
segmentation = portfolio.segmentation or SegmentationLevel(profile.base_segmentation)
...
backup = (portfolio.backup_override.value
          if portfolio.backup_override else profile.backup_strategy)
```

`enumerate_portfolios()` **always** sets both fields (segmentation ∈
{flat, basic, least_privilege}, backup ∈ {connected, isolated}). The `or` and
the conditional are therefore never reached for any optimizer candidate: the
portfolio value always wins.

`portfolio_cost()` charges for `BASIC`/`LEAST_PRIVILEGE` segmentation and for
`ISOLATED` backup, and charges **nothing** for `FLAT` or `CONNECTED`.

Consequences, verified against the frozen finalist list in
`data/multiobjective/processed/multiobjective_holdout_protocol.json`:

- The `high_capacity` profile declares `base_segmentation: least_privilege` and
  `backup_strategy: isolated`. The candidate
  `seg-flat|patch+0|det0|iso0|bak-connected|idm0` **strips both** and costs
  **0 points**. It is present in the frozen high-capacity finalist set and
  reported as non-dominated.
- Four of the seven frozen high-capacity finalists are `seg-flat` or
  `bak-connected` downgrades of the profile's own declared posture.
- Patch coverage is handled correctly (priced on rungs actually gained from the
  profile baseline), so the model is *internally inconsistent* about whether a
  profile's posture is exogenous capacity or a free decision variable.
- `intermediate_capacity` declares `backup_strategy: periodic`
  (`backup_traversal = 0.30`). No enumerated portfolio can express `periodic`,
  so **every** optimizer candidate silently replaces it with `connected` (1.0)
  or `isolated` (0.0). The profile's declared middle tier is unreachable in the
  entire study.

Net effect: the cheapest candidates in the strong profiles are free
*downgrades*, which is why low-cost points look attractive on the frontier. The
separation between environmental capacity and purchased controls — the thing
the three profiles exist to represent — does not hold in the code.

### 4.3 Holdout frontier is finalist-only — *handoff blocker 3* — **CONFIRMED**

Verified against committed data:

| Stage | resource_constrained | intermediate_capacity | high_capacity |
|---|---:|---:|---:|
| Resolved candidates evaluated in discovery | 192 | 144 | 96 |
| Discovery point-estimate Pareto | 31 | 19 | 5 |
| Frozen finalists carried to holdout | 29 | 21 | 7 |
| Holdout non-dominated | 22 | 20 | 7 |

The holdout "frontier" is computed among 57 pre-selected finalists, not among
all 432 resolved profile-candidates. A candidate that was mediocre in discovery
and excellent on holdout is structurally unable to appear. The
high-capacity row is the clearest illustration: 7 of 7 candidates are
non-dominated, which is close to arithmetically inevitable in six dimensions
with seven points, yet it is presented as a frontier result.

The manuscript is partly careful here — Results says "22 of 29 **tested**"
— but the README states "Forty-six of 52 discovery-frontier finalists remained
non-dominated on holdout data", Figure 2's caption says "Held-out
profile-specific trade-offs. Lines connect non-dominated points" with no
candidate-set qualifier, and the abstract's "no bundle minimized every
objective" is asserted without noting the restricted comparison set. A reader
cannot tell from the figures that the frontier is conditioned on discovery.

Per Section 3, this is fixable by computation rather than by relabelling.

### 4.4 Holdout freeze is self-rewriting — *handoff blocker 4* — **CONFIRMED**

`scripts/run_multiobjective_holdout.py` writes
`data/multiobjective/processed/multiobjective_holdout_protocol.json` and then
immediately calls `run_multiobjective_holdout(...)` **in the same process**:

```python
manifest_path.write_text(json.dumps({...}))
run_multiobjective_holdout(load_config(args.config), finalists, args.output, ...)
```

The protocol is written before the simulation within a single run, but it is
**regenerated on every invocation** and its content is derived from whatever
discovery tables are on disk at the time. There is no hash, no timestamp, no
code commit, and no config hash inside it. `"status": "frozen before holdout
generation"` is an unverifiable self-assertion: nothing in the repository or
its history distinguishes a genuine prospective freeze from a protocol written
after the fact. The manuscript's claim that "No candidate was added or removed
after holdout outcomes were observed" cannot be checked by a reader.

### 4.5 Provenance and manifest defects — *handoff blocker 5* — **PARTIALLY CONFIRMED**

Recomputed SHA-256 for the two archived public sources:

| File | Manifest SHA-256 | Recomputed | Match |
|---|---|---|---|
| `threat_database.csv` | `a78291e0…27b536` | `a78291e0…27b536` | ✅ |
| `cisa_known_exploited_vulnerabilities.json` | `c4560f42…4db675` | `c4560f42…4db675` | ✅ |

The handoff's reported source-manifest hash mismatch **does not reproduce at
this commit**; `data/observed/raw/source_manifest.json` is accurate. That
finding is downgraded.

The multi-objective manifests are genuinely deficient:

- `data/multiobjective/raw/multiobjective_portfolio_optimization_manifest.json`
  records seeds and counts but **no hash of any input or output**, no config
  hash, no code commit, no environment, no timestamp.
- `data/multiobjective/holdout_processed/multiobjective_manifest.json` records
  file *paths* with **Windows backslash separators**
  (`data\\multiobjective\\raw\\…`), which are not portable and are not
  resolvable on the CI runner declared in `.github/workflows/tests.yml`. It
  contains no hashes either.
- No manifest records the SHA-256 of `configs/multiobjective_portfolio.yaml`,
  `configs/defense_costs.yaml`, or `configs/defense_burdens.yaml`, all three of
  which determine reported objective values.

So: source provenance is sound, **result provenance is not**. Nothing in the
pipeline would fail if a config changed between the raw run and the analysis.

## 5. Additional defects found in this audit (not in the handoff)

### ISSUE-006 — Isolated backup is unconditionally unreachable

`src/grrc/config.py:111`:

```python
backup_traversal = {"connected": 1.0, "periodic": 0.30, "isolated": 0.0}
```

A traversal multiplier of exactly `0.0` makes every edge into the backup zone
have compromise probability identically zero. Isolated backups therefore
**cannot fail by any modeled mechanism**. The handoff's own red-line list
forbids "Backup isolation eliminates compromise", and the evidence memorandum
requires nonzero residual failure. Sophos 2024 reports attackers attempted
backup compromise in 95% of healthcare victims and succeeded in 66% of
attempts; a hard zero is not a defensible representation of *any* real backup
architecture, isolated or otherwise. It also makes `protected_backups` a
deterministic win in the objective space.

### ISSUE-007 — Restoration is gated on full containment

`propagation.py`, `run()`:

```python
contained = not bool(np.any(self.comp & ~self.isolated))
...
if contained:
    self._restore(t, backups_available)
```

No node begins restoring until **every** actively compromised node is isolated.
Real incident response restores in parallel with containment, prioritising
clinical systems. This assumption materially lengthens outages under wide
compromise and shortens them under fast containment, which directly couples the
detection/isolation controls to the recovery objective through a structural
choice that appears nowhere in the manuscript's Methods.

### ISSUE-008 — Recovery rate implies whole-inventory restore in hours

`restore_rate_fraction: 0.0066666667` × ~250 nodes ≈ 1.67 nodes/step, floor
0.333, at 5-minute steps ≈ 20 nodes/hour. A 250-node estate restores in ≈ 12.5
hours once contained. The evidence memorandum's THREAT cohort reports a mean
disruption of 15.8 days with 16/374 events exceeding four weeks. The 72-hour
horizon plus this rate cannot express the observed tail at all, and
`nonrecovery_probability` is consequently an artifact of the horizon rather
than a recovery estimate. The manuscript acknowledges "Technical recovery is
not operational recovery" but still reports non-recovery as a decision
objective.

### ISSUE-009 — `patch_effectiveness: 0.85` applied universally

`propagation.py`: `patch_factor = np.where(net.patched, 1.0 - sim.patch_effectiveness, 1.0)`.
A single scalar reduces compromise probability by 85% on every patched node
against every pathway, including credential-origin and vendor pathways where
patching is mechanically irrelevant. This is on the handoff's red-line list
("Patching is 85% effective against ransomware") and is unsupported by any
cited source. The value is currently presented as a "stress assumption" in the
manuscript, which is the right label but is not matched by a stress *range* —
it is a fixed point estimate in every frozen config.

### ISSUE-010 — `identity_breach_multiplier` is a whole-network scalar

A compromised identity zone multiplies **every** edge probability by 1.5. The
evidence memorandum is explicit that MFA/identity effects must be
coverage-dependent and confined to eligible authentication pathways, and that
the Microsoft Azure AD estimate must not become a network-wide multiplier. The
same objection applies symmetrically to the breach multiplier.

### ISSUE-011 — Objective saturation degrades the frontier

At the current *k* = 1 definition, `catastrophic_probability` is 0.953 and
0.973 for the two reported resource-constrained preference selections. An
objective pinned near 1.0 across most of the candidate set carries almost no
dominance information, which inflates frontier size — an effect the manuscript
attributes solely to many-objective geometry ("dominance becomes less common as
objectives are added") without noting that one objective is saturated.

### ISSUE-012 — Abstract/Results framing mismatch on frontier counts

The abstract reports "Forty-six of 52 discovery-frontier finalists remained
non-dominated: 22/28 … and all 19/19 and 5/5", while Results reports the
holdout frontier as "22 of 29 … 20 of 21 … all 7". Both are internally
consistent (survival of discovery-frontier members vs. membership among tested
candidates), but they are adjacent, use the same words, and differ. A reader
will read them as contradictory.

### ISSUE-013 — Manuscript cites a public-preview data normalization

Section "Observed-data bridge" uses a THREAT CSV "normalized from its displayed
public preview" because the original requires ICPSR sign-in. The limitation is
disclosed, but the derived counts (149 hospital-event records, 74 events,
25.7% multi-hospital) are used in the Results and in the failure-boundary
argument. The evidence memorandum requires reconciliation against the published
article's ≈160 affected hospitals and the 198/374 multi-facility statistic
before these are load-bearing.

### ISSUE-014 — Reproduction fails opaquely below Python 3.12

See Section 1. Documented but not guarded; no version check produces a clear
error.

## 6. Claim → code → data traceability matrix

Manuscript claims checked directly against committed artifacts at this commit.

| # | Manuscript claim | Locus | Artifact checked | Status |
|---|---|---|---|---|
| C1 | 192 composable portfolios enumerated | `defenses.enumerate_portfolios` | 3×4×2×2×2×2 = 192 | ✅ verified |
| C2 | 192 / 144 / 96 behaviorally distinct per profile | Methods §2.1 | `discovery raw.groupby(profile).portfolio.nunique()` → 192/144/96 | ✅ matches |
| C3 | Discovery bank 12,960 executions | Abstract | discovery raw rows = 12,960 | ✅ matches |
| C4 | 30 paired scenarios per candidate | Methods §2.3 | scenarios/profile = 30 | ✅ matches |
| C5 | 55 discovery point-estimate Pareto candidates (31/19/5) | Results §3.1 | `processed/portfolio_pareto_frontier.csv` → 31/19/5 | ✅ matches |
| C6 | 57 finalists (29/21/7) | Methods §2.5 | holdout protocol JSON counts | ✅ matches |
| C7 | 8,550 holdout executions | Abstract | holdout raw rows = 8,550 | ✅ matches |
| C8 | 150 fresh paired scenarios per finalist | Methods §2.5 | scenarios/profile = 150 | ✅ matches |
| C9 | Holdout frontier 22/29, 20/21, 7/7 | Results §3.1 | `holdout_processed/portfolio_pareto_frontier.csv` | ✅ matches |
| C10 | 21,510 new executions total | Conclusion | 12,960 + 8,550 = 21,510 | ✅ matches |
| C11 | **Sustained outage = >2h in ≥4 clinical services** | Table 1 | `propagation.py:332` uses `any()` over 4 services | ❌ **contradicted** |
| C12 | Sustained-outage probabilities 95.3 / 97.3 / 54.7 / 31.3 / 15.3 / 2.7 % | Table 2 | recomputable only under the k=1 code path | ⚠️ **numerically consistent with code, inconsistent with C11** |
| C13 | "Profile names … vary starting patch coverage, detection delay, isolation success, legacy fraction, **segmentation**, **backup connectivity**, and a normalized budget" | Methods §2.1 | segmentation and backup are overwritten by every candidate | ❌ **contradicted** |
| C14 | Held-out frontier presented without candidate-set qualifier | Fig. 2 caption, README | finalist-only by construction | ⚠️ **misleading** |
| C15 | "No candidate was added or removed after holdout outcomes were observed" | Methods §2.5 | protocol JSON regenerated by the runner; no hash/commit | ⚠️ **unverifiable** |
| C16 | 70 automated tests | Methods §2.7 | `pytest -q` → 70 passed | ✅ matches |
| C17 | THREAT: 149 records, 74 events, 19 multi-hospital (25.7%) | Methods §2.6 | `data/observed/processed/` | ⚠️ **unreconciled with published article** |
| C18 | CISA KEV v2026.09.01, 1,687 records, 352 ransomware-tagged | Methods §2.6 | archived JSON, hash verified | ✅ verified |
| C19 | Cost/burden are normalized points, not dollars | throughout | consistently labeled in code and outputs | ✅ verified |
| C20 | "Isolated backup" as a purchasable control | Methods §2.1 | traversal multiplier is exactly 0.0 | ❌ **unfalsifiable control** |

**Score: 12 verified, 4 contradicted or misleading, 4 unverifiable or
unreconciled.**

## 7. Rubric position at baseline

Applying the handoff's own score caps to the confirmed findings:

| Cap trigger | Status at baseline | Cap |
|---|---|---|
| Unresolved semantic mismatch | ISSUE-001 (C11/C13) | **≤ 74** |
| Unverifiable full-space/holdout claim | ISSUE-003, ISSUE-004 | ≤ 78 |
| Incomplete source/result provenance | ISSUE-005 (result side) | ≤ 82 |
| "Calibrated hospital model" claim without telemetry | **not triggered** — the manuscript is consistently restrained | — |
| No external validation / no failure reporting | **not triggered** — §3.4 reports failure boundaries honestly | — |
| Manuscript not reproducible from recorded inputs | partially — results reproduce, provenance does not bind | ≤ 80 |

**Binding cap at baseline: 74.** The handoff's ≈62/100 estimate is consistent
with this audit.

## 8. What is genuinely strong here

Recording this matters, because the rebuild must not damage it:

- The paired common-random-numbers design is correct and tested
  (`test_paired_design.py`); candidates genuinely replay one latent scenario.
- Exact enumeration with behavioral deduplication, rather than a metaheuristic,
  is the right choice at this problem size and is honestly described.
- Six objectives reported separately, with declared weights applied *after* the
  frontier, is methodologically sound.
- Cost and burden are labeled as normalized points everywhere — in code, in
  output columns, in figure captions, and in prose. No dollar claim is made.
- The observed-data bridge is allowed to contradict the model, and §3.4
  ("What the observed data did and did not validate") reports failure rather
  than fit. This is unusual and should be preserved verbatim in spirit.
- The limitations section is already restrained and largely accurate.
- Raw trial-level data are committed, which is what made this audit possible.

The problem is not that the paper overclaims in prose. It is that the prose
describes a model the code does not implement.

## 9. Machine-readable output

The full ledger is at `audit/issue_ledger.csv`, with one row per issue and
columns for severity, handoff blocker mapping, evidence locus, affected
artifacts, and resolution status.
