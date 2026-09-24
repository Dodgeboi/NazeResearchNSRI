"""Analyse the exploratory islanding experiment.

Reads data/islanding/raw/islanding_experiment.csv.gz and writes paired
contrasts, a threshold test of the island-count rule, and an entry-point
breakdown to data/islanding/processed/, then renders data/islanding/RESULTS.md
from those tables so that no number in the prose is typed by hand.

Every contrast is a within-scenario difference: each condition replays the
same scenario bank, so a scenario's difference isolates the condition. The
bootstrap resamples scenarios with replacement inside each (profile, entry
point) cell, preserving the balanced design. Intervals are percentile
intervals from a fixed seed. They are descriptive: this run is exploratory,
there are many contrasts, and none was prespecified.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "islanding" / "raw" / "islanding_experiment.csv.gz"
PROC = ROOT / "data" / "islanding" / "processed"
RESULTS = ROOT / "data" / "islanding" / "RESULTS.md"
DRAWS = 2000
SEED = 20260922

HOURS = "weighted_service_hours_lost"
#: Primary sustained-outage endpoint in configs/multiobjective_portfolio.yaml
#: (all four clinical services), and the most sensitive rung (any one).
OUTAGE_K4 = "sustained_clinical_outage_k4"
OUTAGE_K1 = "sustained_clinical_outage_k1"
SPREAD = "ever_compromised_fraction"
METRICS = (HOURS, OUTAGE_K4, OUTAGE_K1, SPREAD)

#: (label, reference, treatment, question)
CONTRASTS = [
    ("method", "none", "dcci3",
     "Does dependency-closed islanding reduce harm at all?"),
    ("prior_art", "none", "zone",
     "How much does detection-triggered segmentation (prior art) help?"),
    ("method_vs_prior_art", "zone", "dcci3",
     "Does the method beat the closest prior art?"),
    ("micro_lockdown", "none", "micro",
     "How much does the strongest segmentation lockdown help?"),
    ("method_vs_micro", "micro", "dcci3",
     "Does the method beat the strongest segmentation comparator?"),
    ("islanding_on_top_of_micro", "micro", "dcci3_micro",
     "Does islanding add anything on top of that lockdown?"),
    ("micro_inside_islands", "dcci3", "dcci3_micro",
     "Does the lockdown add anything inside islands?"),
    ("disconnection_alone", "none", "crude3",
     "Is severing without replicas protective?"),
    ("dependency_closure", "crude3", "dcci3",
     "What does dependency closure add to the same cuts?"),
    ("two_islands", "none", "dcci2", "Two islands at theta = 0.60."),
    ("four_islands", "none", "dcci4", "Four islands at theta = 0.60."),
    ("three_vs_two", "dcci2", "dcci3", "Third island at theta = 0.60."),
    ("four_vs_three", "dcci3", "dcci4", "Fourth island at theta = 0.60."),
    ("without_local_restore", "none", "dcci3_nolocal",
     "The method with no restoration inside contained islands."),
    ("local_restore_share", "dcci3_nolocal", "dcci3",
     "What local restoration adds (the part that runs through S1)."),
    ("method_s1_off", "none_ungated", "dcci3_ungated",
     "The method with restoration not gated on containment."),
    ("method_vs_prior_art_s1_off", "zone_ungated", "dcci3_ungated",
     "Method vs prior art with S1 off."),
    ("two_islands_theta45", "none_theta45", "dcci2_theta45",
     "Two islands at theta = 0.45."),
    ("three_islands_theta45", "none_theta45", "dcci3_theta45",
     "Three islands at theta = 0.45."),
]


def _paired(raw: pd.DataFrame, ref: str, trt: str) -> pd.DataFrame:
    keys = ["scenario_id", "profile", "entry_point"]
    a = raw[raw.condition == ref].set_index(keys)[list(METRICS)]
    b = raw[raw.condition == trt].set_index(keys)[list(METRICS)]
    if len(a) != len(b):
        raise ValueError(f"{trt} and {ref} have different scenario counts")
    b = b.reindex(a.index)
    if b.isna().any().any():
        raise ValueError(f"{trt} is not paired with {ref}")
    diff = (b - a).reset_index()
    for m in METRICS:
        diff[f"ref_{m}"] = a[m].to_numpy()
        diff[f"trt_{m}"] = b[m].to_numpy()
    return diff


def _resample_index(frame: pd.DataFrame, rng) -> np.ndarray:
    """(DRAWS, n) row positions, resampled within (profile, entry) cells.

    Built once per subset and shared by every metric, so all metrics in a
    row of the output come from the same bootstrap resamples.
    """
    frame = frame.reset_index(drop=True)
    cells = [np.asarray(v) for v in
             frame.groupby(["profile", "entry_point"]).indices.values()]
    return np.concatenate(
        [c[rng.integers(0, c.size, size=(DRAWS, c.size))] for c in cells],
        axis=1)


def _interval(values: np.ndarray) -> tuple[float, float]:
    return (float(np.nanpercentile(values, 2.5)),
            float(np.nanpercentile(values, 97.5)))


def contrast_table(raw: pd.DataFrame) -> pd.DataFrame:
    rng = np.random.default_rng(SEED)
    rows = []
    for label, ref, trt, question in CONTRASTS:
        diff = _paired(raw, ref, trt).reset_index(drop=True)
        for profile in ["pooled", *sorted(diff.profile.unique())]:
            sub = (diff if profile == "pooled"
                   else diff[diff.profile == profile]).reset_index(drop=True)
            row = {"contrast": label, "reference": ref, "treatment": trt,
                   "profile": profile, "n_scenarios": len(sub),
                   "question": question}
            idx = _resample_index(sub, rng)
            for m in METRICS:
                lo, hi = _interval(sub[m].to_numpy()[idx].mean(axis=1))
                row.update({f"ref_mean_{m}": sub[f"ref_{m}"].mean(),
                            f"trt_mean_{m}": sub[f"trt_{m}"].mean(),
                            f"diff_{m}": sub[m].mean(),
                            f"diff_{m}_lo": lo, f"diff_{m}_hi": hi})
            row["share_worse"] = float((sub[HOURS] > 1e-9).mean())
            row["share_better"] = float((sub[HOURS] < -1e-9).mean())
            rows.append(row)
    return pd.DataFrame(rows)


def island_count_rule(raw: pd.DataFrame) -> pd.DataFrame:
    """Share of the three-island benefit that two islands recover, by theta.

    The edge cut made by two islands is the same at both thresholds, so a
    difference in this share between thresholds is attributable to the
    capacity rule, not to weaker containment.
    """
    rng = np.random.default_rng(SEED + 1)
    arms = {0.60: ("none", "dcci2", "dcci3"),
            0.45: ("none_theta45", "dcci2_theta45", "dcci3_theta45")}
    rows = []
    for theta, (none_c, two_c, three_c) in arms.items():
        d2 = _paired(raw, none_c, two_c).reset_index(drop=True)
        d3 = _paired(raw, none_c, three_c).reset_index(drop=True)
        for metric in (HOURS, OUTAGE_K1):
            two, three = d2[metric].to_numpy(), d3[metric].to_numpy()
            idx = _resample_index(d2, rng)
            gain2, gain3 = -two[idx].mean(axis=1), -three[idx].mean(axis=1)
            with np.errstate(divide="ignore", invalid="ignore"):
                boot = np.where(gain3 > 0, gain2 / gain3, np.nan)
            lo, hi = _interval(boot)
            point3 = -three.mean()
            rows.append({"theta": theta, "metric": metric,
                         "k_min": 3 if theta == 0.60 else 2,
                         "two_island_gain": -two.mean(),
                         "three_island_gain": point3,
                         "share_recovered": (-two.mean() / point3
                                             if point3 > 0 else np.nan),
                         "share_lo": lo, "share_hi": hi})
    return pd.DataFrame(rows)


def entry_point_table(raw: pd.DataFrame) -> pd.DataFrame:
    rng = np.random.default_rng(SEED + 2)
    rows = []
    for label, ref, trt in [("method", "none", "dcci3"),
                            ("method_vs_prior_art", "zone", "dcci3"),
                            ("method_vs_micro", "micro", "dcci3"),
                            ("islanding_on_top_of_micro", "micro",
                             "dcci3_micro"),
                            ("disconnection_alone", "none", "crude3")]:
        diff = _paired(raw, ref, trt).reset_index(drop=True)
        for entry, sub in diff.groupby("entry_point"):
            sub = sub.reset_index(drop=True)
            idx = _resample_index(sub, rng)
            lo, hi = _interval(sub[HOURS].to_numpy()[idx].mean(axis=1))
            rows.append({"contrast": label, "entry_point": entry,
                         "n_scenarios": len(sub),
                         "ref_mean_hours": sub[f"ref_{HOURS}"].mean(),
                         "diff_hours": sub[HOURS].mean(),
                         "diff_hours_lo": lo, "diff_hours_hi": hi,
                         "share_worse": float((sub[HOURS] > 1e-9).mean())})
    return pd.DataFrame(rows)


def _ci(row, metric, scale=1.0, digits=1, pct=False):
    unit = " pp" if pct else ""
    return (f"{row[f'diff_{metric}'] * scale:+.{digits}f}{unit} "
            f"[{row[f'diff_{metric}_lo'] * scale:+.{digits}f}, "
            f"{row[f'diff_{metric}_hi'] * scale:+.{digits}f}]")


def render(contrasts, rule, entries, manifest) -> str:
    pooled = contrasts[contrasts.profile == "pooled"].set_index("contrast")
    lines = [
        "# Islanding experiment — exploratory results",
        "",
        "> **Exploratory.** No protocol was frozen before this run. There are "
        f"{len(CONTRASTS)} contrasts and none was prespecified, so intervals "
        "are descriptive, not tests. The model has no identified hospital "
        "control effects; these are properties of the simulator under its "
        "declared assumptions. Generated by "
        "`scripts/analyze_islanding_experiment.py` — do not edit by hand.",
        "",
        f"Scenario bank: seed {manifest['master_seed']}, "
        f"{manifest['scenarios_per_cell']} scenarios per (profile, entry "
        f"point) cell, {len(manifest['profiles'])} profiles x "
        f"{len(manifest['entry_points'])} entry points = "
        f"{manifest['scenarios_per_cell'] * len(manifest['profiles']) * len(manifest['entry_points'])} "
        f"paired scenarios per condition, {manifest['rows']} trials. "
        f"Config `{manifest['config']}`.",
        "",
        "Differences are treatment minus reference, paired by scenario, with "
        "95% percentile bootstrap intervals (resampling scenarios within "
        "design cells). Negative is better. *Worse* is the share of scenarios "
        "where the treatment lost more weighted service-hours.",
        "",
        "## Pooled contrasts",
        "",
        "| Contrast | Reference → treatment | Δ weighted service-hours | "
        "Δ sustained outage, all 4 services | Δ sustained outage, any service "
        "| Worse |",
        "|---|---|---|---|---|---|",
    ]
    for label, ref, trt, _ in CONTRASTS:
        r = pooled.loc[label]
        lines.append(
            f"| {label.replace('_', ' ')} | `{ref}` → `{trt}` | "
            f"{_ci(r, HOURS)} | {_ci(r, OUTAGE_K4, 100, 1, True)} | "
            f"{_ci(r, OUTAGE_K1, 100, 1, True)} | {r['share_worse']:.0%} |")

    lines += [
        "",
        "## Island-count rule, with the spread confound removed",
        "",
        "Two islands cut the same edges at both thresholds, so the change in "
        "the share of the three-island benefit that two islands recover is "
        "attributable to the capacity rule k ≥ 1/(1 − θ). The rule predicts "
        "the share is low at θ = 0.60 (k_min = 3) and high at θ = 0.45 "
        "(k_min = 2).",
        "",
        "| θ | k_min | Metric | 2-island gain | 3-island gain | "
        "Share recovered by 2 islands |",
        "|---|---|---|---|---|---|",
    ]
    for _, r in rule.iterrows():
        metric = ("weighted service-hours" if r.metric == HOURS
                  else "P(sustained outage, any service)")
        scale = 1 if r.metric == HOURS else 100
        unit = "" if r.metric == HOURS else " pp"
        lines.append(
            f"| {r.theta:.2f} | {r.k_min} | {metric} | "
            f"{r.two_island_gain * scale:.1f}{unit} | "
            f"{r.three_island_gain * scale:.1f}{unit} | "
            f"{r.share_recovered:.0%} [{r.share_lo:.0%}, {r.share_hi:.0%}] |")

    lines += [
        "",
        "## By entry point (pooled over profiles)",
        "",
        "| Contrast | Entry point | Reference mean hours | Δ hours | Worse |",
        "|---|---|---|---|---|",
    ]
    for _, r in entries.iterrows():
        lines.append(
            f"| {r.contrast.replace('_', ' ')} | {r.entry_point} | "
            f"{r.ref_mean_hours:.1f} | {r.diff_hours:+.1f} "
            f"[{r.diff_hours_lo:+.1f}, {r.diff_hours_hi:+.1f}] | "
            f"{r.share_worse:.0%} |")

    lines += [
        "",
        "## By profile",
        "",
        "| Contrast | Profile | Δ weighted service-hours | "
        "Δ sustained outage, any service | Worse |",
        "|---|---|---|---|---|",
    ]
    for _, r in contrasts[contrasts.profile != "pooled"].iterrows():
        if r.contrast not in ("method", "method_vs_prior_art",
                              "method_vs_micro", "islanding_on_top_of_micro",
                              "disconnection_alone", "dependency_closure"):
            continue
        lines.append(
            f"| {r.contrast.replace('_', ' ')} | {r.profile} | "
            f"{_ci(r, HOURS)} | {_ci(r, OUTAGE_K1, 100, 1, True)} | "
            f"{r['share_worse']:.0%} |")
    return "\n".join(lines) + "\n"


def main() -> None:
    raw = pd.read_csv(RAW, float_precision="round_trip")
    manifest = json.loads((RAW.parent / "manifest.json").read_text("utf-8"))
    PROC.mkdir(parents=True, exist_ok=True)
    contrasts = contrast_table(raw)
    rule = island_count_rule(raw)
    entries = entry_point_table(raw)
    contrasts.to_csv(PROC / "paired_contrasts.csv", index=False)
    rule.to_csv(PROC / "island_count_rule.csv", index=False)
    entries.to_csv(PROC / "entry_point_contrasts.csv", index=False)
    RESULTS.write_text(render(contrasts, rule, entries, manifest),
                       encoding="utf-8")
    print(f"wrote {PROC} and {RESULTS}")


if __name__ == "__main__":
    main()
