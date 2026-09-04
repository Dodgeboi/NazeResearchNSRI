# Validation deviations and corrections

## 2026-08-03 - diagnostic scenario pairing and time conversion

After the primary, cross-setting, and joint-stress runs were complete, the
first summaries revealed a design error limited to two diagnostics:

1. time-step variants used different scenario identifiers, so their topologies
   and entry events were not shared; and
2. the fixed detection-improvement ladder did not preserve the intended
   90-minute detection delay at a 5-minute time step.

The recovery-horizon diagnostic also used different scenario identifiers by
horizon. That was valid for separate estimates but unnecessarily weakened the
comparison.

The original diagnostic files were renamed with the suffix
`initial_design_error.csv` and retained. The diagnostics were rerun with shared
scenario identifiers. The time-step run additionally used an explicit
90-minute detection delay for both rapid-response portfolios at every step
size. No primary, cross-setting, or joint-stress row was regenerated or
changed. The manifest records this correction.

## 2026-08-03 - exploratory fine-step pilot

The corrected 5-, 15-, and 30-minute diagnostic showed material variation in
absolute modeled loss for the layered portfolio. A new 1-, 2-, and 5-minute
pilot was therefore added after seeing that diagnostic. It is explicitly
exploratory and is used only to decide whether a finer-step fresh replication
is necessary. Its seeds and rows are not pooled with the frozen 15-minute
primary analysis.

## 2026-09-03 - methodological rebuild: endpoint, capacity, and confirmation

A full forensic audit at commit `3b734df`
(`audit/baseline_forensic_report.md`, ledger at `audit/issue_ledger.csv`)
found defects severe enough that the multi-objective results could not be
repaired by re-analysis. This entry records what changed, what was
superseded, and what was **not** carried forward.

### Why re-analysis was impossible

The sustained-outage endpoint was computed as `any()` over a four-member
clinical service set — *k* = 1 — while the manuscript defined it as "at least
four clinical services", i.e. *k* = 4. It was one of six Pareto objectives,
so the inversion propagated into the frontier, the bootstrap stability
estimates, the finalist rule, the preference selections, and every reported
outage percentage. Crucially, the per-service maximum outage streak was
never persisted to raw output, so **the endpoint could not be recomputed at
any other k from the committed data**. A fresh run was the only option.

### Changes to the specification

1. **Endpoint registry.** Every reported outcome is now defined once in
   `src/grrc/endpoints.py`, and the optimizer's objective list is read from
   it rather than kept privately. `study/MODEL_SPECIFICATION.md` is the prose
   half; `tests/test_endpoint_registry.py` asserts the two agree.

2. **Sustained clinical outage.** Implemented literally as a *k*-of-*n* rule
   with the primary *k* declared in config. **Primary k = 4**, restoring the
   definition the manuscript always stated, with the full k = 1..4 ladder
   reported in every results table. The endpoint was renamed away from
   "catastrophic" because no clinical validation of the threshold exists.

   *A justification was drafted and then withdrawn.* An earlier version of
   the specification set the primary k to 2, arguing that k = 1 would
   saturate and k = 4 would be too rare to estimate. The rebuilt discovery
   bank does not support that argument. The number of qualifying clinical
   services is almost perfectly bimodal — of 12,000 paired trials, 4,189 had
   none and 7,269 had all four, with 4.5 per cent anywhere in between — so
   candidate outage probabilities differ by about three percentage points
   between k = 1 and k = 4 and the interquartile spread is identical to
   three decimals. The k choice is not load-bearing, so it was settled on
   construct grounds alone and the strictest reading was taken. Choosing a
   looser k would have moved the science closer to where the defect
   happened to sit, with no evidence for it. The withdrawn rationale is
   recorded here rather than quietly replaced.

   The bimodality is itself a model artifact and is reported as one: binary
   per-step service availability over a shared network structure yields
   all-or-nothing clinical outcomes, whereas real incidents show partial and
   staggered service loss. That is a stronger caveat on this endpoint than
   the choice of k ever was.

