"""One-at-a-time (OAT) sensitivity analysis over key model parameters.

Reviewer feedback asked us to *show* sensitivity analyses over plausible
parameter ranges and to identify which strategies remain Pareto-efficient
across assumptions — not merely to describe them as future work. This
module does exactly that, on the primary scenario (intermediate-capacity
regional hospital), for the 14 named defense portfolios.

For each of the model's key dynamics parameters — transition probability,
defense effects, recovery timing, and outcome definitions — we hold every
other parameter at its documented default (docs/assumptions.md) and move
that one parameter to the low and high ends of a plausible range. For each
setting we re-evaluate all 14 portfolios and record, per portfolio, mean
weighted service-hours lost, catastrophic probability, cost, and whether
the portfolio sits on the cost-vs-loss Pareto frontier. We then report:

  * how much the full-defense reduction and the single-control ranking
    move across settings (ranking robustness), and
  * for each portfolio, the share of settings in which it stays
    Pareto-efficient (Pareto robustness across assumptions).

This is a local (OAT) analysis; global variance-based methods
(Sobol / Latin-hypercube) remain future work, as noted in the manuscript.
"""

from __future__ import annotations

import copy
from pathlib import Path

import numpy as np
import pandas as pd

from .config import Config, load_defense_costs
from .defenses import get_portfolio, portfolio_cost
from .experiments import run_specs
from .models import TrialSpec
from .statistics import wilson_ci
from .utilities import ensure_dirs, resolve_path, setup_logging, write_csv

SENS_ID_OFFSET = 20_000_000
DISRUPTION = "weighted_service_hours_lost"
BASELINE = "baseline_flat"
FULL = "full_defense"
SINGLE_CONTROLS = ["basic_segmentation", "least_privilege", "patch_90",
                   "isolated_backups", "identity_controls"]

#: Scenario the sensitivity analysis is run on (the manuscript's primary one).
SENS_FACILITY = "regional_hospital"
SENS_PROFILE = "intermediate_capacity"
SENS_TRIALS_PER_PORTFOLIO = 50   # 10 per entry point x 5 entry points

#: OAT grid. Each entry: (id, human label, setter-path, low, high, default,
#: what-kind). Ranges are plausible bands around the documented defaults
#: (docs/assumptions.md); see the manuscript's calibration subsection.
PARAM_GRID = [
    ("base_spread_rate", "Base spread rate (transition prob.)",
     ("simulation", "base_spread_rate"), 0.25, 0.45, 0.35, "transition"),
    ("patch_effectiveness", "Patch effectiveness (defense effect)",
     ("simulation", "patch_effectiveness"), 0.70, 0.95, 0.85, "defense"),
    ("least_privilege_modifier", "Least-privilege traversal modifier",
     ("network", "segmentation_modifiers", "least_privilege"),
     0.15, 0.35, 0.25, "defense"),
    ("identity_breach_multiplier", "Identity-breach spread multiplier",
     ("simulation", "identity_breach_multiplier"), 1.25, 2.0, 1.5, "transition"),
    ("false_positive_rate", "False-positive isolation rate",
     ("simulation", "false_positive_rate"), 0.0, 0.005, 0.002, "defense"),
    ("restore_duration", "Restore duration per node (recovery time)",
     ("simulation", "restore_duration"), 1, 4, 2, "recovery"),
    ("restore_rate_fraction", "Restore throughput (recovery speed)",
     ("simulation", "restore_rate_fraction"), 0.01, 0.04, 0.02, "recovery"),
    ("service_functional_fraction", "Service-up node threshold",
     ("simulation", "service_functional_fraction"), 0.5, 0.7, 0.6, "outcome"),
    ("catastrophic_service_steps", "Catastrophic-outage threshold (steps)",
     ("simulation", "catastrophic_service_steps"), 6, 12, 8, "outcome"),
]


def _set_param(cfg: Config, path: tuple, value) -> None:
    """Set a (possibly nested-dict) config field in place."""
    section = getattr(cfg, path[0])
    if len(path) == 2:
        setattr(section, path[1], value)
    elif len(path) == 3:                       # e.g. a dict entry
        getattr(section, path[1])[path[2]] = value
    else:
        raise ValueError(f"unsupported param path {path}")


