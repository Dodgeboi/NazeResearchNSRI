# Dependency-closed controlled islanding: specification, version 1

**Status:** proposed method with one **exploratory** experiment. No protocol
was frozen before that experiment, so none of its numbers may be reported as
confirmatory. Results: [`data/islanding/RESULTS.md`](../data/islanding/RESULTS.md).
**Scope:** adds one purchasable method and one availability rule that applies
only while that method's breakers are open. Nothing about the model changes
while `simulation.islanding_enabled` is false (section 7).
**Authority:** where this document and the code disagree, this document is the
specification and the code is the defect, as in
[`MODEL_SPECIFICATION.md`](MODEL_SPECIFICATION.md).

---

## 0. What is claimed to be new, and what is not

Every ingredient of this method has a precedent. The claim is about the
combination and about one condition it makes testable. That distinction has to
survive into any paper, so it comes first.

**The method.** When compromise is first detected, split the hospital network
into pre-planned islands. Islands are *vertical*: each holds a slice of every
clinical zone, plus a core replica for every service and an identity replica.
Every island that stays clean keeps serving on its own. Reconnect once the
estate is contained and the primaries are clean.

**The condition it makes testable.** *Disconnection is protective only if what
is disconnected is dependency-closed.* Cutting part of a hospital off from its
central identity and EHR core is itself an outage, even with no attacker in
that part at all (`tests/test_islanding.py::test_disconnection_without_closure_is_itself_an_outage`).

**A design rule that falls out of it.** A service needs a fraction θ of its
capacity. Losing one of *k* equal islands leaves (k − 1)/k. So one lost island
is survivable only if **k ≥ 1/(1 − θ)**. At the model's declared θ = 0.60 that
is 3 islands; 2 islands keep no service up once either island is lost. This is
arithmetic, not a finding. It is stated because it is the first thing an
islanding design gets wrong, and the experiment tests it in a way that removes
its main confound (section 5).

### Closest prior work found, and the specific difference from each

