# First validation of an ATT&CK-based clinical-impact model against real coded harm

Recorded 2026-09-20, before running the analysis. A new, additive study. To our
knowledge (prior-art check this session) no published work calibrates an
ATT&CK-based clinical-impact model against a coded patient-harm corpus; that
first validation is the contribution. It is a validation/benchmark result, not a
new theorem.

## Question

Does the clinical-impact model's predicted distribution of harm across the four
modelled clinical services (EHR, laboratory, pharmacy, imaging) match the
distribution of real coded patient harm in the CIPHER corpus?

## Held-out design (circularity pre-emption)

The single biggest threat is training-on-test: deriving the model from CIPHER and
then "validating" against CIPHER. We forbid that. The predicted profiles use only
model inputs that are independent of CIPHER:

- `uniform`: the ATT&CK null. ATT&CK carries no clinical-service resolution, so its
  honest prior over the four services is uniform.
- `assumed`: the model's own `SERVICE_DEGRADATION` (in `hospital_attack_model`),
  which was set from the Neprash aggregate care-disruption figures, not from
  CIPHER, normalised to a profile over the four services.

CIPHER is held out strictly as external ground truth. The CIPHER-derived
degradation intervals from the separate `cipher_inference` study are NOT used here.

## Method

1. Observed profile: CIPHER high-severity (impact score >= tau) counts per clinical
   service via `grrc.cipher_bounds.high_severity_counts`, conditioned on the four
   modelled services (the unmodelled residual is reported separately, not folded in).
2. Discrepancy: total-variation distance between each predicted profile and the
   observed profile.
3. Goodness-of-fit: an exact Monte-Carlo multinomial test of H0 "the observed
   per-service counts are drawn from the predicted profile" (test statistic: the
   multinomial log-likelihood / chi-square; p-value by simulating counts under H0
   at the observed total, fixed seed). Reported alongside the asymptotic chi-square.
4. Partial-identification-robust reconciliation (the distinctive statistic): using
   the bounded-underreporting envelope from
   `grrc.cipher_bounds.partial_identification_bounds`, find the minimum gamma at
   which every predicted per-service share falls inside CIPHER's share interval --
   how much reporting bias would be required to reconcile model and data. gamma=0
   iff the predicted profile already lies in the observed shares (exact-ish match);
   a large reconciling gamma is evidence of a real gap.
5. Per-service residuals (predicted minus observed) to show direction of
   miscalibration; tau sensitivity (e.g. tau in {6,7,8}).
6. Overlay artifact (secondary, honest framing "CIPHER supplies what ATT&CK lacks"):
   for each modelled clinical service, CIPHER's empirical specialty mix, mean
   severity, and onset-timing profile -- the clinical-resolution layer ATT&CK has no
   native signal for.

## Scope and limits (stated up front)

- CIPHER is a convenience sample of *reported* harms: selection/reporting bias, no
  denominator, English-language and severe-harm skew. The comparison tests
  consistency with *this corpus*, not population truth; the reconciling-gamma makes
  the reporting-bias assumption explicit rather than hidden.
- The four-service conditioning drops CIPHER's large unmodelled residual (reported,
  not hidden); the model simply has no construct for those domains.
- Single-label coding (one specialty/domain per record) and coarse ATT&CK->service
  mapping; real incidents are multi-technique and multi-specialty.
- Small counts -> low power; the GoF and TV are reported with these caveats.
- Not causal, not a population incidence estimate, and not a new statistical test:
  the novelty is the first application of a calibration comparison between an
  ATT&CK-clinical model and coded harm, with circularity and selection bias handled
  honestly.

## Software and reporting

Pure-array kernel, no I/O. Validated by: a hand-computed total-variation oracle;
the Monte-Carlo GoF being approximately uniform under a true H0 and small under a
gross mismatch (seeded); reconciling-gamma monotonicity and the gamma=0 case; and
invalid-input rejection. Deterministic (fixed MC seed): re-running reproduces every
CSV byte for byte. Provenance manifest over the CIPHER corpus, the pinned ATT&CK
bundle, and the source modules. All note numbers generated from committed tables.
