"""Scenario-paired interpretation diagnostics for finite simulation studies.

These functions analyze recorded trials; they do not alter the simulator.
Resampling describes uncertainty conditional on the observed bank and model.
"""
from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations

import numpy as np
import pandas as pd
from scipy.stats import t

from .multiobjective import OBJECTIVES, pareto_mask


@dataclass
class PairedBank:
    profile: str
    names: list[str]
    scenarios: np.ndarray
    loss: np.ndarray
    outage: np.ndarray  # scenario x candidate x k
    nonrecovery: np.ndarray
    static: np.ndarray  # candidate x (cost, burden)
    finalist: np.ndarray

    def objectives(self, draw: np.ndarray | None = None, k: int = 4) -> np.ndarray:
        if k not in (1, 2, 3, 4):
            raise ValueError("k must be between one and four")
        ix = np.arange(len(self.scenarios)) if draw is None else draw
        values = self.loss[ix]
        return np.column_stack((values.mean(axis=0), upper_tail_mean(values),
                                self.outage[ix, :, k - 1].mean(axis=0),
                                self.nonrecovery[ix].mean(axis=0), self.static))


def upper_tail_mean(values: np.ndarray) -> np.ndarray:
    """Historical empirical tail convention, including ties at the quantile."""
    values = np.asarray(values, dtype=float)
    if values.ndim != 2 or not np.isfinite(values).all():
        raise ValueError("finite scenario-by-candidate matrix required")
    cutoff = np.quantile(values, .9, axis=0)
    keep = values >= cutoff
    return np.where(keep, values, 0).sum(axis=0) / keep.sum(axis=0)


def make_bank(raw: pd.DataFrame, summary: pd.DataFrame, profile: str,
              finalists: list[str]) -> PairedBank:
    frame = raw.loc[raw.profile == profile].copy()
    if frame.empty or not frame.paired.eq(1).all():
        raise ValueError("nonempty paired trials required")
    if frame.duplicated(["scenario_id", "portfolio"]).any():
        raise ValueError("duplicate scenario/candidate cell")
    names = sorted(frame.portfolio.unique())
    scenarios = np.sort(frame.scenario_id.unique())
    if len(scenarios) < 2:
        raise ValueError("at least two scenarios required")
    expected = pd.MultiIndex.from_product([scenarios, names],
                                         names=["scenario_id", "portfolio"])
    indexed = frame.set_index(["scenario_id", "portfolio"]).reindex(expected)
    columns = ["weighted_service_hours_lost", "recovered_within_horizon"] + [
        f"sustained_clinical_outage_k{k}" for k in range(1, 5)]
    if indexed[columns].isna().any().any():
        raise ValueError("incomplete scenario/candidate bank")
    values = indexed[columns].to_numpy(float)
    if not np.isfinite(values).all():
        raise ValueError("nonfinite trial result")
    indicators = values[:, 1:]
    if not np.isin(indicators, [0., 1.]).all():
        raise ValueError("event indicators must be binary")
    shape = (len(scenarios), len(names))
    outage = values[:, 2:].reshape(*shape, 4)
    if (np.diff(outage, axis=2) > 0).any():
        raise ValueError("k ladder must be monotonically nonincreasing")
    s = summary.loc[summary.profile == profile].set_index("portfolio")
    if s.index.has_duplicates or set(s.index) != set(names):
        raise ValueError("summary and raw candidate sets differ")
    if not set(finalists) <= set(names):
        raise ValueError("finalist outside candidate bank")
    static = s.loc[names, ["implementation_cost_points", "operational_burden_points"]].to_numpy(float)
    if not np.isfinite(static).all() or (static < 0).any():
        raise ValueError("cost and burden must be finite and nonnegative")
    return PairedBank(profile, names, scenarios,
                      values[:, 0].reshape(shape), outage,
                      1 - values[:, 1].reshape(shape), static,
                      np.array([n in finalists for n in names]))