3. **Raw schema.** Per-service maximum outage streaks and the indicator at
   every k are now persisted, so any auditor can recompute the endpoint at
   any k and any duration threshold without rerunning a simulation.

4. **Capacity precedence.** Posture ladders are upgrade-only: a portfolio can
   raise a profile's segmentation or backup architecture but never lower it.
   Previously every enumerated candidate overwrote both, and the weakest rung
   of each ladder was priced at zero, so a high-capacity hospital could "buy"
   flat segmentation and connected backups for **zero points**. Four of the
   seven frozen high-capacity finalists in the superseded study were exactly
   such free downgrades.

5. **Costing.** Segmentation and backup are priced on the increment actually
   bought relative to the profile baseline, as patch upgrades already were.
   Exactly one zero-cost candidate now exists per profile: the profile's own
   untouched posture.

6. **Cost and burden tables gained a `periodic_backups` rung** (1 point on
   both tables). The backup ladder is now connected → periodic → isolated on
   both the mechanism and the pricing side. Without it the intermediate
   profile's own declared `periodic` architecture — which no candidate could
   name, and which therefore never ran — had no price.

7. **Enumeration.** The backup dimension enumerates all three rungs rather
   than only its endpoints, giving 288 enumerated portfolios instead of 192.
   This is what allows every resolved posture to be named honestly.

8. **Deduplication.** Candidates are now resolved under the study config
   rather than library defaults, and the surviving representative is the one
   whose declared posture matches what it actually runs. Resolved counts are
   288 / 96 / 16 for the three profiles.

### Changes to the study design

9. **Full-space confirmation.** The confirmatory frontier ranges over every
   resolved candidate, not over a discovery-selected subset. The superseded
   holdout evaluated 57 finalists and reported the result as a frontier; a
   candidate that looked mediocre in discovery could not appear, and "7 of 7
   non-dominated" in the high-capacity profile was near-inevitable with seven
   points in six dimensions. Measured throughput made the honest version
   affordable. The finalist-only frontier is retained as a *view of the same
   data*, and the number of candidates that appear efficient only because
   their dominator was never evaluated is now reported directly.

10. **Protocol freezing.** Confirmatory protocols are content-addressed
    artifacts under `study/protocols/`. A protocol's own SHA-256 is stored
    inside it, `freeze_protocol` refuses to overwrite an existing one, and
    loading recomputes the digest and raises if the file was edited. The
    runner will not start without a protocol that verifies, refuses to run if
    the resolved candidate space has changed since freezing, and stamps the
    digest into every raw row and the manifest. Previously the "frozen"
    protocol was rewritten by its own runner on every invocation and
    contained no hash, commit, or timestamp.

11. **Retrospective status of the earlier freeze.** The pre-rebuild holdout
    freeze **cannot be established from the public record**, and no claim
    that it was prospective is made anywhere in the rebuilt work. That
    analysis is described as retrospective. Only protocols frozen under the
    mechanism above support a prospective claim, and only from their freeze
    timestamp and commit forward.

12. **Provenance.** Every run and analysis writes a manifest hashing each
    consumed input and produced output, with the code commit, dirty-tree
    state, and environment. Verification recomputes hashes and **raises** on
    mismatch. Paths are recorded POSIX-relative; the superseded holdout
    manifest used Windows separators that the declared CI runner could not
    resolve.

13. **Monte Carlo error** is reported for every stochastic objective, along
    with the count of candidate pairs the scenario bank cannot reliably
    order. The scenario count is justified by a pilot precision analysis
    embedded in the frozen protocol.

### What was superseded, not deleted

All pre-rebuild multi-objective raw and processed data were moved to
`data/multiobjective/archive_pre_rebuild/` with a README stating why no
number in it may be cited. Nothing was removed.

### Known defects deliberately carried into this stage

