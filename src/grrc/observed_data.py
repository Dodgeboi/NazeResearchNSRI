"""Observed-data summaries and an explicit bridge to simulation outputs.

The functions in this module never fit mechanistic simulation parameters.
They keep observational endpoints separate from modeled proxies so that a
numerical resemblance cannot be mistaken for calibration or validation.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


THREAT_COLUMNS = {
    "medicare_id",
    "attacked",
    "attack_date",
    "er_diversion",
    "cancel_delay",
    "threat_id",
    "nearest_neighbor",
}


def _require_columns(frame: pd.DataFrame, required: set[str], source: str) -> None:
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"{source} is missing required columns: {missing}")


def _binary(series: pd.Series) -> pd.Series:
    """Parse a public-data 0/1 field while retaining missing values."""
    values = pd.to_numeric(series.replace("", np.nan), errors="coerce")
    invalid = values.dropna()[~values.dropna().isin([0, 1])]
    if not invalid.empty:
        raise ValueError(f"expected a binary field, found {invalid.iloc[0]!r}")
    return values


def load_threat_data(path: str | Path) -> pd.DataFrame:
    """Load the public THREAT hospital/market file without coercing CCNs."""
    frame = pd.read_csv(path, dtype=str, keep_default_na=False)
    frame.columns = [str(column).strip() for column in frame.columns]
    _require_columns(frame, THREAT_COLUMNS, "THREAT data")
    for column in frame.columns:
        frame[column] = frame[column].astype(str).str.strip()
    frame["medicare_id"] = frame["medicare_id"].str.zfill(6)
    frame["attacked_flag"] = _binary(frame["attacked"])
    frame["er_diversion_flag"] = _binary(frame["er_diversion"])
    frame["cancel_delay_flag"] = _binary(frame["cancel_delay"])
    frame["nearest_neighbor_flag"] = _binary(frame["nearest_neighbor"])
    frame["attack_date_parsed"] = pd.to_datetime(
        frame["attack_date"], errors="coerce", format="%m/%d/%Y"
    )
    return frame


def unique_hospital_events(frame: pd.DataFrame) -> pd.DataFrame:
    """Collapse exact/duplicate hospital-event rows without losing flags."""
    attacked = frame.loc[frame["attacked_flag"] == 1].copy()
    keys = ["medicare_id", "threat_id", "attack_date"]
    if attacked.empty:
        return attacked
    return (
        attacked.groupby(keys, dropna=False, as_index=False)
        .agg(
            er_diversion_flag=("er_diversion_flag", "max"),
            cancel_delay_flag=("cancel_delay_flag", "max"),
            attack_date_parsed=("attack_date_parsed", "first"),
            source_row_count=("medicare_id", "size"),
        )
        .sort_values(["attack_date_parsed", "threat_id", "medicare_id"])
        .reset_index(drop=True)
    )


def summarize_threat(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return traceable metrics and event-breadth records for THREAT."""
    hospital_events = unique_hospital_events(frame)
    if hospital_events.empty:
        raise ValueError("THREAT data contains no attacked hospital-event records")

    def observed_fraction(column: str) -> tuple[int, int, float]:
        observed = hospital_events[column].dropna()
        numerator = int(observed.sum())
        denominator = int(observed.size)
        return numerator, denominator, numerator / denominator

    diversion_n, diversion_d, diversion_p = observed_fraction(
        "er_diversion_flag"
    )
    cancel_n, cancel_d, cancel_p = observed_fraction("cancel_delay_flag")
    jointly_observed = hospital_events.dropna(
        subset=["er_diversion_flag", "cancel_delay_flag"]
    ).copy()
    either = (
        (jointly_observed["er_diversion_flag"] == 1)
        | (jointly_observed["cancel_delay_flag"] == 1)
    )
    both = (
        (jointly_observed["er_diversion_flag"] == 1)
        & (jointly_observed["cancel_delay_flag"] == 1)
    )

    event_breadth = (
        hospital_events.groupby("threat_id", as_index=False)
        .agg(
            attacked_hospitals=("medicare_id", "nunique"),
            first_attack_date=("attack_date_parsed", "min"),
            any_er_diversion=("er_diversion_flag", "max"),
            any_cancel_delay=("cancel_delay_flag", "max"),
        )
        .sort_values(["first_attack_date", "threat_id"])
        .reset_index(drop=True)
    )
    event_breadth["multi_hospital_event"] = (
        event_breadth["attacked_hospitals"] > 1
    )

    metrics: list[dict[str, Any]] = []

    def add(
        metric: str,
        value: Any,
        unit: str,
        numerator: Any = "",
        denominator: Any = "",
        interpretation: str = "",
    ) -> None:
        metrics.append(
            {
                "metric": metric,
                "value": value,
                "unit": unit,
                "numerator": numerator,
                "denominator": denominator,
                "interpretation": interpretation,
            }
        )

    add("source_rows", len(frame), "rows")
    add("unique_source_rows", len(frame.drop_duplicates()), "rows")
    add("attacked_hospital_event_records", len(hospital_events), "records")
    add(
        "unique_attacked_hospitals",
        hospital_events["medicare_id"].nunique(),
        "hospitals",
    )
    add("unique_attack_events", len(event_breadth), "events")
    add(
        "attack_date_min",
        hospital_events["attack_date_parsed"].min().date().isoformat(),
        "date",
    )
    add(
        "attack_date_max",
        hospital_events["attack_date_parsed"].max().date().isoformat(),
        "date",
    )
    add(
        "er_diversion_fraction",
        diversion_p,
        "fraction of attacked hospital-events with observed flag",
        diversion_n,
        diversion_d,
        "Observed operational endpoint; not equivalent to modeled downtime.",
    )
    add(
        "cancel_or_delay_fraction",
        cancel_p,
        "fraction of attacked hospital-events with observed flag",
        cancel_n,
        cancel_d,
        "Observed operational endpoint; not equivalent to modeled downtime.",
    )
    add(
        "either_diversion_or_cancel_delay_fraction",
        float(either.mean()),
        "fraction of jointly observed attacked hospital-events",
        int(either.sum()),
        int(len(jointly_observed)),
    )
    add(
        "both_diversion_and_cancel_delay_fraction",
        float(both.mean()),
        "fraction of jointly observed attacked hospital-events",
        int(both.sum()),
        int(len(jointly_observed)),
    )
    add(
        "multi_hospital_event_fraction",
        float(event_breadth["multi_hospital_event"].mean()),
        "fraction of attack events",
        int(event_breadth["multi_hospital_event"].sum()),
        int(len(event_breadth)),
        "Directly exposes the single-facility model's missing event breadth.",
    )
    add(
        "median_attacked_hospitals_per_event",
        float(event_breadth["attacked_hospitals"].median()),
        "hospitals per event",
    )
    add(
        "max_attacked_hospitals_per_event",
        int(event_breadth["attacked_hospitals"].max()),
        "hospitals per event",
    )
    return pd.DataFrame(metrics), event_breadth


