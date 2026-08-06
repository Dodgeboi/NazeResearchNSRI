# Fine-step replication protocol

**Frozen:** 2026-08-03, before `data/fine_step_replication` was generated
**Status:** post-diagnostic local replication; not externally preregistered

## Reason for this phase

The frozen 15-minute validation succeeded on its comparative criteria, but a
prespecified numerical diagnostic showed material changes in absolute outcomes
at 5, 15, and 30 minutes. An explicitly exploratory 1-, 2-, and 5-minute pilot
then suggested that the paired portfolio comparison was much more stable than
the absolute outcomes at fine resolution. Because these diagnostics were seen
before this protocol was written, this phase is a transparent post-diagnostic
replication, not confirmation independent of prior results.

## Frozen design

- Five-minute step and 72-hour horizon.
- Clock-time hazard and duration conversions from the prior 15-minute
  reference; these remain stress assumptions, not empirical rates.
- Reference `baseline_flat` versus `seg_detect_backup` only.
- 500 new paired scenarios, balanced across five entry types.
- 128 new Latin-hypercube stress settings with 10 paired scenarios per
  setting.
- Fresh master seeds and scenario identifiers.
- Primary outcome: paired difference in weighted service-hours lost.

The same sample-size logic as the 15-minute phase is retained. The paper will
report both phases. It will emphasize the direction and distribution of paired
effects, and it will identify absolute hours, relative percentages, and the
sustained-outage indicator as time-step sensitive.

## Success rule

The layered portfolio must have a paired bootstrap 95% interval below zero,
lower mean loss in at least 95% of joint settings, and a positive fifth
percentile of setting-specific relative reduction. Regardless of success, the
time-step sensitivity remains a limitation and all results remain conditional
on the synthetic model.
