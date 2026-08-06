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
