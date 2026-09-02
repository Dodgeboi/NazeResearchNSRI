# Observed data

This directory keeps public real-world records separate from synthetic simulation output.

## Sources

### THREAT hospital ransomware data

Neprash, McGlave, and Nikpay published the hospital/market event file used by *Hacked to Pieces? The Effects of Ransomware Attacks on Hospitals and Patients* as openICPSR project V1, DOI [10.3886/E235483V1](https://doi.org/10.3886/E235483V1). The repository page labels the deposit CC BY 4.0.

`raw/threat_database.csv` is a normalized UTF-8 export of the public browser preview. It retains all 1,999 displayed records and 14 columns while removing surrounding cell whitespace. The analysis collapses exact duplicate hospital-event rows using Medicare ID, THREAT event ID, and attack date, then takes the maximum of duplicate operational flags. This yields 149 attacked hospital-event records across 74 events.

The source page requires an ICPSR sign-in for the original-file download. Before journal submission, replace the normalized preview export with the depositor's original CSV and codebook, rerun the analysis, and document whether any values or row counts change.

### CISA Known Exploited Vulnerabilities

`raw/cisa_known_exploited_vulnerabilities.json` is the complete CISA catalog version 2026.09.01 from the [official JSON feed](https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json). It contains 1,687 vulnerabilities confirmed as exploited in the wild; 352 have `knownRansomwareCampaignUse` set to `Known`.

CISA's tag is used only to create an auditable inventory of plausible ransomware-linked vulnerability scenarios. The share of catalog entries tagged `Known` is not an attack probability, a healthcare-sector rate, or a measure of patch efficacy.

Exact source URLs, timestamps, representations, and SHA-256 hashes are in `raw/source_manifest.json`.

## Rebuild the summaries

```bash
python scripts/analyze_observed_data.py
```

The command writes:

- `processed/threat_empirical_summary.csv`;
- `processed/threat_event_breadth.csv`;
- `processed/cisa_kev_summary.csv`;
- `processed/cisa_ransomware_kev.csv`;
- `processed/cisa_ransomware_kev_vendor_summary.csv`; and
- `processed/observed_simulation_bridge.csv`.

It uses existing simulation summaries only. It does not generate or rerun simulations.
