"""Statistical analysis of raw simulation results.

Emphasis (per the study design): effect sizes and bootstrap confidence
intervals first; non-parametric hypothesis tests (Mann-Whitney U with
Holm correction) only for the focused defense-vs-baseline comparisons.
Simulation outcomes are heavily skewed, so medians/IQRs and rank-based
tests are appropriate; normality is never assumed.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

from .config import Config
from .utilities import ensure_dirs, resolve_path, setup_logging, write_csv

#: Outcome columns summarized for every experimental cell.
#: NOTE: ``recovery_step`` is deliberately NOT summarized here. It encodes
#: "never recovered within the horizon" as -1 (a censored, worst-case
#: outcome), so a plain mean/median would treat the worst runs as the
#: best. Recovery is instead reported by :func:`recovery_summary` (recovery
#: probability + median time among trials that actually recovered). The
#: clean 0/1 indicator ``recovered_within_horizon`` is safe to average and
#: is included below.
KEY_METRICS = [
    "weighted_service_hours_lost", "pct_compromised", "catastrophic",
    "total_service_downtime_steps", "backup_compromised",
    "identity_compromised", "recovered_within_horizon",
    "pct_clinical_capacity_lost", "defensive_isolation_node_steps",
]

BASELINE_PORTFOLIO = "baseline_flat"


def bootstrap_ci(values: np.ndarray, n_boot: int = 2000,
                 alpha: float = 0.05, seed: int = 0) -> tuple[float, float]:
    """Percentile bootstrap CI for the mean."""
    values = np.asarray(values, dtype=float)
    if values.size == 0:
        return (np.nan, np.nan)
    if values.size == 1:
        return (float(values[0]), float(values[0]))
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, values.size, size=(n_boot, values.size))
    means = values[idx].mean(axis=1)
    return (float(np.percentile(means, 100 * alpha / 2)),
            float(np.percentile(means, 100 * (1 - alpha / 2))))


def wilson_ci(successes: int, n: int,
              alpha: float = 0.05) -> tuple[float, float]:
    """Wilson score confidence interval for a binomial proportion.

    Used for probabilities estimated from a small number of Monte Carlo
    trials (e.g. catastrophic-disruption probability at n=25 per cell),
    where the normal approximation is unreliable and the point estimate
    alone hides real sampling uncertainty. Returns (lo, hi), both clamped
    to [0, 1].
    """
    if n <= 0:
        return (float("nan"), float("nan"))
    z = float(stats.norm.ppf(1 - alpha / 2))
    p = successes / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = (z / denom) * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (float(max(0.0, center - half)), float(min(1.0, center + half)))


def summarize(values: np.ndarray, seed: int = 0) -> dict[str, float]:
    """Mean/median/std/IQR/percentiles/CI for one metric sample."""
    values = np.asarray(values, dtype=float)
    lo, hi = bootstrap_ci(values, seed=seed)
    q1, q3 = np.percentile(values, [25, 75])
    return {
        "n": int(values.size),
        "mean": float(values.mean()),
        "median": float(np.median(values)),
        "std": float(values.std(ddof=1)) if values.size > 1 else 0.0,
        "iqr": float(q3 - q1),
        "p90": float(np.percentile(values, 90)),
        "p95": float(np.percentile(values, 95)),
        "ci95_lo": lo,
        "ci95_hi": hi,
    }


def cliffs_delta(a: np.ndarray, b: np.ndarray) -> float:
    """Cliff's delta effect size in [-1, 1] (negative: a < b typically).

    Computed from the Mann-Whitney U statistic: delta = 2U/(n_a n_b) - 1.
    """
    a, b = np.asarray(a, float), np.asarray(b, float)
    if a.size == 0 or b.size == 0:
        return np.nan
    u, _ = stats.mannwhitneyu(a, b, alternative="two-sided")
    return float(2.0 * u / (a.size * b.size) - 1.0)


def holm_correction(pvals: list[float]) -> list[float]:
    """Holm-Bonferroni adjusted p-values (step-down, monotone)."""
    m = len(pvals)
    order = np.argsort(pvals)
    adjusted = np.empty(m)
    running_max = 0.0
    for rank, idx in enumerate(order):
        adj = min(1.0, (m - rank) * pvals[idx])
        running_max = max(running_max, adj)
        adjusted[idx] = running_max
    return adjusted.tolist()


def group_summaries(df: pd.DataFrame, group_cols: list[str],
                    metrics: list[str] | None = None,
                    seed: int = 0) -> pd.DataFrame:
    """Long-format summary table: one row per group x metric."""
    metrics = metrics or [m for m in KEY_METRICS if m in df.columns]
    rows = []
    for keys, grp in df.groupby(group_cols):
        keys = keys if isinstance(keys, tuple) else (keys,)
        for metric in metrics:
            rows.append({
                **dict(zip(group_cols, keys)),
                "metric": metric,
                **summarize(grp[metric].to_numpy(), seed=seed),
            })
    return pd.DataFrame(rows)


def recovery_summary(df: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    """Censoring-aware recovery analysis (replaces naive mean recovery_step).

    ``recovery_step`` (propagation.py) is coded as:
      * ``0``        — the trial never had a clinical outage;
      * ``positive`` — the step at which clinical service was restored;
      * ``-1``       — outage never recovered within the horizon (censored).

    Averaging that column directly is invalid: the *worst* outcome (-1) is
    numerically the smallest. Instead we report, per group, the outage
    rate, the recovery probability among trials that had an outage, and the
    median/P90 recovery time among trials that actually recovered.
    """
    rows = []
    for keys, grp in df.groupby(group_cols):
        keys = keys if isinstance(keys, tuple) else (keys,)
        rs = grp["recovery_step"].to_numpy()
        n = int(rs.size)
        recovered = int((rs > 0).sum())
        censored = int((rs == -1).sum())
        had_outage = recovered + censored
        rec_times = rs[rs > 0]
        rows.append({
            **dict(zip(group_cols, keys)),
            "n": n,
            "n_no_outage": int((rs == 0).sum()),
            "n_recovered": recovered,
            "n_censored_never_recovered": censored,
            "outage_rate": had_outage / n if n else np.nan,
            "recovery_prob_given_outage":
                recovered / had_outage if had_outage else np.nan,
            "median_recovery_step_recovered":
                float(np.median(rec_times)) if rec_times.size else np.nan,
            "p90_recovery_step_recovered":
                float(np.percentile(rec_times, 90))
                if rec_times.size else np.nan,
            "share_recovered_within_horizon":
                float((rs >= 0).mean()) if n else np.nan,
        })
    return pd.DataFrame(rows)


def baseline_comparisons(df: pd.DataFrame, seed: int = 0) -> pd.DataFrame:
    """Compare every portfolio to the flat baseline within each
    facility x profile cell (main experiment).

    Reports: relative reduction in mean weighted service-hours lost,
    absolute risk reduction in catastrophic probability, Cliff's delta,
    and Holm-corrected Mann-Whitney p-values on hours lost.
    """
    rows = []
    pvals = []
    for (facility, profile), grp in df.groupby(["facility", "profile"]):
        base = grp[grp["portfolio"] == BASELINE_PORTFOLIO]
        if base.empty:
            continue
        base_hours = base["weighted_service_hours_lost"].to_numpy()
        base_cat = float(base["catastrophic"].mean())
        for portfolio, sub in grp.groupby("portfolio"):
            if portfolio == BASELINE_PORTFOLIO:
                continue
            hours = sub["weighted_service_hours_lost"].to_numpy()
            cat = float(sub["catastrophic"].mean())
            _, p = stats.mannwhitneyu(hours, base_hours,
                                      alternative="two-sided")
            pvals.append(float(p))
            base_mean = float(base_hours.mean())
            rel = ((base_mean - float(hours.mean())) / base_mean
                   if base_mean > 0 else np.nan)
            lo, hi = bootstrap_ci(hours, seed=seed)
            rows.append({
                "facility": facility, "profile": profile,
                "portfolio": portfolio,
                "n": len(sub),
                "mean_hours_lost": float(hours.mean()),
                "hours_ci95_lo": lo, "hours_ci95_hi": hi,
                "baseline_mean_hours_lost": base_mean,
                "relative_reduction_hours": rel,
                "catastrophic_prob": cat,
                "baseline_catastrophic_prob": base_cat,
                "absolute_risk_reduction_catastrophic": base_cat - cat,
                "cliffs_delta_vs_baseline":
                    cliffs_delta(hours, base_hours),
                "mannwhitney_p": float(p),
            })
    out = pd.DataFrame(rows)
    if not out.empty:
        out["mannwhitney_p_holm"] = holm_correction(pvals)
        out["significant_holm_05"] = (
            out["mannwhitney_p_holm"] < 0.05).astype(int)
    return out


def kruskal_across_profiles(df: pd.DataFrame,
                            metric: str = "weighted_service_hours_lost") -> pd.DataFrame:
    """Kruskal-Wallis test of metric differences across capacity profiles,
    within each facility x portfolio condition."""
    rows = []
    for (facility, portfolio), grp in df.groupby(["facility", "portfolio"]):
        samples = [g[metric].to_numpy() for _, g in grp.groupby("profile")]
        if len(samples) < 2:
            continue
        try:
            h, p = stats.kruskal(*samples)
        except ValueError:  # all-identical values
            h, p = np.nan, 1.0
        rows.append({
            "facility": facility, "portfolio": portfolio,
            "metric": metric, "kruskal_h": float(h) if h == h else np.nan,
            "kruskal_p": float(p),
            "n_groups": len(samples),
        })
    return pd.DataFrame(rows)


def sweep_summary(sweep_df: pd.DataFrame, seed: int = 0) -> pd.DataFrame:
    """Patch x detection grid summary (Figure 3 data)."""
    rows = []
    for (patch, delay), grp in sweep_df.groupby(
            ["patch_coverage", "detection_delay"]):
        hours = grp["weighted_service_hours_lost"].to_numpy()
        lo, hi = bootstrap_ci(hours, seed=seed)
        rows.append({
            "patch_coverage": patch, "detection_delay": delay,
            "n": len(grp),
            "catastrophic_prob": float(grp["catastrophic"].mean()),
            "mean_hours_lost": float(hours.mean()),
            "hours_ci95_lo": lo, "hours_ci95_hi": hi,
            "mean_pct_compromised": float(grp["pct_compromised"].mean()),
        })
    return pd.DataFrame(rows)


def analyze(cfg: Config, main_csv: str | Path | None = None,
            sweep_csv: str | Path | None = None) -> dict[str, Path]:
    """Produce all processed summary tables from raw CSVs."""
    log = setup_logging(resolve_path(cfg.output.logs_dir), "grrc.analyze")
    raw_dir = resolve_path(cfg.output.raw_dir)
    proc_dir = resolve_path(cfg.output.processed_dir)
    ensure_dirs(proc_dir)
    main_path = Path(main_csv) if main_csv else (
        raw_dir / f"{cfg.mode}_main_results.csv")
    if not main_path.exists():
        raise FileNotFoundError(
            f"raw results not found: {main_path} — run "
            f"'python -m grrc.cli simulate --config <config>' first")
    df = pd.read_csv(main_path)
    outputs: dict[str, Path] = {}

    cell = group_summaries(
        df, ["facility", "profile", "portfolio"], seed=cfg.seed)
    p = proc_dir / f"{cfg.mode}_summary_by_portfolio.csv"
    write_csv(cell, p)
    outputs["summary_by_portfolio"] = p

    entry = group_summaries(
        df, ["profile", "portfolio", "entry_point"],
        metrics=["weighted_service_hours_lost", "catastrophic"],
        seed=cfg.seed)
    p = proc_dir / f"{cfg.mode}_summary_by_entry.csv"
    write_csv(entry, p)
    outputs["summary_by_entry"] = p

    rec = recovery_summary(df, ["facility", "profile", "portfolio"])
    p = proc_dir / f"{cfg.mode}_recovery_summary.csv"
    write_csv(rec, p)
    outputs["recovery_summary"] = p

    comps = baseline_comparisons(df, seed=cfg.seed)
    p = proc_dir / f"{cfg.mode}_baseline_comparisons.csv"
    write_csv(comps, p)
    outputs["baseline_comparisons"] = p

    kw = kruskal_across_profiles(df)
    p = proc_dir / f"{cfg.mode}_kruskal_profiles.csv"
    write_csv(kw, p)
    outputs["kruskal_profiles"] = p

    sweep_path = Path(sweep_csv) if sweep_csv else (
        raw_dir / f"{cfg.mode}_sweep_results.csv")
    if sweep_path.exists():
        sw = sweep_summary(pd.read_csv(sweep_path), seed=cfg.seed)
        p = proc_dir / f"{cfg.mode}_sweep_summary.csv"
        write_csv(sw, p)
        outputs["sweep_summary"] = p

    log.info("analysis complete; %d tables in %s", len(outputs), proc_dir)
    return outputs