These are named in the model specification and tracked in the ledger. They
are **not** fixed by this entry and are scheduled for WP3. Until then they
are reported as declared assumptions with the defect named:

- `patch_effectiveness` is a single 0.85 scalar applied to every pathway,
  including credential and vendor origins where patching is mechanically
  irrelevant (ISSUE-009);
- `identity_breach_multiplier` is a whole-network scalar rather than a
  coverage-dependent authentication effect (ISSUE-010);
- `backup_traversal["isolated"]` is exactly 0.0, so isolated backups cannot
  fail by any modeled mechanism (ISSUE-006). A deliberately failing test
  (`tests/test_falsification.py`, marked xfail) keeps this visible in every
  test run rather than only in a document;
- restoration is gated on complete containment, an undocumented structural
  assumption that couples the response controls to the recovery endpoint
  (ISSUE-007);
- the 72-hour horizon with the current restore rate cannot express the
  weeks-to-months recovery tail in the public record, so non-recovery is an
  artifact of the horizon rather than a recovery estimate (ISSUE-008).

## 2026-09-03 - discovery run manifest failed verification, and why

The manifest verifier refused the first discovery run's manifest:

```
discovery_run_manifest.json does not describe the files on disk:
  inputs: configs/multiobjective_portfolio.yaml sha256 8b4ce785a816 !=
          recorded a5d0e64a659b
```

This is recorded rather than quietly repaired, because the failure is the
provenance layer working correctly on its author.

**What happened.** Discovery ran while the study config declared
`sustained_outage_min_services: 2`. The discovery data then showed the
clinical-outage outcome to be bimodal, the k = 2 justification was withdrawn,
and the config was changed to `4`. The manifest had hashed the live config
file, so it stopped describing reality the moment that file changed.

**What was and was not affected.** The changed key does not enter the
simulation dynamics at all. `propagation.py` uses it only to select which
k-of-n indicator is copied into the deprecated `catastrophic` alias column;
spread, detection, isolation and restoration are untouched, and the raw
schema emits the indicator at every k independently. So:

- the raw discovery trials are unaffected except for that one alias column,
  which was computed at k = 2 and is therefore stale;
- the discovery analysis was re-run under k = 4 and reads the explicit
  `sustained_clinical_outage_k4` column, never the alias;
- the frozen confirmatory protocol's finalist labels derive from the k = 4
  bootstrap inclusion probabilities, so they are correct.

**Resolution.** Two changes, one structural and one specific.

*Structural.* Runs now archive the exact configuration bytes they used into a
`config_snapshot/` directory beside their outputs, and the manifest hashes
the archived copies rather than the live files. An archived copy cannot
drift, and a reader can diff it against the current config to see exactly
what changed since. This is the "complete configuration snapshots"
requirement, and it would have prevented this entirely.

*Specific.* Discovery is re-run under the final configuration so that no
stale artifact remains anywhere in the record. Because the changed key does
not affect the dynamics, the re-run is expected to reproduce the previous
trials exactly apart from the alias column, and the frozen finalist labels
are expected to be identical. Both expectations are checked explicitly rather
than assumed, and the check is recorded below. Had the labels changed, the
frozen protocol would have had to be superseded under a new name rather than
reused.

The pre-rebuild archive under `data/multiobjective/archive_pre_rebuild/` is
exempt from manifest verification. Those manifests predate this schema and
are retained only as a record; their README states that no number in them may
be cited.

### Verification of the discovery re-run (2026-09-03)

Both expectations stated above were checked rather than assumed.

**Frozen finalist labels are identical.** Re-deriving the finalist rule from
the re-run discovery analysis reproduces the frozen protocol's identities
exactly: 40 resource-constrained, 16 intermediate-capacity, 3 high-capacity,
with zero added and zero removed in every profile. The frozen confirmatory
protocol therefore still describes the study that was run, and is reused
rather than superseded. Had a single label moved, the protocol would have had
to be re-frozen under a new name and the confirmatory bank re-run against it.

