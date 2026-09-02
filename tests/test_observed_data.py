"""Checks for the public observed-data layer."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from grrc.observed_data import (
    build_observation_bridge,
    load_threat_data,
    summarize_cisa_kev,
    summarize_threat,
)


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "observed" / "raw"


def _metric(frame: pd.DataFrame, name: str):
    values = frame.loc[frame["metric"].eq(name), "value"]
    assert len(values) == 1
    return values.iloc[0]


def test_threat_snapshot_and_deduplication_are_stable():
    frame = load_threat_data(RAW / "threat_database.csv")
    metrics, events = summarize_threat(frame)
    assert len(frame) == 1999
    assert int(_metric(metrics, "attacked_hospital_event_records")) > 0
    assert int(_metric(metrics, "unique_attack_events")) == len(events)
    assert events["attacked_hospitals"].min() >= 1
    assert 0 <= float(_metric(metrics, "multi_hospital_event_fraction")) <= 1


def test_cisa_snapshot_count_and_ransomware_subset_agree():
    metrics, ransomware, vendors = summarize_cisa_kev(
        RAW / "cisa_known_exploited_vulnerabilities.json"
    )
    assert int(float(_metric(metrics, "catalog_vulnerability_count"))) == 1687
    assert int(float(_metric(metrics, "known_ransomware_use_count"))) == len(ransomware)
    assert ransomware["cve_id"].is_unique
    assert ransomware["remediation_window_days"].min() >= 0
    assert vendors["ransomware_linked_cves"].sum() == len(ransomware)


def test_bridge_labels_noncommensurate_endpoints():
    threat_metrics, _ = summarize_threat(
        load_threat_data(RAW / "threat_database.csv")
    )
    cisa_metrics, _, _ = summarize_cisa_kev(
        RAW / "cisa_known_exploited_vulnerabilities.json"
    )
    bridge = build_observation_bridge(
        threat_metrics,
        cisa_metrics,
        ROOT / "data" / "fine_step_replication" / "processed" / "primary_summary.csv",
        ROOT / "data" / "public_validation" / "processed" / "recovery_horizon_summary.csv",
    )
    assert len(bridge) == 5
    assert bridge["verdict"].str.contains("Do not calibrate|Fail|cannot|Use").all()
    assert bridge.loc[
        bridge["observed_endpoint"].eq("Multi-hospital attack breadth"),
        "verdict",
    ].iloc[0].startswith("Fail")
