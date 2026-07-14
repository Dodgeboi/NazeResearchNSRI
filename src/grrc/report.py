"""Populate report templates with ACTUAL generated results.

Research-integrity mechanism: report/templates/*.tpl.md contain
``{{TOKEN}}`` placeholders. This module computes every token value
directly from the processed CSV outputs and rewrites the reports. If a
value cannot be computed from real outputs, the token is left visible in
the document (and a warning is printed) — numbers are never invented.

Run via:  python -m grrc.cli report --config configs/standard.yaml
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from .config import Config
from .plotting import PORTFOLIO_LABELS, PROFILE_LABELS
from .utilities import REPO_ROOT, resolve_path, setup_logging

SINGLE_CONTROL_PORTFOLIOS = [
    "basic_segmentation", "least_privilege", "patch_90", "fast_detection",
    "isolated_backups", "identity_controls",
]

PROFILE_KEYS = {"resource_constrained": "RC", "intermediate_capacity": "IC",
                "high_capacity": "HC"}


def _fmt_pct(x: float) -> str:
    return f"{100 * x:.1f}%"


def _fmt_hours(x: float) -> str:
    return f"{x:.1f}"


def _fmt_p(p: float) -> str:
    return "p < 0.001" if p < 0.001 else f"p = {p:.3f}"


def compute_tokens(cfg: Config) -> dict[str, str]:
    """Derive every report token from generated outputs (never invented)."""
    mode = cfg.mode
    raw_dir = resolve_path(cfg.output.raw_dir)
    proc_dir = resolve_path(cfg.output.processed_dir)
    tokens: dict[str, str] = {
        "MODE": mode,
        "MASTER_SEED": str(cfg.seed),
        "DATE": date.today().isoformat(),
        "N_PER_CELL": str(cfg.experiment.trials_per_cell),
        "HORIZON_HOURS": f"{cfg.simulation.max_steps * cfg.simulation.step_minutes / 60:.0f}",
        "CATASTROPHIC_STEPS": str(cfg.simulation.catastrophic_service_steps),
        "CATASTROPHIC_HOURS": f"{cfg.simulation.catastrophic_service_steps * cfg.simulation.step_minutes / 60:.0f}",
    }

    main = pd.read_csv(raw_dir / f"{mode}_main_results.csv")
    tokens["N_MAIN"] = f"{len(main):,}"
    sweep_path = raw_dir / f"{mode}_sweep_results.csv"
    n_sweep = len(pd.read_csv(sweep_path)) if sweep_path.exists() else 0
    tokens["N_SWEEP"] = f"{n_sweep:,}"
    opt_path = raw_dir / f"{mode}_optimization_results.csv"
    n_opt = len(pd.read_csv(opt_path)) if opt_path.exists() else 0
    tokens["N_OPT"] = f"{n_opt:,}"
    bak_path = raw_dir / f"{mode}_backup_results.csv"
    n_bak = len(pd.read_csv(bak_path)) if bak_path.exists() else 0
    tokens["N_BACKUP"] = f"{n_bak:,}"
    tokens["N_TOTAL"] = f"{len(main) + n_sweep + n_opt + n_bak:,}"

    comp = pd.read_csv(proc_dir / f"{mode}_baseline_comparisons.csv")
    reg = comp[comp["facility"] == "regional_hospital"]
    for prof, key in PROFILE_KEYS.items():
        sub = reg[(reg["profile"] == prof)
                  & (reg["portfolio"] == "full_defense")]
        if sub.empty:
            continue
        r = sub.iloc[0]
        tokens[f"BASELINE_HOURS_{key}"] = _fmt_hours(
            r["baseline_mean_hours_lost"])
        tokens[f"FULL_HOURS_{key}"] = _fmt_hours(r["mean_hours_lost"])
        tokens[f"REL_RED_FULL_{key}"] = _fmt_pct(
            r["relative_reduction_hours"])
        tokens[f"CAT_BASE_{key}"] = _fmt_pct(r["baseline_catastrophic_prob"])
        tokens[f"CAT_FULL_{key}"] = _fmt_pct(r["catastrophic_prob"])
        tokens[f"FULL_MW_P_{key}"] = _fmt_p(r["mannwhitney_p_holm"])
        tokens[f"FULL_DELTA_{key}"] = f"{r['cliffs_delta_vs_baseline']:.2f}"

    singles = reg[reg["portfolio"].isin(SINGLE_CONTROL_PORTFOLIOS)]
    if not singles.empty:
        pooled = (singles.groupby("portfolio")["relative_reduction_hours"]
                  .mean().sort_values(ascending=False))
        tokens["BEST_SINGLE_NAME"] = PORTFOLIO_LABELS.get(
            pooled.index[0], pooled.index[0])
        tokens["BEST_SINGLE_RED"] = _fmt_pct(pooled.iloc[0])
        tokens["SECOND_SINGLE_NAME"] = PORTFOLIO_LABELS.get(
            pooled.index[1], pooled.index[1])
        tokens["SECOND_SINGLE_RED"] = _fmt_pct(pooled.iloc[1])
        lines = ["| Single defense | Mean reduction in weighted "
                 "service-hours lost vs. flat baseline |", "|---|---|"]
        for name, val in pooled.items():
            lines.append(f"| {PORTFOLIO_LABELS.get(name, name)} | "
                         f"{_fmt_pct(val)} |")
        tokens["TABLE_SINGLE_DEFENSES"] = "\n".join(lines)

    sweep_sum_path = proc_dir / f"{mode}_sweep_summary.csv"
    if sweep_sum_path.exists():
        sw = pd.read_csv(sweep_sum_path)
        worst = sw.sort_values("catastrophic_prob").iloc[-1]
        best = sw.sort_values("catastrophic_prob").iloc[0]
        tokens["SWEEP_WORST_CAT"] = _fmt_pct(worst["catastrophic_prob"])
        tokens["SWEEP_WORST_CELL"] = (
            f"{worst['patch_coverage']:.0%} patch / "
            f"{int(worst['detection_delay'])}-step delay")
        tokens["SWEEP_BEST_CAT"] = _fmt_pct(best["catastrophic_prob"])
        tokens["SWEEP_BEST_CELL"] = (
            f"{best['patch_coverage']:.0%} patch / "
            f"{int(best['detection_delay'])}-step delay")

    backup_path = raw_dir / f"{mode}_backup_results.csv"
    if backup_path.exists():
        backup = pd.read_csv(backup_path)
        for strat, key in (("connected", "PBAK_CONNECTED"),
                           ("periodic", "PBAK_PERIODIC"),
                           ("isolated", "PBAK_ISOLATED")):
            sub = backup[backup["backup_strategy"] == strat]
            if len(sub):
                tokens[key] = _fmt_pct(sub["backup_compromised"].mean())

    best_path = proc_dir / f"{mode}_best_portfolios.csv"
    if best_path.exists():
        best = pd.read_csv(best_path)
        pick = best[(best["criterion"] == "min_expected_disruption")
                    & (best["cost_scale"] == 1.0)]
        lines = ["| Profile | Budget | Best portfolio (min expected "
                 "disruption) | Mean hours lost | P(catastrophic) |",
                 "|---|---|---|---|---|"]
        for _, r in pick.sort_values(["profile", "budget"]).iterrows():
            lines.append(
                f"| {PROFILE_LABELS.get(r['profile'], r['profile'])} | "
                f"{int(r['budget'])} | {r['description']} | "
                f"{_fmt_hours(r['mean_hours_lost'])} | "
                f"{_fmt_pct(r['catastrophic_prob'])} |")
        tokens["TABLE_BEST_BUDGET"] = "\n".join(lines)

    stab_path = proc_dir / f"{mode}_cost_sensitivity.csv"
    if stab_path.exists():
        stab = pd.read_csv(stab_path)
        control_labels = {
            "has_basic_segmentation": "Basic segmentation",
            "has_least_privilege": "Least-privilege segmentation",
            "has_patch_upgrade": "Patch upgrade (any level)",
            "has_detection_improvement": "Detection improvement",
            "has_rapid_isolation": "Rapid isolation",
            "has_protected_backups": "Protected backups",
            "has_identity_controls": "Identity controls",
        }
        lines = ["| Control | " + " | ".join(
            PROFILE_LABELS.get(p, p) for p in stab["profile"]) + " |",
            "|---|" + "---|" * len(stab)]
        for col, label in control_labels.items():
            vals = " | ".join(_fmt_pct(v) for v in stab[col])
            lines.append(f"| {label} | {vals} |")
        tokens["STABILITY_TABLE"] = "\n".join(lines)
        pooled = stab[list(control_labels)].mean()
        top = pooled.sort_values(ascending=False)
        tokens["MOST_STABLE_CONTROL"] = control_labels[top.index[0]]
        tokens["MOST_STABLE_FREQ"] = _fmt_pct(top.iloc[0])

    minb_path = proc_dir / f"{mode}_minimum_budget.csv"
    if minb_path.exists():
        minb = pd.read_csv(minb_path)
        lines = [f"| Profile | Minimum budget for P(catastrophic) <= "
                 f"{cfg.optimization.catastrophic_target:.0%} |", "|---|---|"]
        for _, r in minb.iterrows():
            val = ("not reachable in tested space"
                   if not r["reachable"] else f"{int(r['min_budget'])} points")
            lines.append(
                f"| {PROFILE_LABELS.get(r['profile'], r['profile'])} | "
                f"{val} |")
        tokens["TABLE_MIN_BUDGET"] = "\n".join(lines)

    return tokens


TOKEN_RE = re.compile(r"\{\{([A-Z0-9_]+)\}\}")


def render_template(template: Path, out: Path,
                    tokens: dict[str, str]) -> list[str]:
    """Fill one template; return the list of unresolved token names."""
    text = template.read_text()
    missing: list[str] = []

    def sub(match: re.Match) -> str:
        key = match.group(1)
        if key in tokens:
            return tokens[key]
        missing.append(key)
        return match.group(0)  # leave visible; never invent

    out.write_text(TOKEN_RE.sub(sub, text))
    return missing


def populate_reports(cfg: Config) -> dict[str, list[str]]:
    """Render every report template; returns unresolved tokens per file."""
    log = setup_logging(resolve_path(cfg.output.logs_dir), "grrc.report")
    tokens = compute_tokens(cfg)
    tpl_dir = REPO_ROOT / "report" / "templates"
    unresolved: dict[str, list[str]] = {}
    for tpl in sorted(tpl_dir.glob("*.tpl.md")):
        out = REPO_ROOT / "report" / tpl.name.replace(".tpl.md", ".md")
        missing = render_template(tpl, out, tokens)
        unresolved[out.name] = missing
        if missing:
            log.warning("%s: %d unresolved tokens: %s — these remain "
                        "visible placeholders (values are never invented)",
                        out.name, len(missing), sorted(set(missing)))
        else:
            log.info("rendered %s (all tokens resolved)", out.name)
    return unresolved
