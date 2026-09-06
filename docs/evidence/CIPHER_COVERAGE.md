# CIPHER construct-coverage audit

We use Straw, Tully, and Dameff's [CIPHER release v1.0.1](https://doi.org/10.5281/zenodo.17344644),
archived October 13, 2025. The dataset is CC BY 4.0, copyright 2025 Isabel
Straw. The CSV is preserved byte-for-byte, with its original license and
citation files, under ../../data/cipher/raw.

The downloaded archive's MD5 is dd8c21831164565baec999df0e9a56a6, matching
Zenodo. Its SHA-256 and the CSV SHA-256 are in source_manifest.json.
The upstream citation file internally calls the version 1.0.0 and includes
an older repository link and one author spelling discrepancy; our citation
uses the actual archive DOI and the README author spelling.

The [analysis plan](../../study/CIPHER_COVERAGE_PLAN.md) records what was
inspected before aggregation: the schema, first two rows, and distinct
category labels. The [mapping](../../data/cipher/processed/domain_mapping.csv)
then assigns each technical domain to a modeled digital service, an absent
explicit service, or an unspecified category.

| Coverage | Coded records | Distinct reference links |
| --- | ---: | ---: |
| Represented digital service | 229 | 32 |
| Absent explicit service | 85 | 19 |
| Unspecified | 2 | 1 |
| Total | 316 | 36 |

Reference counts overlap across categories. Rows can reuse evidence from
the same source and sources can describe the same incident. There are no
exact duplicate rows; this does not make the rows independent. The sole
time-label correction changes Firsy Day to First Day and is reported.

Ninety-seven records have Week 2 or First Month annotations. First Week
straddles 72 hours and is reported separately. These are annotations on
harm records, not measured restoration times. The dataset's Clinical Impact
Score is not used to set service weights or infer control effectiveness.

Leaving out one reference link at a time gives absent-service shares of
25.7% to 30.3% and later-annotation shares of 17.4% to 31.7%. These are
influence diagnostics, not confidence intervals. The wide latter range
shows that one source contributes many later annotations.

The added evidence supports concrete statements about what the model
represents. It does not calibrate the simulator, validate patient outcomes,
or resolve the recovery-rate mismatch in the existing external comparisons.