**The stale artifact is gone.** The deprecated `catastrophic` alias column in
the re-run raw file now equals `sustained_clinical_outage_k4`, the configured
primary. Previously it carried the k = 2 value from the superseded config.

**The manifest now verifies**, because the run archived the exact
configuration bytes it used into `config_snapshot/` and hashes those rather
than the live files. A later edit to the study config can no longer
invalidate a completed run's provenance.

## 2026-09-04 - WP3: mechanism repairs and parameter uncertainty

The scored rubric put 9 of its 19 missing points on three misapplied
mechanisms and on the absence of parameter uncertainty. This entry records
that work, including one repair that was wrong on the first attempt.

### Mechanisms

1. **Pathway classification.** Every edge is now labelled by the mechanism
   that traverses it: exploitation of a vulnerability on the target, use of
   valid credentials or tokens, or passage through a third-party gateway.
   Credential takes precedence over vendor, because an attacker holding
   valid credentials does not need the vulnerability. This is what lets a
   control act only where it could act.

2. **Patching (ISSUE-009).** A patch now removes susceptibility on the
   exploit pathway, does essentially nothing on the credential pathway, and
   acts partly on the vendor pathway. One scalar across every edge was on
   the handoff's red-line list.

3. **Identity (ISSUE-010).** A compromised identity zone accelerates
   credential-mediated traversal only. Identity controls carry explicit
   coverage and effectiveness on the covered fraction; the remainder stands
   for unenrolled accounts, service accounts, legacy protocols and token
   theft.

4. **Isolated backups (ISSUE-006), corrected twice.** The first attempt set
   the per-step traversal into an isolated backup zone to 0.02, reasoning
   that a small nonzero value made the architecture falsifiable. **That was
   wrong, and the test suite caught it:** the aggressive validation case
   went to a 100% backup failure rate, because 0.02 per step compounds to
   near-certainty across 864 steps. A per-step probability models *delay*,
   not rarity.

   The traversal is therefore zero again — a correctly isolated backup has
   no network path — and falsifiability moved to two per-incident
   mechanisms: an isolation lapse, in which a nominally isolated estate
   turns out to have a usable path, and a residual failure covering causes
   the network does not model. Both are drawn once per incident and shared
   across candidates in a scenario. Under the aggressive config isolated
   backups now fail 8.3% of the time against 100% for connected. The strict
   `xfail` that pinned this defect now passes.

### Parameter uncertainty

Ten unidentified coefficients carry prespecified ranges, sampled once per
scenario and shared by every candidate replaying it. Parameter uncertainty
is therefore another latent dimension of the common-random-numbers design:
comparisons stay matched, and objectives become marginal over the ranges
rather than conditional on a point estimate. Every draw is written into
every raw row, which makes a variance-based global sensitivity analysis free.

Four falsification tests had to disable sampling, because they pin a
coefficient and assert what the mechanism must then do; leaving sampling on
would have had them assert something about a random draw. A new test asserts
that override directly rather than leaving it implicit in a fixture.

### Consequences for the study design

The precision analysis was re-run and its answer changed shape. Most
objectives still need 28 to 297 paired scenarios. Two are now unattainable:
resource-constrained sustained outage needs about 1,400, and high-capacity
mean disruption needs roughly 80,000 because its 16 candidates differ by an
interquartile range of 0.066 weighted service-hours.

**Three of the four high-capacity objectives now have an interquartile range
of exactly zero across all 16 candidates.** No scenario count resolves them,
because there is nothing to resolve. That is a finding about the profile
rather than a budget problem, and it is reported as one.

A uniform 400 scenarios per candidate replaces v1's per-profile allocation:
allocating scenarios where they are scarce only helps when the binding
requirement is attainable somewhere. Both under-resolved objectives are
recorded in the frozen protocol as under-resolved.

### Superseded protocol

