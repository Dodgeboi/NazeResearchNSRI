# Superseded pre-rebuild multi-objective results

Everything in this directory was generated at commit `3b734df` and is
**superseded**. It is retained, not deleted, because the handoff requires
that raw inputs and old results are never removed merely because they
conflict with a rebuilt analysis.

Do not cite any number from this directory. Three defects make these results
uninterpretable as stated (see `audit/baseline_forensic_report.md`):

1. **The sustained-outage endpoint is inverted.** Every `catastrophic` column
   here means "at least one of four clinical services was down more than two
   hours", while the manuscript defined the endpoint as requiring four. The
   per-service outage streaks were not persisted, so these files cannot be
   recomputed at any other service count. That is why the confirmatory study
   is a fresh run rather than a re-analysis (audit ISSUE-001, ISSUE-002).

2. **Capacity profiles were overwritten at zero cost.** Every candidate here
   set both segmentation and backup architecture, and the weakest rung of
   each was priced at zero, so a high-capacity hospital could "buy" flat
   segmentation and connected backups for nothing. Four of the seven frozen
   high-capacity finalists are such free downgrades (ISSUE-003, ISSUE-004).

3. **The holdout frontier is finalist-only.** It ranges over 57
   discovery-selected candidates, not the resolved space, and was presented
   without a candidate-set qualifier (ISSUE-012).

The replacement data live in `../discovery/` and `../confirmatory/`.