def pairwise_standard_errors(values: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """SE(mean_i - mean_j), with and without the observed paired covariance."""
    values = np.asarray(values, dtype=float)
    if values.ndim != 2 or len(values) < 2 or not np.isfinite(values).all():
        raise ValueError("finite matrix with at least two scenarios required")
    covariance = np.atleast_2d(np.cov(values, rowvar=False, ddof=1)) / len(values)
    variances = np.diag(covariance)
    independent = np.sqrt(np.maximum(variances[:, None] + variances[None, :], 0))
    paired = np.sqrt(np.maximum(independent ** 2 - 2 * covariance, 0))
    np.fill_diagonal(paired, 0)
    return paired, independent


def covariance_difference_se(draws: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """SE differences from bootstrap estimators, without another division by B."""
    paired, independent = pairwise_standard_errors(draws)
    return paired * np.sqrt(len(draws)), independent * np.sqrt(len(draws))


def frontier_counts(matrix: np.ndarray, finalist: np.ndarray) -> dict[str, int]:
    full = pareto_mask(matrix)
    restricted = np.zeros(len(matrix), dtype=bool)
    if finalist.any():
        restricted[finalist] = pareto_mask(matrix[finalist])
    return {"full_frontier": int(full.sum()),
            "restricted_frontier": int(restricted.sum()),
            "omitted_efficient": int((full & ~finalist).sum()),
            "restricted_artifacts": int((restricted & ~full).sum())}


def bootstrap_bank(bank: PairedBank, *, n_boot: int, seed: int) -> tuple[pd.DataFrame, np.ndarray, np.ndarray]:
    if n_boot < 2:
        raise ValueError("at least two bootstrap draws required")
    rng = np.random.default_rng(seed)
    records = []
    tails = np.empty((n_boot, len(bank.names)))
    gaps = np.empty(n_boot)
    for b in range(n_boot):
        draw = rng.integers(len(bank.scenarios), size=len(bank.scenarios))
        matrix = bank.objectives(draw)
        tails[b] = matrix[:, 1]
        gaps[b] = (bank.outage[draw, :, 0] - bank.outage[draw, :, 3]).mean()
        records.append({"profile": bank.profile, "draw": b, **frontier_counts(matrix, bank.finalist)})
    return pd.DataFrame(records), tails, gaps


def resolution_diagnostic(bank: PairedBank, tail_draws: np.ndarray) -> dict[str, object]:
    estimates = bank.objectives()[:, :4]
    pairs = [pairwise_standard_errors(bank.loss),
             covariance_difference_se(tail_draws),
             pairwise_standard_errors(bank.outage[:, :, 3]),
             pairwise_standard_errors(bank.nonrecovery)]
    gap = np.abs(estimates[:, None, :] - estimates[None, :, :])
    paired = np.stack([p[0] for p in pairs], axis=2)
    independent = np.stack([p[1] for p in pairs], axis=2)
    upper = np.triu(np.ones((len(bank.names), len(bank.names)), dtype=bool), 1)
    near_paired = (gap <= paired + 1e-12).all(axis=2) & upper
    near_independent = (gap <= independent + 1e-12).all(axis=2) & upper
    return {"profile": bank.profile, "candidate_pairs": int(upper.sum()),
            "paired_one_se_near_pairs": int(near_paired.sum()),
            "independent_one_se_near_pairs": int(near_independent.sum()),
            "classification_changed_pairs": int(((near_paired != near_independent) & upper).sum()),
            "interpretation": "one-SE diagnostic, not a hypothesis/equivalence test"}


def baseline_contrasts(bank: PairedBank, family_size: int, alpha: float = .05) -> pd.DataFrame:
    zeros = np.flatnonzero(bank.static[:, 0] == 0)
    if len(zeros) != 1 or family_size < len(bank.names) - 1:
        raise ValueError("unique free baseline and sufficient contrast family required")
    baseline = zeros[0]
    critical = t.ppf(1 - alpha / (2 * family_size), len(bank.scenarios) - 1)
    ordinary = t.ppf(1 - alpha / 2, len(bank.scenarios) - 1)
    records = []
    for j, name in enumerate(bank.names):
        if j == baseline:
            continue
        difference = bank.loss[:, baseline] - bank.loss[:, j]
        effect = difference.mean()
        se = difference.std(ddof=1) / np.sqrt(len(difference))
        independent = np.sqrt((bank.loss[:, baseline].var(ddof=1) + bank.loss[:, j].var(ddof=1)) / len(difference))
        valid = se > 0
        records.append({"profile": bank.profile, "baseline": bank.names[baseline],
                        "portfolio": name, "n_scenarios": len(difference),
                        "mean_hours_saved": effect, "paired_se": se,
                        "independent_se": independent, "family_size": family_size,
                        "pointwise_lower": effect - ordinary * se if valid else np.nan,
                        "pointwise_upper": effect + ordinary * se if valid else np.nan,
                        "simultaneous_lower": effect - critical * se if valid else np.nan,
                        "simultaneous_upper": effect + critical * se if valid else np.nan,
                        "interval_status": "approximate paired t, Bonferroni" if valid else "unestimable: zero sample variance"})
    return pd.DataFrame(records)


def endpoint_frontiers(bank: PairedBank) -> pd.DataFrame:
    base = pareto_mask(bank.objectives(k=4))
    rows = []
    for k in range(1, 5):
        mask = pareto_mask(bank.objectives(k=k))
        union = (base | mask).sum()
        rows.append({"profile": bank.profile, "k": k,
                     "candidate_mean_probability": bank.outage[:, :, k - 1].mean(),
                     "frontier_size": int(mask.sum()),
                     "added_vs_k4": int((mask & ~base).sum()),
                     "removed_vs_k4": int((base & ~mask).sum()),
                     "jaccard_vs_k4": (base & mask).sum() / union if union else 1.})
    return pd.DataFrame(rows)


def objective_ablation(bank: PairedBank) -> pd.DataFrame:
    matrix = bank.objectives()
    original = pareto_mask(matrix)
    rows = []
    for size in range(1, len(OBJECTIVES) + 1):
        for subset in combinations(range(len(OBJECTIVES)), size):
            mask = pareto_mask(matrix[:, subset])
            rows.append({"profile": bank.profile, "dimensions": size,
                         "objectives": "|".join(OBJECTIVES[j] for j in subset),
                         "frontier_size": int(mask.sum()),
                         "added_vs_six": int((mask & ~original).sum()),
                         "removed_vs_six": int((original & ~mask).sum())})
    return pd.DataFrame(rows)