| Prior work | What it does | Difference |
|---|---|---|
| Controlled islanding in power grids, including adversarial variants (Niu, Sahabandu, Clark & Poovendran, 2021, [arXiv:2108.01628](https://arxiv.org/abs/2108.01628)) | Opens pre-planned breakers so each island balances generation and load | Different domain and constraint. The constraint here is service-dependency closure, not power balance, and the trigger is detected adversarial lateral movement, not a physical cascade. That paper explicitly does not treat IT networks. |
| Cell-based architecture in cloud reliability engineering | Partitions a platform into self-contained cells, each with its own dependencies, to cap blast radius | Cells are *permanently* separate and serve disjoint users. Islands are connected in normal operation and sever only on detection, so normal clinical workflow is unchanged. |
| Dynamic or self-healing segmentation; detection-triggered host/segment isolation (EDR network containment) | Tightens segmentation or isolates segments when a threat is seen | *Horizontal*: cuts between functions, and must leave required cross-function paths open (EHR to identity, etc.) or services break. Attackers move along exactly those paths. Vertical islands can cut *every* cross-island path because each island's required paths are internal. This is the comparator the experiment runs (`zone`). |
| Micro-segmentation "lockdown" on detection (zero-trust segmentation products that restrict every host to essential flows when ransomware is seen) | Cuts nearly every lateral path, including within a zone, and keeps only the required application flows | The strongest prior art here, and the comparator most likely to beat the method. It still has to leave every required cross-function path open, because each function has one central instance, and those paths connect every part of the estate. The experiment runs it (`micro`) and also runs islanding *on top of* it (`dcci3_micro`), which asks whether islanding adds anything beyond the best segmentation rather than only whether it beats it. |
| Epidemic containment by edge removal while preserving connectivity (network science) | Removes edges to stop spread while keeping the largest connected component | Preserves generic connectivity, not per-service dependency closure. A connected network can still leave every service without identity. |
| Hospital cyber-resilience optimization (Helfrich & Grass, 2026, [arXiv:2601.11129](https://arxiv.org/abs/2601.11129)) | Defender–attacker–defender planning over service capacity, patient transfer and backup capacity | Strategic, cross-hospital planning. It does not model in-incident partitioning of one hospital's network. |
| Health systems disconnecting an affected facility during an incident | Sever the affected site from the enterprise network | Practice, without dependency closure. Clean sites then lose central identity and EHR. Modeled here as `crude3`, so its harm can be measured against the method on matched scenarios. |

**How far this search goes.** Web searches (September 2026) for controlled or
network islanding in IT and ransomware settings, cell-based architecture in
hospitals, dependency-aware containment, detection-triggered partitioning with
local authentication failover, and hospital network resilience models. No
direct precedent for the combination turned up. **That is not a novelty
claim.** Before one appears in a paper it needs a systematic review of IEEE
Xplore, ACM DL and the intrusion-tolerance and survivability literature
(Ellison et al.'s survivable network systems, MAFTIA-era intrusion tolerance,
mission-aware response), which are the likeliest places for a precedent.

---

## 1. Mechanism

**Plan.** In every zone, the node at position *j* (ascending node index) joins
island *j mod k*. The primary core of each service sits at position 0, so it is
in island 0. With dependency closure, island *i* designates its first node in
each service zone as that service's core replica. Without it, only the primary
exists. The plan is deterministic in the network alone. In the paired design it
is therefore identical for every candidate replaying a scenario.

**Trip.** When cumulative detections reach `island_trigger_detections`
(default 1), the breakers open. From the next step, no inter-island edge can be
traversed. That includes *intra-zone* edges between islands, which
segmentation never cuts.

**Availability while severed.** A supporting node serves only if it is
functional, its island's core for that service is functional, and, for an
authentication-dependent service, its island's identity replica is available.
The service is available if the serving fraction meets θ. With one island this
reduces *exactly* to `service_dependencies.service_availability`, which a
property test checks on 10,000 random states.

**Restoration while severed.** A severed island with no active compromise
cannot be reinfected while the breakers stay open. So restoration may begin
inside it before global containment (`island_local_restore`). Every island that
is not contained stays under the global gate. Capacity accrues only on steps
with work, and at most one step's worth is banked, so islanding cannot release
stored-up restoration throughput in a burst.

**Reconnect.** When the estate is contained *and* every primary core is
functional. Reconnecting earlier could strand an island whose replica is
serving while the primary it would fall back to is still down.

---

## 2. Declared assumptions

| Assumption | Choice | Why |
|---|---|---|
| Replicas in connected operation | Standby only; the connected rule is unchanged | Keeps the effect attributable to islanding, not to ordinary high availability. |
| Replica credential stores | Shared: identity compromise anywhere still boosts credential spread everywhere | Conservative. Replicas of one directory do not isolate a stolen credential. |
| Availability semantics while severed | Hospital-level serving fraction against the same θ | Generalizes the existing rule exactly. The alternative, per-island capacity serving each island's own patients, is not modeled. |
| Replica placement | Existing nodes promoted to core; no nodes added | Keeps the graph, and so the paired design, unchanged. It understates attack surface (section 3). |
| Replica restore priority | Raised to the primary core's criticality (2.0) | A plan that designates replicas as cores should restore them as cores. |
| Island assignment | Round-robin by node index | Naive and balanced. An optimized assignment is future work, and would only strengthen the result. |

---

## 3. Limitations that bear directly on the result

These are not boilerplate. Each could change the sign or size of the effect,
and a reader should attack them first.

1. **Detection timing is favorable to islanding.** Islanding helps only when
   the breakers trip before the attacker has footholds in every island. The
   model's attacker spreads epidemically *while* detection runs. Real
   hospital ransomware often dwells quietly, builds access everywhere, and
   then encrypts everywhere at once. Against that attacker, detection-triggered
   islanding trips too late. **The simulator does not model that attacker, and
   no result here says anything about it.**
2. **The attacker is not adaptive.** It does not target replicas, anticipate
   islanding, or pre-position in each island.
3. **Edges carry attack, not workflow.** In this model service availability
   never depends on network connectivity. So the operational cost of running
   severed appears only through the per-island core and identity requirement.
   Data divergence between replicas, reconciliation after reconnect, and
   clinicians who cannot reach records held in another island are not
   represented.
4. **False trips are not modeled.** Every trial is an incident, so the cost of
   tripping on a false alarm cannot appear.
5. **Replicas add no attack surface here.** Real replicas would be
   high-value targets in their own right.
6. **Local restoration interacts with structural assumption S1.** The
   experiment reports the method with and without it, and with S1 off.

---

## 4. Parameters

| Parameter | Default | Status |
|---|---|---|
| `islanding_enabled` | `false` | master switch |
| `island_count` | 3 | the smallest useful value at θ = 0.60 |
| `island_dependency_closed` | `true` | `false` models crude disconnection |
| `island_trigger_detections` | 1 | declared |
| `island_local_restore` | `true` | ablated in the experiment |
| `island_partition` | `service_chain` | `zone` is the prior-art comparator |
| cost | 6 points | normalized, **not** dollars; the highest in the table |
| burden | 5 points | replica upkeep, per-island downtime workflows, breaker drills |

---

## 5. The experiment

`scripts/run_islanding_experiment.py` replays one bank of paired scenarios
under 13 conditions. It uses `configs/multiobjective_portfolio.yaml`, the
study's primary design, with its declared parameter uncertainty, and a fresh
seed so the frozen confirmatory bank is untouched.
`scripts/analyze_islanding_experiment.py` writes the tables and renders
`data/islanding/RESULTS.md` from them. No number in that file is typed by hand.

Two design choices carry most of the weight.

**The micro-segmentation comparator.** The model charges nothing for cutting an
edge, since service availability never depends on connectivity. So a lockdown
that cuts every intra-zone edge costs nothing here, although in a real
hospital an application server and its database share a zone and must talk.
`micro` is therefore an *upper bound* on segmentation-based lockdown, not a
realistic version of it. Beating it is a stronger result than beating `zone`.
`dcci3_micro` asks the more useful question: does islanding add anything on
top of it?

**The threshold test.** Comparing two islands against three confounds the
capacity rule with containment, since fewer islands also cut fewer edges. The
cut does not depend on θ, but the rule does. So the share of the three-island
benefit that two islands recover should be low at θ = 0.60 (k_min = 3) and high
at θ = 0.45 (k_min = 2). That shift holds the spread effect fixed. It is not a
perfectly clean test: θ also changes how any compromise maps to outage, for
every island count. A shift in the predicted direction is *consistent with*
the rule; it does not isolate it perfectly.

### 5.1 Record of design decisions, in order

Recorded because this run is exploratory. What was decided before and after
seeing results changes how much the results can bear.

1. **Before any results:** conditions `none`, `zone`, `crude3`, `dcci3`,
   `dcci2`, `dcci4`, `dcci3_nolocal` and the three `*_ungated` conditions, the
   bootstrap design, and the contrasts. A 4-scenario smoke test was run first,
   to check that the code executed.
2. **Before any results:** the three `*_theta45` conditions, added after that
   smoke test and before the full run, once it was clear that `dcci2` vs
   `dcci3` alone could not separate the capacity rule from weaker containment.
3. **After seeing the first 13 conditions:** `micro` and `dcci3_micro`. The
   `zone` comparator leaves every intra-zone edge open, so a win against it
   was too weak to support "beats prior art". This comparator was added
   *because* it is the one most likely to overturn that claim, not to support
   it.
4. **After the first full run:** a defect was found and fixed, but the data
   were **not** regenerated. The first run's assembly step read its
   checkpoints with pandas' default float parser, which is inexact and
   changed 19 values in the last digit. That affects no reported number, but
   it means the committed `data/islanding/raw/islanding_experiment.csv.gz`
   will not reproduce byte for byte from the fixed runner. A full
   regeneration was started and then stopped when the work moved to the
   autonomous-defender study (`docs/aidc26`), which evaluates the same
   response modes as scripted defenders on a fresh paired bank and is where
   the islanding results that the paper reports come from.
5. **Consequently:** the committed islanding data contain the first 13
   conditions only. `micro` and `dcci3_micro` are defined in the runner but
   have never been run by it; the micro-segmentation comparator was
   evaluated instead as a scripted defender in the autonomous-defender study.
   Running the runner now produces all 15 conditions, with exact reads.

---

## 6. Claims this specification forbids

Inheriting `MODEL_SPECIFICATION.md` section 0, and adding:

1. That islanding reduces real hospital ransomware harm. The simulator
   supports statements about the simulator.
2. That any effect size here is a property of islanding rather than of the
   declared attacker (section 3, item 1) and the declared parameters.
3. That the method is novel, without the systematic review section 0 requires.
4. That the exploratory experiment is confirmatory.

---

## 7. Reproducibility guarantee

While `islanding_enabled` is false, which is the default everywhere, the
method is absent:

* `enumerate_portfolios()` yields the original 288 candidates in their
  original order with their original names. Islanded candidates are appended
  with a `|isl1` suffix only when the dimension is on.
* The result schema is unchanged. Island columns are keyed off the run-level
  switch, never the row's portfolio.
* `CONTROL_COLUMNS` stays at seven and `portfolio_features` stays
  8-dimensional.
* With no island plan, `restore_priority` *is* `net.criticality` — the same
  object — so restoration order cannot move, and the connected availability
  function is the unmodified original.
* `full_defense` keeps its frozen meaning; `full_defense_islanded` is the
  all-controls condition.
* An undeclared `islanding` tariff raises rather than pricing the method at
  zero (audit ISSUE-003/ISSUE-004).

This was checked empirically, not only asserted. 1,260 trials, plus the full
288-candidate space's costs, burdens, price features, resolved settings and
deduplication, produce **byte-identical** output on this branch and on `main`.

---

## 8. What has not been done

* **No confirmatory run.** A protocol must be frozen first, per the procedure
  behind `study/protocols/multiobjective_confirmatory_v2`.
* No systematic literature review (section 0).
* No adaptive, dwell-then-detonate attacker (section 3, item 1). This is the
  experiment most likely to overturn the result, and the most important next
  step.
* No false-trip cost, no replica attack surface, no data reconciliation.
* No optimization of island assignment or of the trigger threshold.
* No review by hospital IT, security or clinical-operations staff, who would
  have to say whether islanded operation is operable at all.
* The islanding dimension has not been through the optimizer, the price-region
  retention screen, or the claim-contract machinery.