def summarize_cisa_kev(
    path: str | Path,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Extract ransomware-linked records from CISA's authoritative KEV JSON."""
    with Path(path).open(encoding="utf-8") as stream:
        catalog = json.load(stream)
    vulnerabilities = catalog.get("vulnerabilities")
    if not isinstance(vulnerabilities, list):
        raise ValueError("CISA KEV JSON has no vulnerabilities list")
    if int(catalog.get("count", -1)) != len(vulnerabilities):
        raise ValueError("CISA KEV count does not match the vulnerability list")

    records = pd.DataFrame(vulnerabilities)
    required = {
        "cveID",
        "vendorProject",
        "product",
        "vulnerabilityName",
        "dateAdded",
        "dueDate",
        "knownRansomwareCampaignUse",
        "requiredAction",
    }
    _require_columns(records, required, "CISA KEV data")
    ransomware = records.loc[
        records["knownRansomwareCampaignUse"].eq("Known")
    ].copy()
    ransomware["date_added"] = pd.to_datetime(ransomware["dateAdded"])
    ransomware["due_date"] = pd.to_datetime(ransomware["dueDate"])
    ransomware["remediation_window_days"] = (
        ransomware["due_date"] - ransomware["date_added"]
    ).dt.days
    if (ransomware["remediation_window_days"] < 0).any():
        raise ValueError("CISA KEV contains a negative remediation window")

    export_columns = [
        "cveID",
        "vendorProject",
        "product",
        "vulnerabilityName",
        "dateAdded",
        "dueDate",
        "remediation_window_days",
        "requiredAction",
        "notes",
        "cwes",
    ]
    for column in export_columns:
        if column not in ransomware:
            ransomware[column] = ""
    subset = ransomware[export_columns].rename(
        columns={
            "cveID": "cve_id",
            "vendorProject": "vendor_project",
            "vulnerabilityName": "vulnerability_name",
            "dateAdded": "date_added",
            "dueDate": "due_date",
            "requiredAction": "required_action",
        }
    )
    subset["cwes"] = subset["cwes"].map(
        lambda value: ";".join(value) if isinstance(value, list) else value
    )
    subset = subset.sort_values(["date_added", "cve_id"]).reset_index(drop=True)

    known_count = len(subset)
    catalog_count = len(records)
    metrics = pd.DataFrame(
        [
            {"metric": "catalog_version", "value": catalog["catalogVersion"], "unit": "version"},
            {"metric": "date_released", "value": catalog["dateReleased"], "unit": "timestamp"},
            {"metric": "catalog_vulnerability_count", "value": catalog_count, "unit": "vulnerabilities"},
            {"metric": "known_ransomware_use_count", "value": known_count, "unit": "vulnerabilities"},
            {
                "metric": "known_ransomware_use_fraction",
                "value": known_count / catalog_count,
                "unit": "fraction of KEV catalog",
            },
            {
                "metric": "unique_ransomware_linked_vendors",
                "value": subset["vendor_project"].nunique(),
                "unit": "vendors",
            },
            {
                "metric": "unique_ransomware_linked_products",
                "value": subset[["vendor_project", "product"]].drop_duplicates().shape[0],
                "unit": "vendor-product pairs",
            },
            {
                "metric": "median_remediation_window_days",
                "value": float(subset["remediation_window_days"].median()),
                "unit": "days",
            },
        ]
    )
    vendor_summary = (
        subset.groupby("vendor_project", as_index=False)
        .agg(
            ransomware_linked_cves=("cve_id", "nunique"),
            products=("product", "nunique"),
        )
        .sort_values(
            ["ransomware_linked_cves", "vendor_project"],
            ascending=[False, True],
        )
        .reset_index(drop=True)
    )
    return metrics, subset, vendor_summary


def _metric_value(metrics: pd.DataFrame, metric: str) -> Any:
    values = metrics.loc[metrics["metric"].eq(metric), "value"]
    if len(values) != 1:
        raise ValueError(f"expected exactly one metric named {metric!r}")
    return values.iloc[0]


def build_observation_bridge(
    threat_metrics: pd.DataFrame,
    cisa_metrics: pd.DataFrame,
    primary_summary_path: str | Path,
    recovery_summary_path: str | Path,
) -> pd.DataFrame:
    """Map observed endpoints to existing outputs without equating constructs."""
    primary = pd.read_csv(primary_summary_path)
    recovery = pd.read_csv(recovery_summary_path)
    if len(primary) != 1:
        raise ValueError("expected one row in the fine-step primary summary")
    required_primary = {
        "baseline_sustained_outage_fraction",
        "treatment_sustained_outage_fraction",
    }
    _require_columns(primary, required_primary, "primary simulation summary")
    required_recovery = {
        "horizon_hours_variant",
        "portfolio",
        "recovery_within_horizon_fraction",
    }
    _require_columns(recovery, required_recovery, "recovery summary")

    seven_day = recovery.loc[
        recovery["horizon_hours_variant"].eq(168)
        & recovery["portfolio"].eq("baseline_flat")
    ]
    if len(seven_day) != 1:
        raise ValueError("expected one seven-day baseline recovery row")

    return pd.DataFrame(
        [
            {
                "evidence_source": "THREAT openICPSR hospital-event data",
                "observed_endpoint": "Emergency-department diversion",
                "observed_result": f"{float(_metric_value(threat_metrics, 'er_diversion_fraction')):.1%} of attacked hospital-events with an observed flag",
                "simulation_endpoint": "Sustained clinical-service outage indicator",
                "simulation_result": f"{float(primary.iloc[0]['baseline_sustained_outage_fraction']):.1%} reference; {float(primary.iloc[0]['treatment_sustained_outage_fraction']):.1%} layered",
                "relationship": "Low-comparability operational proxy",
                "verdict": "Do not calibrate: diversion depends on demand, staffing, policy, and regional capacity absent from the model.",
            },
            {
                "evidence_source": "THREAT openICPSR hospital-event data",
                "observed_endpoint": "Canceled or delayed care",
                "observed_result": f"{float(_metric_value(threat_metrics, 'cancel_or_delay_fraction')):.1%} of attacked hospital-events with an observed flag",
                "simulation_endpoint": "Binary digital-service downtime",
                "simulation_result": "Seven service-specific downtime outputs",
                "relationship": "Construct bridge only",
                "verdict": "The data justify service-oriented outcomes but cannot convert modeled hours to canceled cases.",
            },
            {
                "evidence_source": "THREAT openICPSR hospital-event data",
                "observed_endpoint": "Multi-hospital attack breadth",
                "observed_result": f"{float(_metric_value(threat_metrics, 'multi_hospital_event_fraction')):.1%} of observed attack events affected multiple hospitals",
                "simulation_endpoint": "Facilities per run",
                "simulation_result": "Exactly one synthetic facility",
                "relationship": "Direct structural check",
                "verdict": "Fail: the current model cannot represent multi-facility or regional propagation and spillover.",
            },
            {
                "evidence_source": "Neprash, McGlave, and Nikpay (2026)",
                "observed_endpoint": "Hospital-volume recovery",
                "observed_result": "17%-24% first-week volume decline; recovery over roughly three weeks",
                "simulation_endpoint": "Technical/service recovery",
                "simulation_result": f"{float(seven_day.iloc[0]['recovery_within_horizon_fraction']):.0%} of reference runs recovered within 7 days",
                "relationship": "External duration-pattern check",
                "verdict": "Fail: technical recovery is too fast and is not the same construct as operational volume recovery.",
            },
            {
                "evidence_source": "CISA Known Exploited Vulnerabilities catalog",
                "observed_endpoint": "Confirmed exploited vulnerabilities tagged for ransomware use",
                "observed_result": f"{int(float(_metric_value(cisa_metrics, 'known_ransomware_use_count')))} of {int(float(_metric_value(cisa_metrics, 'catalog_vulnerability_count')))} catalog entries",
                "simulation_endpoint": "Generic vulnerability and patch modifiers",
                "simulation_result": "No CVE or product identity",
                "relationship": "Scenario provenance only",
                "verdict": "Use the CVE set to define plausible entry scenarios; do not treat the catalog share as an attack probability or patch efficacy.",
            },
        ]
    )


def analyze_observed_data(repo_root: str | Path) -> dict[str, Path]:
    """Run the deterministic observed-data analysis and write CSV products."""
    root = Path(repo_root)
    raw = root / "data" / "observed" / "raw"
    processed = root / "data" / "observed" / "processed"
    processed.mkdir(parents=True, exist_ok=True)

    threat = load_threat_data(raw / "threat_database.csv")
    threat_metrics, event_breadth = summarize_threat(threat)
    cisa_metrics, ransomware_kev, vendor_summary = summarize_cisa_kev(
        raw / "cisa_known_exploited_vulnerabilities.json"
    )
    bridge = build_observation_bridge(
        threat_metrics,
        cisa_metrics,
        root / "data" / "fine_step_replication" / "processed" / "primary_summary.csv",
        root / "data" / "public_validation" / "processed" / "recovery_horizon_summary.csv",
    )

    outputs = {
        "threat_summary": processed / "threat_empirical_summary.csv",
        "event_breadth": processed / "threat_event_breadth.csv",
        "cisa_summary": processed / "cisa_kev_summary.csv",
        "ransomware_kev": processed / "cisa_ransomware_kev.csv",
        "vendor_summary": processed / "cisa_ransomware_kev_vendor_summary.csv",
        "bridge": processed / "observed_simulation_bridge.csv",
    }
    threat_metrics.to_csv(outputs["threat_summary"], index=False)
    event_breadth.to_csv(outputs["event_breadth"], index=False, date_format="%Y-%m-%d")
    cisa_metrics.to_csv(outputs["cisa_summary"], index=False)
    ransomware_kev.to_csv(outputs["ransomware_kev"], index=False)
    vendor_summary.to_csv(outputs["vendor_summary"], index=False)
    bridge.to_csv(outputs["bridge"], index=False)
    return outputs
