"""Cybersecurity defense controls and portfolios.

A :class:`DefensePortfolio` is a bundle of defense controls layered on top
of a cyber-capacity profile. :func:`effective_settings` resolves the
profile + portfolio into the concrete parameters the simulator uses, and
:func:`portfolio_cost` prices a portfolio in *normalized cost points*
(model abstractions — explicitly NOT dollar estimates; see
configs/defense_costs.yaml and docs/assumptions.md A16).

Controls modeled:
  * Segmentation architecture (flat / basic / least-privilege)
  * Patch coverage upgrades along the ladder 25% -> 50% -> 75% -> 90%
  * Detection improvement (one tier faster on the delay ladder)
  * Rapid automated isolation (high isolation success, same-step attempt)
  * Protected (isolated/immutable) backups
  * Identity & access restrictions
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator

from .config import Config, ProfileSpec
from .enums import BackupStrategy, SegmentationLevel

#: Patch-coverage ladder used by upgrades and by the optimizer.
PATCH_LADDER: tuple[float, ...] = (0.25, 0.50, 0.75, 0.90)

#: Detection-delay ladder (steps); improvement moves one tier faster.
DETECTION_LADDER: tuple[int, ...] = (24, 12, 6, 3, 1)

@dataclass(frozen=True)
class DefensePortfolio:
    """A bundle of defense controls.

    ``None`` fields mean 'keep the profile's baseline setting'. The main
    experiment uses explicit settings so each named condition means the
    same thing under every profile; the special portfolio
    ``profile_baseline`` keeps everything at profile defaults.
    """

    name: str
    segmentation: SegmentationLevel | None = None
    patch_boost_levels: int = 0
    patch_coverage_override: float | None = None
    detection_improvement: bool = False
    detection_delay_override: int | None = None
    rapid_isolation: bool = False
    backup_override: BackupStrategy | None = None
    identity_controls: bool = False


@dataclass(frozen=True)
class EffectiveSettings:
    """Concrete simulator parameters after profile + portfolio resolution."""

    segmentation: SegmentationLevel
    patch_coverage: float
    detection_delay: int
    isolation_success: float
    isolate_same_step: bool
    backup_strategy: str
    identity_controls: bool


def _ladder_index(ladder: tuple, value: float) -> int:
    """Index of the ladder rung closest to ``value``."""
    diffs = [abs(rung - value) for rung in ladder]
    return diffs.index(min(diffs))


def boosted_patch_coverage(baseline: float, levels: int) -> float:
    """Patch coverage after ``levels`` ladder upgrades from ``baseline``."""
    if levels <= 0:
        return baseline
    idx = _ladder_index(PATCH_LADDER, baseline)
    new_idx = min(idx + levels, len(PATCH_LADDER) - 1)
    return max(baseline, PATCH_LADDER[new_idx])


def improved_detection_delay(baseline: int) -> int:
    """Detection delay after one tier of improvement (faster)."""
    idx = _ladder_index(DETECTION_LADDER, baseline)
    new_idx = min(idx + 1, len(DETECTION_LADDER) - 1)
    return min(baseline, DETECTION_LADDER[new_idx])


def effective_settings(
    profile: ProfileSpec,
    portfolio: DefensePortfolio,
    *,
    patch_override: float | None = None,
    detection_override: int | None = None,
    rapid_isolation_success: float = 0.95,
    detection_improvement_factor: float | None = None,
) -> EffectiveSettings:
    """Resolve profile + portfolio (+ sweep overrides) into simulator settings.

    Precedence for patch coverage and detection delay:
    sweep override > portfolio override > portfolio upgrade > profile value.
    """
    segmentation = portfolio.segmentation or SegmentationLevel(
        profile.base_segmentation)

    patch = profile.patch_coverage
    if portfolio.patch_boost_levels:
        patch = boosted_patch_coverage(patch, portfolio.patch_boost_levels)
    if portfolio.patch_coverage_override is not None:
        patch = portfolio.patch_coverage_override
    if patch_override is not None:
        patch = patch_override

    delay = profile.detection_delay_steps
    if portfolio.detection_improvement:
        if detection_improvement_factor is None:
            delay = improved_detection_delay(delay)
        else:
            delay = max(1, int(round(
                delay * detection_improvement_factor)))
    if portfolio.detection_delay_override is not None:
        delay = portfolio.detection_delay_override
    if detection_override is not None:
        delay = detection_override

    isolation = profile.isolation_success
    if portfolio.rapid_isolation:
        isolation = max(isolation, rapid_isolation_success)

    backup = (portfolio.backup_override.value
              if portfolio.backup_override else profile.backup_strategy)

    return EffectiveSettings(
        segmentation=segmentation,
        patch_coverage=patch,
        detection_delay=delay,
        isolation_success=isolation,
        isolate_same_step=portfolio.rapid_isolation,
        backup_strategy=backup,
        identity_controls=portfolio.identity_controls,
    )


# ---------------------------------------------------------------------------
# Named portfolio catalog (main experiment conditions)
# ---------------------------------------------------------------------------
# Single-control conditions sit on an explicit flat/connected base so each
# control's effect is measured against the same reference (baseline_flat).

_FLAT = SegmentationLevel.FLAT
_BASIC = SegmentationLevel.BASIC
_LP = SegmentationLevel.LEAST_PRIVILEGE
_CONN = BackupStrategy.CONNECTED
_ISO = BackupStrategy.ISOLATED

PORTFOLIO_CATALOG: dict[str, DefensePortfolio] = {p.name: p for p in [
    DefensePortfolio("baseline_flat", segmentation=_FLAT,
                     backup_override=_CONN),
    DefensePortfolio("profile_baseline"),  # as-is posture of each profile
    DefensePortfolio("basic_segmentation", segmentation=_BASIC,
                     backup_override=_CONN),
    DefensePortfolio("least_privilege", segmentation=_LP,
                     backup_override=_CONN),
    DefensePortfolio("patch_90", segmentation=_FLAT,
                     patch_coverage_override=0.90, backup_override=_CONN),
    DefensePortfolio("fast_detection", segmentation=_FLAT,
                     detection_improvement=True, rapid_isolation=True,
                     backup_override=_CONN),
    DefensePortfolio("isolated_backups", segmentation=_FLAT,
                     backup_override=_ISO),
    DefensePortfolio("identity_controls", segmentation=_FLAT,
                     identity_controls=True, backup_override=_CONN),
    DefensePortfolio("seg_plus_patch", segmentation=_BASIC,
                     patch_coverage_override=0.90, backup_override=_CONN),
    DefensePortfolio("seg_plus_detection", segmentation=_BASIC,
                     detection_improvement=True, rapid_isolation=True,
                     backup_override=_CONN),
    DefensePortfolio("detection_plus_backups", segmentation=_FLAT,
                     detection_improvement=True, rapid_isolation=True,
                     backup_override=_ISO),
    DefensePortfolio("patch_plus_least_privilege", segmentation=_LP,
                     patch_coverage_override=0.90, backup_override=_CONN),
    DefensePortfolio("seg_detect_backup", segmentation=_BASIC,
                     detection_improvement=True, rapid_isolation=True,
                     backup_override=_ISO),
    DefensePortfolio("full_defense", segmentation=_LP,
                     patch_coverage_override=0.90,
                     detection_improvement=True, rapid_isolation=True,
                     backup_override=_ISO, identity_controls=True),
]}


def get_portfolio(name: str) -> DefensePortfolio:
    try:
        return PORTFOLIO_CATALOG[name]
    except KeyError:
        raise KeyError(
            f"unknown portfolio '{name}'; known: "
            f"{sorted(PORTFOLIO_CATALOG)}") from None


# ---------------------------------------------------------------------------
# Costing (normalized points — NOT dollars)
# ---------------------------------------------------------------------------

def portfolio_cost(portfolio: DefensePortfolio, profile: ProfileSpec,
                   costs: dict[str, float], scale: float = 1.0) -> float:
    """Price a portfolio relative to a flat/connected, profile-baseline
    posture, in normalized cost points scaled by ``scale``.

    Patch upgrades are priced per ladder level actually gained from the
    profile's baseline, so reaching 90% coverage costs more for a
    lower-capacity profile — a deliberate modeling choice (docs A16).
    """
    total = 0.0
    seg = portfolio.segmentation
    if seg == SegmentationLevel.BASIC:
        total += costs["basic_segmentation"]
    elif seg == SegmentationLevel.LEAST_PRIVILEGE:
        total += costs["least_privilege_segmentation"]

    target_patch = None
    if portfolio.patch_coverage_override is not None:
        target_patch = portfolio.patch_coverage_override
    elif portfolio.patch_boost_levels:
        target_patch = boosted_patch_coverage(
            profile.patch_coverage, portfolio.patch_boost_levels)
    if target_patch is not None and target_patch > profile.patch_coverage:
        levels = (_ladder_index(PATCH_LADDER, target_patch)
                  - _ladder_index(PATCH_LADDER, profile.patch_coverage))
        total += max(0, levels) * costs["patch_level_upgrade"]

    if portfolio.detection_improvement:
        total += costs["detection_improvement"]
    if portfolio.rapid_isolation:
        total += costs["rapid_isolation"]
    if portfolio.backup_override == BackupStrategy.ISOLATED:
        total += costs["protected_backups"]
    if portfolio.identity_controls:
        total += costs["identity_controls"]
    return total * scale


# ---------------------------------------------------------------------------
# Optimizer search space
# ---------------------------------------------------------------------------

def enumerate_portfolios() -> Iterator[DefensePortfolio]:
    """All composable defense combinations searched by the optimizer.

    3 segmentation tiers x 4 patch boosts x 2 detection x 2 isolation x
    2 backup x 2 identity = 192 candidate portfolios. Patch boosts run
    0..3 so that the ceiling (90%) is reachable from *every* profile's
    baseline — including the resource-constrained profile (25% baseline,
    which needs +3 rungs) — matching the 90%-patch conditions the main
    experiment studies. Because a boost is capped at the top rung, several
    of these resolve to the same effective configuration for higher-
    baseline profiles; the optimizer evaluates each *distinct* resolved
    configuration once per profile (see optimization.py) so no duplicate is
    double-counted. Each portfolio is priced by :func:`portfolio_cost`;
    feasibility under a budget is decided by the optimizer, not here.
    """
    for seg in (_FLAT, _BASIC, _LP):
        for patch_boost in (0, 1, 2, 3):
            for det in (False, True):
                for iso in (False, True):
                    for bak in (_CONN, _ISO):
                        for idm in (False, True):
                            name = (
                                f"seg-{seg.value}|patch+{patch_boost}"
                                f"|det{int(det)}|iso{int(iso)}"
                                f"|bak-{bak.value}|idm{int(idm)}"
                            )
                            yield DefensePortfolio(
                                name=name, segmentation=seg,
                                patch_boost_levels=patch_boost,
                                detection_improvement=det,
                                rapid_isolation=iso,
                                backup_override=bak,
                                identity_controls=idm,
                            )


def describe_portfolio(p: DefensePortfolio) -> str:
    """Human-readable one-line description (used in tables/reports)."""
    parts: list[str] = []
    if p.segmentation:
        parts.append(f"segmentation={p.segmentation.value}")
    if p.patch_coverage_override is not None:
        parts.append(f"patch={p.patch_coverage_override:.0%}")
    elif p.patch_boost_levels:
        parts.append(f"patch+{p.patch_boost_levels} levels")
    if p.detection_improvement:
        parts.append("faster detection")
    if p.rapid_isolation:
        parts.append("rapid isolation")
    if p.backup_override:
        parts.append(f"backups={p.backup_override.value}")
    if p.identity_controls:
        parts.append("identity controls")
    return "; ".join(parts) if parts else "profile baseline posture"