def _evaluate(cfg: Config, costs: dict, tid_start: int) -> tuple[pd.DataFrame, int]:
    """Evaluate the 14 named portfolios on the primary scenario for one config."""
    portfolios = cfg.experiment.portfolios
    entries = cfg.experiment.entry_points
    per_entry = max(1, SENS_TRIALS_PER_PORTFOLIO // len(entries))
    specs, tid = [], tid_start
    for name in portfolios:
        get_portfolio(name)  # fail fast
        for entry in entries:
            for _ in range(per_entry):
                specs.append(TrialSpec(
                    trial_id=tid, experiment="sensitivity",
                    facility=SENS_FACILITY, profile=SENS_PROFILE,
                    portfolio=name, entry_point=entry, master_seed=cfg.seed))
                tid += 1
    raw = run_specs(cfg, specs, desc="sensitivity")
    prof = cfg.profiles[SENS_PROFILE]
    rows = []
    for name, grp in raw.groupby("portfolio"):
        hours = grp[DISRUPTION].to_numpy()
        n = len(grp)
        cat = int(grp["catastrophic"].sum())
        rows.append({
            "portfolio": name,
            "cost": portfolio_cost(get_portfolio(name), prof, costs),
            "n": n,
            "mean_hours_lost": float(hours.mean()),
            "median_hours_lost": float(np.median(hours)),
            "catastrophic_prob": cat / n,
            "catastrophic_ci_hi": wilson_ci(cat, n)[1],
        })
    return pd.DataFrame(rows), tid


def _pareto_names(df: pd.DataFrame) -> set:
    """Names on the cost-vs-mean-hours Pareto frontier (lower cost & loss)."""
    sub = df.sort_values(["cost", "mean_hours_lost"])
    best, front = np.inf, set()
    for _, r in sub.iterrows():
        if r["mean_hours_lost"] < best - 1e-9:
            best = r["mean_hours_lost"]
            front.add(r["portfolio"])
    return front


def run_sensitivity(cfg: Config,
                    defense_costs_path: str | Path | None = None
                    ) -> dict[str, Path]:
    """Run the OAT sensitivity sweep and write per-run, summary, and
    Pareto-robustness tables."""
    log = setup_logging(resolve_path(cfg.output.logs_dir), "grrc.sensitivity")
    proc = resolve_path(cfg.output.processed_dir)
    ensure_dirs(proc)
    costs = load_defense_costs(
        defense_costs_path or resolve_path("configs/defense_costs.yaml"))

    settings = [("baseline", "All parameters at documented defaults",
                 None, None, "-")]
    for pid, label, path, lo, hi, dflt, kind in PARAM_GRID:
        settings.append((f"{pid}_low", f"{label} = {lo}", path, lo, kind))
        settings.append((f"{pid}_high", f"{label} = {hi}", path, hi, kind))

    log.info("sensitivity: %d settings x %d portfolios on %s/%s (%d trials each)",
             len(settings), len(cfg.experiment.portfolios),
             SENS_FACILITY, SENS_PROFILE, SENS_TRIALS_PER_PORTFOLIO)

    per_run, summ, tid = [], [], SENS_ID_OFFSET
    frontier_hits = {n: 0 for n in cfg.experiment.portfolios}
    for setting_id, desc, path, value, kind in settings:
        cfg2 = copy.deepcopy(cfg)
        if path is not None:
            _set_param(cfg2, path, value)
        df, tid = _evaluate(cfg2, costs, tid)
        front = _pareto_names(df)
        base = df[df.portfolio == BASELINE].iloc[0]
        full = df[df.portfolio == FULL].iloc[0]
        red = (1 - full.mean_hours_lost / base.mean_hours_lost
               if base.mean_hours_lost > 0 else np.nan)
        singles = df[df.portfolio.isin(SINGLE_CONTROLS)].copy()
        singles["reduction"] = 1 - singles.mean_hours_lost / base.mean_hours_lost
        top_single = singles.sort_values("reduction", ascending=False).iloc[0]
        for n in front:
            frontier_hits[n] = frontier_hits.get(n, 0) + 1
        for _, r in df.iterrows():
            per_run.append({"setting": setting_id, "description": desc,
                            "param_kind": kind, **r.to_dict(),
                            "on_pareto_frontier": int(r.portfolio in front)})
        summ.append({
            "setting": setting_id, "description": desc, "param_kind": kind,
            "baseline_mean_hours": float(base.mean_hours_lost),
            "full_defense_mean_hours": float(full.mean_hours_lost),
            "full_defense_reduction": float(red),
            "baseline_catastrophic_prob": float(base.catastrophic_prob),
            "full_defense_catastrophic_prob": float(full.catastrophic_prob),
            "top_single_control": top_single.portfolio,
            "top_single_reduction": float(top_single.reduction),
            "n_pareto_portfolios": len(front),
        })
        log.info("  [%s] full-defense reduction %.1f%%, top single=%s",
                 setting_id, 100 * red, top_single.portfolio)

    per_run_df = pd.DataFrame(per_run)
    summ_df = pd.DataFrame(summ)
    n_set = len(settings)
    robust = pd.DataFrame([
        {"portfolio": n,
         "settings_on_frontier": frontier_hits.get(n, 0),
         "n_settings": n_set,
         "pareto_robustness": frontier_hits.get(n, 0) / n_set}
        for n in cfg.experiment.portfolios
    ]).sort_values("pareto_robustness", ascending=False)

    out = {}
    out["runs"] = proc / f"{cfg.mode}_sensitivity_runs.csv"
    write_csv(per_run_df, out["runs"])
    out["summary"] = proc / f"{cfg.mode}_sensitivity_summary.csv"
    write_csv(summ_df, out["summary"])
    out["pareto_robustness"] = proc / f"{cfg.mode}_sensitivity_pareto.csv"
    write_csv(robust, out["pareto_robustness"])

    log.info("sensitivity complete: reduction range %.1f%%-%.1f%%, "
             "least-privilege top single in %d/%d settings",
             100 * summ_df.full_defense_reduction.min(),
             100 * summ_df.full_defense_reduction.max(),
             int((summ_df.top_single_control == "least_privilege").sum()),
             n_set)
    return out
