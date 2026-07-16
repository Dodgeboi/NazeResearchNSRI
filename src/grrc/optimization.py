"""Budget-constrained defense-portfolio optimization + cost sensitivity.

Approach: the simulator's outcomes do not depend on what a defense
*costs*, only on what it *does*. So each behaviorally-distinct candidate
portfolio is evaluated ONCE per capacity profile with Monte Carlo trials;
budgets and cost-scaling scenarios then just re-filter and re-rank the
same measured performance. This makes the +/-50% cost sensitivity
analysis essentially free.

All costs are normalized model points (configs/defense_costs.yaml),
explicitly NOT dollar estimates.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from .config import Config, load_defense_costs
from .defenses import (DefensePortfolio, effective_settings,
                       enumerate_portfolios, portfolio_cost,
                       describe_portfolio)
from .enums import BackupStrategy, SegmentationLevel
from .experiments import OPT_ID_OFFSET, run_specs
from .models import TrialSpec
from .statistics import bootstrap_ci, wilson_ci
from .utilities import ensure_dirs, resolve_path, setup_logging, write_csv

#: Metric minimized as 'expected service disruption'.
DISRUPTION_METRIC = "weighted_service_hours_lost"


def _resolved_key(eff) -> tuple:
    """Canonical key for a behaviorally-distinct simulator configuration."""
    return (
        eff.segmentation.value,
        round(eff.patch_coverage, 6),
        int(eff.detection_delay),
        round(eff.isolation_success, 6),
        bool(eff.isolate_same_step),
        eff.backup_strategy,
        bool(eff.identity_controls),
    )


def distinct_portfolios_for_profile(
        cfg: Config, profile: str) -> list[DefensePortfolio]:
    """Candidate portfolios that are behaviorally distinct for one profile.

    The enumerated search space contains upgrade combinations that resolve
    to the *same* effective settings once clamped to a profile's baseline
    (e.g. patch+1 and patch+2 both cap at 90% for a high-baseline profile).
    Evaluating such duplicates separately would waste trials and, worse,
    give each a different random network so that noise — not the defense —
    could decide the 'winner'. We therefore keep exactly one representative
    per distinct resolved configuration, per profile.
    """
    prof = cfg.profiles[profile]
    seen: dict[tuple, DefensePortfolio] = {}
    for p in enumerate_portfolios():
        key = _resolved_key(effective_settings(prof, p))
        seen.setdefault(key, p)
    return list(seen.values())


def _portfolio_components(p: DefensePortfolio) -> dict[str, int]:
    """Binary indicators of which controls a portfolio contains."""
    return {
        "has_basic_segmentation":
            int(p.segmentation == SegmentationLevel.BASIC),
        "has_least_privilege":
            int(p.segmentation == SegmentationLevel.LEAST_PRIVILEGE),
        "has_patch_upgrade": int(p.patch_boost_levels > 0),
        "patch_boost_levels": p.patch_boost_levels,
        "has_detection_improvement": int(p.detection_improvement),
        "has_rapid_isolation": int(p.rapid_isolation),
        "has_protected_backups":
            int(p.backup_override == BackupStrategy.ISOLATED),
        "has_identity_controls": int(p.identity_controls),
    }


CONTROL_COLUMNS = [
    "has_basic_segmentation", "has_least_privilege", "has_patch_upgrade",
    "has_detection_improvement", "has_rapid_isolation",
    "has_protected_backups", "has_identity_controls",
]


def evaluate_candidate_portfolios(cfg: Config) -> pd.DataFrame:
    """Monte Carlo evaluation of every *distinct* candidate per profile.

    Duplicate configurations (same resolved settings under a profile) are
    collapsed to one representative before evaluation, so no configuration
    is double-counted or compared against itself on a different network.

    Returns the raw per-trial DataFrame (also exported by ``optimize``).
    """
    opt = cfg.optimization
    entries = cfg.experiment.entry_points
    specs: list[TrialSpec] = []
    portfolios: dict[str, DefensePortfolio] = {}
    tid = OPT_ID_OFFSET
    for profile in opt.profiles:
        for p in distinct_portfolios_for_profile(cfg, profile):
            portfolios.setdefault(p.name, p)
            for k in range(opt.trials_per_portfolio):
                specs.append(TrialSpec(
                    trial_id=tid, experiment="optimization",
                    facility=opt.facility, profile=profile,
                    portfolio=p.name, entry_point=entries[k % len(entries)],
                    master_seed=cfg.seed))
                tid += 1
    return run_specs(cfg, specs, portfolios=portfolios,
                     desc=f"{cfg.mode}:optimize")


def summarize_portfolios(raw: pd.DataFrame, cfg: Config,
                         costs: dict[str, float]) -> pd.DataFrame:
    """Aggregate trials into one row per (profile, portfolio)."""
    portfolios = {p.name: p for p in enumerate_portfolios()}
    rows = []
    for (profile, name), grp in raw.groupby(["profile", "portfolio"]):
        p = portfolios[name]
        hours = grp[DISRUPTION_METRIC].to_numpy()
        lo, hi = bootstrap_ci(hours, seed=cfg.seed)
        n = len(grp)
        cat_events = int(grp["catastrophic"].sum())
        cat_lo, cat_hi = wilson_ci(cat_events, n)
        rows.append({
            "profile": profile,
            "portfolio": name,
            "description": describe_portfolio(p),
            "base_cost": portfolio_cost(p, cfg.profiles[profile], costs),
            "n_trials": n,
            "mean_hours_lost": float(hours.mean()),
            "hours_lost_ci_lo": lo,
            "hours_lost_ci_hi": hi,
            "median_hours_lost": float(np.median(hours)),
            "p90_hours_lost": float(np.percentile(hours, 90)),
            "catastrophic_prob": float(grp["catastrophic"].mean()),
            # Wilson 95% CI: at n=25 the point estimate alone is coarse
            # (4-point granularity) and its upper bound is far higher.
            "catastrophic_prob_ci_lo": cat_lo,
            "catastrophic_prob_ci_hi": cat_hi,
            "mean_pct_compromised": float(grp["pct_compromised"].mean()),
            "backup_compromise_prob":
                float(grp["backup_compromised"].mean()),
            **_portfolio_components(p),
        })
    return pd.DataFrame(rows)


def _zero_cost_baseline(summary: pd.DataFrame, profile: str) -> pd.Series:
    """The measured zero-cost portfolio (flat, no upgrades) for a profile."""
    sub = summary[(summary["profile"] == profile)
                  & (summary["base_cost"] == 0.0)]
    if sub.empty:  # cost scaling never makes a 0-cost portfolio non-zero
        raise RuntimeError(f"no zero-cost baseline found for '{profile}'")
    return sub.iloc[0]


def select_best(summary: pd.DataFrame, profile: str, budget: float,
                scale: float, baseline_hours: float) -> list[dict]:
    """Pick best portfolios under one budget/cost-scale for 4 criteria."""
    sub = summary[summary["profile"] == profile].copy()
    sub["cost"] = sub["base_cost"] * scale
    feasible = sub[sub["cost"] <= budget].copy()
    if feasible.empty:
        return []
    feasible["hours_preserved"] = (baseline_hours
                                   - feasible["mean_hours_lost"])
    with np.errstate(divide="ignore", invalid="ignore"):
        feasible["hours_preserved_per_point"] = np.where(
            feasible["cost"] > 0,
            feasible["hours_preserved"] / feasible["cost"], np.nan)
    span = (feasible["mean_hours_lost"].max()
            - feasible["mean_hours_lost"].min()) or 1.0
    norm_hours = (feasible["mean_hours_lost"]
                  - feasible["mean_hours_lost"].min()) / span
    cspan = (feasible["catastrophic_prob"].max()
             - feasible["catastrophic_prob"].min()) or 1.0
    norm_cat = (feasible["catastrophic_prob"]
                - feasible["catastrophic_prob"].min()) / cspan
    feasible["balanced_score"] = 0.5 * norm_hours + 0.5 * norm_cat

    picks = {
        "min_expected_disruption":
            feasible.sort_values(["mean_hours_lost", "cost"]).iloc[0],
        "min_catastrophic_prob":
            feasible.sort_values(
                ["catastrophic_prob", "mean_hours_lost"]).iloc[0],
        "max_hours_preserved_per_point":
            feasible.sort_values(
                "hours_preserved_per_point", ascending=False).iloc[0]
            if feasible["hours_preserved_per_point"].notna().any()
            else feasible.sort_values("mean_hours_lost").iloc[0],
        "best_balanced":
            feasible.sort_values(["balanced_score", "cost"]).iloc[0],
    }
    def _n_tied(row) -> int:
        """Feasible portfolios whose mean-hours CI overlaps the winner's.

        The selection ranks on point estimates, so a winner with many
        overlapping rivals is not meaningfully 'the best' — it is one of
        several statistically indistinguishable options. Reported so the
        pick is never over-read.
        """
        lo, hi = row["hours_lost_ci_lo"], row["hours_lost_ci_hi"]
        overlap = ((feasible["hours_lost_ci_lo"] <= hi)
                   & (feasible["hours_lost_ci_hi"] >= lo))
        return int(overlap.sum())

    rows = []
    for criterion, row in picks.items():
        rows.append({
            "profile": profile, "budget": budget, "cost_scale": scale,
            "criterion": criterion, "portfolio": row["portfolio"],
            "description": row["description"], "cost": float(row["cost"]),
            "mean_hours_lost": float(row["mean_hours_lost"]),
            "hours_lost_ci_lo": float(row["hours_lost_ci_lo"]),
            "hours_lost_ci_hi": float(row["hours_lost_ci_hi"]),
            "n_tied_within_ci": _n_tied(row),
            "n_feasible_candidates": int(len(feasible)),
            "catastrophic_prob": float(row["catastrophic_prob"]),
            "hours_preserved_per_point":
                float(row["hours_preserved_per_point"])
                if np.isfinite(row["hours_preserved_per_point"]) else np.nan,
            **{c: int(row[c]) for c in CONTROL_COLUMNS},
        })
    return rows


def pareto_frontier(summary: pd.DataFrame, profile: str) -> pd.DataFrame:
    """Non-dominated (cost, mean hours lost) portfolios for one profile.

    The frontier is built on point estimates (the standard definition), so a
    step of any size counts as an improvement and sampling noise alone can
    create a frontier point. Rather than silently hide that, each point
    carries ``improvement_exceeds_noise``: 1 when its mean falls below the
    previous frontier point's 95% bootstrap *lower* bound, i.e. the gain is
    larger than the incumbent's sampling uncertainty. Points flagged 0 are
    within noise of the portfolio they displace and should not be read as
    genuinely better.
    """
    sub = (summary[summary["profile"] == profile]
           .sort_values(["base_cost", "mean_hours_lost"]))
    frontier = []
    best = np.inf
    best_ci_lo = np.inf
    for _, row in sub.iterrows():
        if row["mean_hours_lost"] < best - 1e-12:
            beyond = bool(row["mean_hours_lost"] < best_ci_lo)
            frontier.append({
                "profile": profile, "portfolio": row["portfolio"],
                "description": row["description"],
                "cost": float(row["base_cost"]),
                "mean_hours_lost": float(row["mean_hours_lost"]),
                "hours_lost_ci_lo": float(row["hours_lost_ci_lo"]),
                "hours_lost_ci_hi": float(row["hours_lost_ci_hi"]),
                "catastrophic_prob": float(row["catastrophic_prob"]),
                "improvement_exceeds_noise": int(beyond),
            })
            best = row["mean_hours_lost"]
            best_ci_lo = row["hours_lost_ci_lo"]
    return pd.DataFrame(frontier)


def minimum_budget_table(summary: pd.DataFrame, cfg: Config,
                         max_budget: int = 25) -> pd.DataFrame:
    """Smallest integer budget whose best portfolio meets the
    catastrophic-probability target, per profile (base costs).

    Three answers are reported per profile, because the honest one depends
    on how the number was obtained:

      * ``min_budget`` — smallest budget whose best portfolio's *point*
        estimate of P(catastrophic) is <= target. Coarse (4-point steps at
        n=25) and optimistic, because it is the minimum over many noisy
        candidates.
      * ``min_budget_ci95_marginal`` — smallest budget at which some feasible
        portfolio's *marginal* Wilson 95% upper bound is <= target. NOTE: this
        is **not** selection-aware. Taking the most favourable of up to 192
        candidates measured on the same trials does not retain 95% coverage,
        so this column must not be quoted as "95% confident".
      * ``min_budget_ci95_simultaneous`` — the defensible one. Each feasible
        candidate's interval is computed at ``alpha/m`` (Bonferroni over the
        m candidates actually searched at that budget), so the statement
        "this portfolio's P(catastrophic) <= target" holds *simultaneously*
        across the whole search at 95%. Quote this column for any claim that
        a budget reaches the target.
    """
    target = cfg.optimization.catastrophic_target
    rows = []
    for profile in cfg.optimization.profiles:
        sub = summary[summary["profile"] == profile]
        found = found_marg = found_simul = None
        sel_prob = sel_lo = sel_hi = np.nan
        n_candidates_at_found = np.nan
        for budget in range(0, max_budget + 1):
            feasible = sub[sub["base_cost"] <= budget]
            if feasible.empty:
                continue
            if found is None and feasible["catastrophic_prob"].min() <= target:
                found = budget
                best = feasible.loc[feasible["catastrophic_prob"].idxmin()]
                sel_prob = float(best["catastrophic_prob"])
                sel_lo = float(best["catastrophic_prob_ci_lo"])
                sel_hi = float(best["catastrophic_prob_ci_hi"])
                n_candidates_at_found = int(len(feasible))
            if (found_marg is None
                    and feasible["catastrophic_prob_ci_hi"].min() <= target):
                found_marg = budget
            if found_simul is None:
                m = max(1, len(feasible))
                alpha_adj = 0.05 / m          # Bonferroni over the search
                uppers = []
                for _, r in feasible.iterrows():
                    n = int(r["n_trials"])
                    k = int(round(float(r["catastrophic_prob"]) * n))
                    uppers.append(wilson_ci(k, n, alpha=alpha_adj)[1])
                if uppers and min(uppers) <= target:
                    found_simul = budget
            if (found is not None and found_marg is not None
                    and found_simul is not None):
                break
        rows.append({
            "profile": profile,
            "catastrophic_target": target,
            "min_budget": found if found is not None else np.nan,
            "reachable": int(found is not None),
            "n_candidates_searched_at_min_budget": n_candidates_at_found,
            "selected_catastrophic_prob": sel_prob,
            "selected_cat_prob_ci_lo": sel_lo,
            "selected_cat_prob_ci_hi": sel_hi,
            "min_budget_ci95_marginal":
                found_marg if found_marg is not None else np.nan,
            "reachable_ci95_marginal": int(found_marg is not None),
            "min_budget_ci95_simultaneous":
                found_simul if found_simul is not None else np.nan,
            "reachable_ci95_simultaneous": int(found_simul is not None),
        })
    return pd.DataFrame(rows)


def selection_stability(raw: pd.DataFrame, summary: pd.DataFrame,
                        cfg: Config, n_boot: int = 500) -> pd.DataFrame:
    """Measure how identifiable the selected 'best portfolio' actually is.

    For each profile x budget we resample each candidate's own trials with
    replacement (a stratified bootstrap), re-run the same
    min-expected-disruption selection, and record how often the originally
    selected portfolio wins again — plus how many distinct portfolios ever
    win.

    Why this exists: the optimizer takes the minimum sample mean over up to
    192 candidates at 25 trials each. That is a classic winner's-curse
    setup — the winner's score is biased optimistic and its *identity* can be
    mostly noise. A low ``reselection_rate`` means the specific best
    portfolio is not identifiable at this sample size and must not be
    presented as a firm recommendation, even when the ranking of control
    *types* (segmentation, detection, backups) is stable. Publishing the
    number is more honest than implying a precision the design cannot
    deliver.
    """
    rng = np.random.default_rng(cfg.seed)
    rows = []
    for profile in cfg.optimization.profiles:
        sub = summary[summary["profile"] == profile]
        rawp = raw[raw["profile"] == profile]
        hours = {name: g[DISRUPTION_METRIC].to_numpy(dtype=float)
                 for name, g in rawp.groupby("portfolio")}
        for budget in cfg.optimization.budgets:
            feasible = sub[sub["base_cost"] <= budget]
            names = [n for n in feasible["portfolio"].tolist() if n in hours]
            if len(names) < 2:
                continue
            n_trials = min(len(hours[n]) for n in names)
            H = np.array([hours[n][:n_trials] for n in names])   # (P, T)
            n_cand = H.shape[0]
            orig = int(H.mean(axis=1).argmin())
            idx = rng.integers(0, n_trials, size=(n_boot, n_cand, n_trials))
            means = np.take_along_axis(H[None, :, :], idx, axis=2).mean(axis=2)
            winners = means.argmin(axis=1)
            rows.append({
                "profile": profile,
                "budget": budget,
                "n_candidates": n_cand,
                "trials_per_candidate": n_trials,
                "selected_portfolio": names[orig],
                "reselection_rate": float((winners == orig).mean()),
                "n_distinct_bootstrap_winners": int(np.unique(winners).size),
                "n_bootstrap_samples": n_boot,
            })
    return pd.DataFrame(rows)


def optimize(cfg: Config,
             defense_costs_path: str | Path | None = None) -> dict[str, Path]:
    """Full optimization pipeline; writes raw + processed CSVs."""
    log = setup_logging(resolve_path(cfg.output.logs_dir), "grrc.optimize")
    raw_dir = resolve_path(cfg.output.raw_dir)
    proc_dir = resolve_path(cfg.output.processed_dir)
    ensure_dirs(raw_dir, proc_dir)
    costs = load_defense_costs(
        defense_costs_path or resolve_path("configs/defense_costs.yaml"))

    distinct_counts = {
        profile: len(distinct_portfolios_for_profile(cfg, profile))
        for profile in cfg.optimization.profiles}
    log.info("evaluating distinct candidate portfolios per profile %s "
             "(%d trials each)", distinct_counts,
             cfg.optimization.trials_per_portfolio)
    raw = evaluate_candidate_portfolios(cfg)
    raw_path = raw_dir / f"{cfg.mode}_optimization_results.csv"
    write_csv(raw, raw_path)

    summary = summarize_portfolios(raw, cfg, costs)
    summary_path = proc_dir / f"{cfg.mode}_portfolio_summary.csv"
    write_csv(summary, summary_path)

    best_rows: list[dict] = []
    for profile in cfg.optimization.profiles:
        baseline_hours = float(
            _zero_cost_baseline(summary, profile)["mean_hours_lost"])
        for scale in cfg.optimization.cost_scale_factors:
            for budget in cfg.optimization.budgets:
                best_rows.extend(select_best(
                    summary, profile, budget, scale, baseline_hours))
    best = pd.DataFrame(best_rows)
    best_path = proc_dir / f"{cfg.mode}_best_portfolios.csv"
    write_csv(best, best_path)

    pareto = pd.concat([pareto_frontier(summary, p)
                        for p in cfg.optimization.profiles],
                       ignore_index=True)
    pareto_path = proc_dir / f"{cfg.mode}_pareto_frontier.csv"
    write_csv(pareto, pareto_path)

    # Defense-inclusion stability across cost scenarios (min-disruption
    # criterion): how often does each control appear in the winner?
    stab = (best[best["criterion"] == "min_expected_disruption"]
            .groupby("profile")[CONTROL_COLUMNS].mean().reset_index())
    stab_path = proc_dir / f"{cfg.mode}_cost_sensitivity.csv"
    write_csv(stab, stab_path)

    min_budget = minimum_budget_table(summary, cfg)
    min_budget_path = proc_dir / f"{cfg.mode}_minimum_budget.csv"
    write_csv(min_budget, min_budget_path)

    stability = selection_stability(raw, summary, cfg)
    stability_sel_path = proc_dir / f"{cfg.mode}_selection_stability.csv"
    write_csv(stability, stability_sel_path)
    if not stability.empty:
        log.info("selection stability (reselection rate of the chosen "
                 "winner): min=%.1f%% max=%.1f%%",
                 100 * stability["reselection_rate"].min(),
                 100 * stability["reselection_rate"].max())

    manifest = {
        "mode": cfg.mode, "master_seed": cfg.seed,
        "n_trials": len(raw),
        "distinct_candidates_per_profile": distinct_counts,
        "profiles": cfg.optimization.profiles,
        "budgets": cfg.optimization.budgets,
        "cost_scale_factors": cfg.optimization.cost_scale_factors,
    }
    (raw_dir / f"{cfg.mode}_optimization_manifest.json").write_text(
        json.dumps(manifest, indent=2))

    log.info("optimization complete: %d trials, outputs in %s",
             len(raw), proc_dir)
    return {"raw": raw_path, "summary": summary_path, "best": best_path,
            "pareto": pareto_path, "cost_sensitivity": stab_path,
            "min_budget": min_budget_path,
            "selection_stability": stability_sel_path}
