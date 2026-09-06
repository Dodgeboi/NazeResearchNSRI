#!/usr/bin/env python3
"""Reproduce the recorded external construct-coverage audit."""
import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd

from grrc.provenance import build_manifest, git_state, write_manifest
from grrc.utilities import write_csv

ROOT = Path(__file__).resolve().parents[1]
MAPPING = {
    "Health Records": ("EHR", "represented digital service"),
    "Laboratory Systems": ("laboratory", "represented digital service"),
    "ePrescribing": ("pharmacy", "represented digital service"),
    "Imaging": ("imaging", "represented digital service"),
    "Booking Systems": ("scheduling", "represented digital service"),
    **{k: ("none", "absent explicit service") for k in [
        "Admin and Billing", "Communications", "Hospital Infrastructure",
        "Operating Rooms", "Telemetry"]},
    "All": ("unspecified", "unspecified"),
}
TIMES = ["First Hour", "First Day", "First Week", "Week 2", "First Month"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-dirty", action="store_true")
    args = parser.parse_args()
    state = git_state()
    if (not state.get("available") or state["dirty"]) and not args.allow_dirty:
        raise SystemExit("Commit code, design and source data before aggregation.")
    base = ROOT/"data/cipher"
    rawpath = base/"raw/cipher-v1.0.1.csv"
    sourcepath = base/"raw/source_manifest.json"
    source = json.loads(sourcepath.read_text(encoding="utf-8"))
    if hashlib.sha256(rawpath.read_bytes()).hexdigest() != source["csv_sha256"]:
        raise AssertionError("raw CIPHER bytes changed")
    frame = pd.read_csv(rawpath)
    original = frame.copy()
    for col in frame.select_dtypes(include=["str", "object"]).columns:
        frame[col] = frame[col].str.strip()
    frame["source"] = frame["Reference Link"].str.rstrip("/")
    typos = int(frame["Time Point"].eq("Firsy Day").sum())
    frame["Time Point"] = frame["Time Point"].replace({"Firsy Day": "First Day"})
    if set(frame["Technical Domain"].dropna()) - MAPPING.keys():
        raise AssertionError("unmapped technical domain")
    if set(frame["Time Point"].dropna()) - set(TIMES):
        raise AssertionError("unmapped time label")
    frame["model_construct"] = frame["Technical Domain"].map(lambda d: MAPPING[d][0])
    frame["coverage"] = frame["Technical Domain"].map(lambda d: MAPPING[d][1])
    frame["beyond_horizon_annotation"] = frame["Time Point"].isin(["Week 2", "First Month"])
    frame["absent_service"] = frame.coverage.eq("absent explicit service")
    out = base/"processed"; out.mkdir(exist_ok=True)
    outputs = []
    def save(name, data):
        path = out/(name+".csv")
        write_csv(pd.DataFrame(data), path); outputs.append(path)
    rows, influence = [], []
    for subset, data in [("all_records", frame),
        ("exact_rows_deduplicated", frame.loc[~original.duplicated()])]:
        for category in ["Technical Domain", "coverage", "Time Point"]:
            for label, group in data.groupby(category, dropna=False):
                rows.append(dict(subset=subset, category=category, label=label,
                    records=len(group), reference_links=group.source.nunique(),
                    record_share=len(group)/len(data)))
        for link in data.source.dropna().unique():
            retained = data[data.source != link]
            influence.append(dict(subset=subset, removed_reference=link,
                remaining_records=len(retained),
                absent_service_share=float(retained.absent_service.mean()),
                beyond_horizon_share=float(retained.beyond_horizon_annotation.mean())))
    save("category_counts", rows)
    save("leave_one_reference_out", influence)
    save("domain_mapping", [dict(domain=k, model_construct=v[0], coverage=v[1])
                            for k, v in MAPPING.items()])
    source_rows = frame.groupby("source", dropna=False).agg(
        records=("source", "size"), absent_service_records=("absent_service", "sum"),
        beyond_horizon_records=("beyond_horizon_annotation", "sum")).reset_index()
    save("reference_counts", source_rows)
    save("missingness", [dict(column=c, missing=int(original[c].isna().sum()))
                         for c in original.columns])
    summary = dict(records=len(frame), exact_duplicate_rows=int(original.duplicated().sum()),
        reference_links=int(frame.source.nunique()), typo_labels_corrected=typos,
        absent_service_records=int(frame.absent_service.sum()),
        absent_service_share=float(frame.absent_service.mean()),
        beyond_horizon_records=int(frame.beyond_horizon_annotation.sum()),
        beyond_horizon_share=float(frame.beyond_horizon_annotation.mean()))
    inf = pd.DataFrame(influence).query("subset == 'all_records'")
    for c in ["absent_service_share", "beyond_horizon_share"]:
        summary[c+"_leave_one_reference_min"] = float(inf[c].min())
        summary[c+"_leave_one_reference_max"] = float(inf[c].max())
    save("coverage_summary", [summary])
    inputs = [Path(__file__), ROOT/"study/CIPHER_COVERAGE_PLAN.md",
        ROOT/"src/grrc/provenance.py", ROOT/"src/grrc/utilities.py",
        *sorted((base/"raw").glob("*"))]
    write_manifest(build_manifest(run_id="cipher-coverage", stage="analysis",
        description="External dataset construct coverage; coded records are not independent incidents.",
        inputs=inputs, outputs=outputs, source_state=state, parameters=dict(
            release="v1.0.1", doi=source["doi"], mapping=MAPPING, time_labels=TIMES,
            inference="descriptive only; no clinical outcome, incidence, duration or control-effect estimate")),
        out/"coverage_manifest.json")
    print(json.dumps(summary, indent=2))
    print(pd.DataFrame(rows).query("subset == 'all_records'").to_string(index=False))


if __name__ == "__main__":
    main()