Confirmatory protocol v1 is superseded rather than edited. The repairs
changed the mechanisms and parameter uncertainty changed the physics, so v1
no longer describes a study anyone would run. The freezing machinery refused
to overwrite it, which is the machinery working; v2 was frozen under a new
name and committed before any v2 output existed. Results generated under v1
are retained and are not reinterpreted under v2.

### Correction: the zero-interquartile-range reading was wrong

The frozen protocol `multiobjective_confirmatory_v2` records, in its
`trials_rationale`, that three of four high-capacity objectives had an
interquartile range of exactly zero across all sixteen candidates and that
"no scenario count resolves them at all -- that is a finding about the
profile, not a budget problem."

**The confirmatory data refute that reading.** At 400 scenarios the sixteen
high-capacity candidates take sixteen distinct values on mean disruption,
spanning 13.07 to 15.02 weighted service-hours, with an interquartile range
of 0.743. The pilot's zero ranges came from its thirty-scenario resolution:
at that size the achievable outcome values are coarse enough that most
candidates tie exactly.

What the precision estimator was actually reporting is that a thirty-scenario
pilot cannot see the differences it was being asked to size. A correlation-
ratio requirement computed from a pilot too small to resolve the quantity
returns an unattainable number, and "this quantity cannot be resolved" and
"this pilot cannot resolve it" are easy to confuse. We confused them.

**The protocol is not edited.** A frozen protocol whose rationale turns out
to be wrong is corrected in the open, not amended, or freezing it means
nothing. The correction is recorded here and stated in the manuscript's
study-design section. No result changes: the scenario count of 400 was
chosen as the affordable maximum and would have been the same under the
correct reading.

### Defect found after WP3: the committed archive was the superseded bank

The confirmatory raw bank is 101 MB and is committed gzipped. For one commit
the committed archive held the **superseded v1 bank of 137,600 executions**
while the uncompressed file beside it held the **v2 bank of 160,000**. Every
check in `scripts/run_full_audit.py` passed regardless, and so did CI.

The reason is worth stating plainly, because it is a general failure mode and
not a slip. `scripts/unpack_raw.py` decided whether an uncompressed file was
current by comparing modification times. In the working tree, the CSV had just
been written by the v2 run, so it was newer than the archive and the script
correctly did nothing — and no other check in the audit ever opens the
archive. The entire provenance chain therefore verified against a file that
the repository could not reproduce. On a fresh clone the sequence would have
restored the v1 bank over the v2 manifests, and every manifest check would
have failed for reasons that pointed at the wrong thing.

A hash-based provenance layer that trusts a timestamp anywhere has a hole
exactly the size of that timestamp.

**Repair.** The archive is regenerated from the current bank
(SHA-256 `6b558145ae77…`, 5.7 MB). `unpack_raw.py` now decides currency by
decompressing and comparing SHA-256, and on a disagreement it **exits
non-zero without writing**, because it cannot tell whether the archive or the
working copy is the stale one, and guessing wrong in one direction discards
hours of compute that the repository does not hold. `--restore` forces the
archive to win when the author knows it should. Five tests in
`tests/test_provenance.py` pin this, including a case where the stale archive
sits beside a fresher file with a far newer mtime — the exact configuration
that went undetected.

**No reported number changes.** The v2 bank was the analyzed data throughout;
what was wrong was the copy committed for others to check against, which is a
reproducibility defect rather than a result defect. It is recorded here rather
than quietly fixed because the audit harness passed while it was true, and
that is the more useful thing for a reader to know about the harness.

**Follow-on: the archive was redundant.** The uncompressed 97 MB bank was
*also* tracked. Committing both made `unpack_raw.py` decorative — the
uncompressed file arrived with every clone, so the restore path was dead code
that no reader ever executed, and the stale archive could therefore sit in
the repository indefinitely without anyone touching it. The uncompressed file
is now git-ignored and the archive is the committed artifact, which makes the
restore path load-bearing and exercised by every reproduction. Earlier
history retains the uncompressed blobs; it is preserved rather than
rewritten, so the saving is prospective.
