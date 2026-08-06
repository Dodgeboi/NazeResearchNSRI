"""Configuration schema and YAML loading.

Every numeric assumption of the model lives either here (as a documented
default) or in the YAML files under ``configs/``. YAML values override
defaults. All parameters are described in docs/assumptions.md and
docs/data_dictionary.md.

Design choice: plain dataclasses + explicit validation (instead of an
extra dependency) keep the schema readable for a student team.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .enums import BackupStrategy, EntryPoint, SegmentationLevel


class ConfigError(ValueError):
    """Raised when a configuration file contains invalid values."""


def _check(condition: bool, message: str) -> None:
    if not condition:
        raise ConfigError(message)


# --------------------------------------------------------------------------
# Sub-sections
# --------------------------------------------------------------------------

@dataclass
class FacilitySpec:
    """Node-count range for one synthetic facility size (model setting,
    not a real-world claim)."""

    min_nodes: int
    max_nodes: int

    def validate(self, name: str) -> None:
        _check(4 <= self.min_nodes <= self.max_nodes,
               f"facility '{name}': need 4 <= min_nodes <= max_nodes")


@dataclass
class ProfileSpec:
    """Neutral cyber-capacity profile (numbers only; no country labels)."""

    patch_coverage: float          # fraction of nodes patched at t=0
    detection_delay_steps: int     # mean steps from compromise to detection
    isolation_success: float       # per-step P(isolate | detected)
    legacy_fraction: float         # fraction of extra-high-vulnerability nodes
    base_segmentation: str         # architecture before added defenses
    backup_strategy: str           # baseline backup connectivity
    budget: int                    # abstract defense budget (cost points)
    complexity_factor: float = 1.0 # multiplier on cross-zone connectivity

    def validate(self, name: str) -> None:
        _check(0.0 <= self.patch_coverage <= 1.0,
               f"profile '{name}': patch_coverage must be in [0,1]")
        _check(self.detection_delay_steps >= 1,
               f"profile '{name}': detection_delay_steps must be >= 1")
        _check(0.0 <= self.isolation_success <= 1.0,
               f"profile '{name}': isolation_success must be in [0,1]")
        _check(0.0 <= self.legacy_fraction <= 1.0,
               f"profile '{name}': legacy_fraction must be in [0,1]")
        _check(self.base_segmentation in {s.value for s in SegmentationLevel},
               f"profile '{name}': unknown segmentation "
               f"'{self.base_segmentation}'")
        _check(self.backup_strategy in {b.value for b in BackupStrategy},
               f"profile '{name}': unknown backup strategy "
               f"'{self.backup_strategy}'")
        _check(self.budget >= 0, f"profile '{name}': budget must be >= 0")
        _check(self.complexity_factor > 0,
               f"profile '{name}': complexity_factor must be > 0")


@dataclass
class NetworkSpec:
    """Synthetic topology parameters (documented in docs/assumptions.md)."""

    # Fraction of facility nodes assigned to each zone (must sum to ~1).
    zone_proportions: dict[str, float] = field(default_factory=lambda: {
        "WORKSTATION": 0.40, "EHR": 0.08, "LAB": 0.06, "PHARMACY": 0.05,
        "IMAGING": 0.06, "MEDICAL_DEVICE": 0.15, "ADMIN": 0.08,
        "IDENTITY": 0.04, "BACKUP": 0.04, "INTERNET_FACING": 0.04,
    })
    min_nodes_per_zone: int = 2
    intra_zone_degree: float = 3.0      # mean intra-zone out-degree
    cross_zone_out_degree: float = 2.0  # mean cross-zone out-degree per node
    vuln_range: tuple[float, float] = (0.2, 0.7)       # standard nodes
    legacy_vuln_range: tuple[float, float] = (0.7, 0.95)  # legacy nodes
    # P(admin privilege) outside the ADMIN/IDENTITY zones.
    admin_fraction_other_zones: float = 0.03
    # Success-probability multipliers by source privilege (all <= 1).
    privilege_modifiers: dict[str, float] = field(default_factory=lambda: {
        "LOW": 0.55, "STANDARD": 0.80, "ADMIN": 1.00,
    })
    # Edge access strength for permitted cross-zone edges, by architecture.
    segmentation_modifiers: dict[str, float] = field(default_factory=lambda: {
        "flat": 1.00, "basic": 0.50, "least_privilege": 0.25,
    })
    # Extra restriction multiplier for edges INTO identity/backup zones
    # under least-privilege segmentation.
    sensitive_zone_modifier: float = 0.60
    # Traversal multiplier for edges into the backup zone by strategy.
    backup_traversal: dict[str, float] = field(default_factory=lambda: {
        "connected": 1.0, "periodic": 0.30, "isolated": 0.0,
    })
    # Per-step detection-probability multiplier for hard-to-monitor nodes.
    device_detect_capability: float = 0.5
    legacy_detect_capability: float = 0.7
    vendor_gateway_count: int = 1

    def validate(self) -> None:
        total = sum(self.zone_proportions.values())
        _check(abs(total - 1.0) < 0.02,
               f"zone_proportions must sum to ~1.0 (got {total:.3f})")
        for key in ("flat", "basic", "least_privilege"):
            _check(0.0 <= self.segmentation_modifiers[key] <= 1.0,
                   "segmentation modifiers must be in [0,1]")
        for key, v in self.privilege_modifiers.items():
            _check(0.0 <= v <= 1.0,
                   f"privilege modifier {key} must be in [0,1]")
        for key, v in self.backup_traversal.items():
            _check(0.0 <= v <= 1.0,
                   f"backup traversal {key} must be in [0,1]")
        lo, hi = self.vuln_range
        _check(0.0 <= lo <= hi <= 1.0, "vuln_range must be within [0,1]")
        lo, hi = self.legacy_vuln_range
        _check(0.0 <= lo <= hi <= 1.0, "legacy_vuln_range must be in [0,1]")


@dataclass
class SimulationSpec:
    """Dynamics of the abstract compromise/response process."""

    max_steps: int = 192            # horizon; 192 x 15 min = 48 modeled hours
    step_minutes: int = 15          # interpretation of one step (assumption)
    base_spread_rate: float = 0.35  # per-edge, per-step baseline
    patch_effectiveness: float = 0.85  # patched target multiplier = 1 - this
    detection_model: str = "geometric"  # 'geometric' | 'fixed'
    false_positive_rate: float = 0.002  # per healthy node per step
    false_positive_duration: int = 8    # steps an FP isolation lasts
    # Per-step success used by rapid-isolation portfolios. Keeping this in
    # configuration makes time-step convergence tests auditable.
    rapid_isolation_success: float = 0.95
    # Optional proportional improvement used by clock-time configurations.
    # ``None`` preserves the archived discrete detection ladder exactly.
    detection_improvement_factor: float | None = None
    identity_breach_multiplier: float = 1.5  # spread boost if identity falls
    restore_rate_fraction: float = 0.02  # nodes restored/step as fraction of n
    restore_rate_min: float = 1.0
    restore_duration: int = 2           # steps a node spends RESTORING
    no_backup_restore_penalty: float = 0.25  # rate multiplier w/o backups
    service_functional_fraction: float = 0.60  # supporting-node threshold
    catastrophic_service_steps: int = 8  # continuous clinical outage > this
    early_stop: bool = True

    def validate(self) -> None:
        _check(self.max_steps >= 1, "max_steps must be >= 1")
        _check(0.0 <= self.base_spread_rate <= 1.0,
               "base_spread_rate must be in [0,1]")
        _check(0.0 <= self.patch_effectiveness <= 1.0,
               "patch_effectiveness must be in [0,1]")
        _check(self.detection_model in ("geometric", "fixed"),
               "detection_model must be 'geometric' or 'fixed'")
        _check(0.0 <= self.false_positive_rate <= 1.0,
               "false_positive_rate must be in [0,1]")
        _check(0.0 <= self.rapid_isolation_success <= 1.0,
               "rapid_isolation_success must be in [0,1]")
        _check(self.detection_improvement_factor is None or
               0.0 < self.detection_improvement_factor <= 1.0,
               "detection_improvement_factor must be in (0,1] or null")
        _check(self.identity_breach_multiplier >= 1.0,
               "identity_breach_multiplier must be >= 1")
        _check(0.0 < self.service_functional_fraction <= 1.0,
               "service_functional_fraction must be in (0,1]")
        _check(self.catastrophic_service_steps >= 1,
               "catastrophic_service_steps must be >= 1")


@dataclass
class ExperimentSpec:
    """Main factorial Monte Carlo experiment."""

    facilities: list[str] = field(default_factory=lambda: [
        "small_clinic", "regional_hospital", "large_hospital"])
    profiles: list[str] = field(default_factory=lambda: [
        "resource_constrained", "intermediate_capacity", "high_capacity"])
    portfolios: list[str] = field(default_factory=list)  # names in defenses.py
    entry_points: list[str] = field(default_factory=lambda: [
        e.value for e in EntryPoint])
    trials_per_cell: int = 4
    workers: int = 0  # 0 = auto (cpu count)

    def validate(self) -> None:
        _check(self.trials_per_cell >= 1, "trials_per_cell must be >= 1")
        # Entry points are cycled with `entries[k % len(entries)]`, so an
        # empty list is a ZeroDivisionError later rather than a clear error.
        _check(len(self.entry_points) > 0,
               "experiment.entry_points must not be empty")
        _check(len(self.facilities) > 0,
               "experiment.facilities must not be empty")
        _check(len(self.profiles) > 0,
               "experiment.profiles must not be empty")
        valid_entries = {e.value for e in EntryPoint}
        for e in self.entry_points:
            _check(e in valid_entries, f"unknown entry point '{e}'")


@dataclass
class SweepSpec:
    """Patch-coverage x detection-delay grid (Figure 3)."""

    enabled: bool = True
    facility: str = "regional_hospital"
    profile: str = "intermediate_capacity"
    patch_levels: list[float] = field(
        default_factory=lambda: [0.25, 0.50, 0.75, 0.90])
    detection_delays: list[int] = field(
        default_factory=lambda: [1, 3, 6, 12, 24])
    trials_per_cell: int = 10

    def validate(self) -> None:
        _check(self.trials_per_cell >= 1, "sweep.trials_per_cell must be >= 1")
        _check(len(self.patch_levels) > 0,
               "sweep.patch_levels must not be empty")
        _check(len(self.detection_delays) > 0,
               "sweep.detection_delays must not be empty")
        for p in self.patch_levels:
            _check(0.0 <= p <= 1.0, "patch levels must be in [0,1]")
        for d in self.detection_delays:
            _check(d >= 1, "detection delays must be >= 1")


@dataclass
class OptimizationSpec:
    """Budget-constrained defense-portfolio search."""

    enabled: bool = True
    facility: str = "regional_hospital"
    profiles: list[str] = field(default_factory=lambda: [
        "resource_constrained", "intermediate_capacity", "high_capacity"])
    budgets: list[int] = field(default_factory=lambda: [5, 10, 15])
    trials_per_portfolio: int = 10
    cost_scale_factors: list[float] = field(
        default_factory=lambda: [0.50, 0.75, 1.00, 1.25, 1.50])
    catastrophic_target: float = 0.05  # for 'minimum budget to reach' metric

    def validate(self) -> None:
        _check(len(self.budgets) > 0, "optimization.budgets must not be empty")
        for b in self.budgets:
            _check(b >= 0, "budgets must be >= 0")
        _check(self.trials_per_portfolio >= 1,
               "trials_per_portfolio must be >= 1")
        _check(len(self.profiles) > 0,
               "optimization.profiles must not be empty")
        _check(0.0 <= self.catastrophic_target <= 1.0,
               "optimization.catastrophic_target must be a probability "
               "in [0,1]")
        _check(len(self.cost_scale_factors) > 0,
               "optimization.cost_scale_factors must not be empty")
        for s in self.cost_scale_factors:
            _check(s > 0, "cost_scale_factors must be > 0")


@dataclass
class OutputSpec:
    raw_dir: str = "data/raw"
    processed_dir: str = "data/processed"
    figures_dir: str = "outputs/figures"
    tables_dir: str = "outputs/tables"
    logs_dir: str = "outputs/logs"


@dataclass
class ServiceWeights:
    """Criticality weight of each service in weighted service-hours."""

    ehr: float = 1.0
    laboratory: float = 0.8
    pharmacy: float = 0.9
    imaging: float = 0.7
    scheduling: float = 0.4
    identity: float = 0.9
    backup_recovery: float = 0.6

    def as_dict(self) -> dict[str, float]:
        return {
            "ehr": self.ehr, "laboratory": self.laboratory,
            "pharmacy": self.pharmacy, "imaging": self.imaging,
            "scheduling": self.scheduling, "identity": self.identity,
            "backup_recovery": self.backup_recovery,
        }


# --------------------------------------------------------------------------
# Top-level config
# --------------------------------------------------------------------------

@dataclass
class Config:
    mode: str = "quick"
    seed: int = 20260713
    facilities: dict[str, FacilitySpec] = field(default_factory=lambda: {
        "small_clinic": FacilitySpec(40, 60),
        "regional_hospital": FacilitySpec(200, 300),
        "large_hospital": FacilitySpec(750, 1000),
    })
    profiles: dict[str, ProfileSpec] = field(default_factory=lambda: {
        "resource_constrained": ProfileSpec(
            patch_coverage=0.25, detection_delay_steps=24,
            isolation_success=0.50, legacy_fraction=0.35,
            base_segmentation="flat", backup_strategy="connected",
            budget=5, complexity_factor=1.0),
        "intermediate_capacity": ProfileSpec(
            patch_coverage=0.50, detection_delay_steps=12,
            isolation_success=0.70, legacy_fraction=0.15,
            base_segmentation="basic", backup_strategy="periodic",
            budget=10, complexity_factor=1.1),
        "high_capacity": ProfileSpec(
            patch_coverage=0.75, detection_delay_steps=3,
            isolation_success=0.90, legacy_fraction=0.05,
            base_segmentation="least_privilege", backup_strategy="isolated",
            budget=15, complexity_factor=1.25),
    })
    network: NetworkSpec = field(default_factory=NetworkSpec)
    simulation: SimulationSpec = field(default_factory=SimulationSpec)
    experiment: ExperimentSpec = field(default_factory=ExperimentSpec)
    sweep: SweepSpec = field(default_factory=SweepSpec)
    optimization: OptimizationSpec = field(default_factory=OptimizationSpec)
    output: OutputSpec = field(default_factory=OutputSpec)
    service_weights: ServiceWeights = field(default_factory=ServiceWeights)

    def validate(self) -> None:
        for name, fac in self.facilities.items():
            fac.validate(name)
        for name, prof in self.profiles.items():
            prof.validate(name)
        self.network.validate()
        self.simulation.validate()
        self.experiment.validate()
        self.sweep.validate()
        self.optimization.validate()
        for name in self.experiment.profiles:
            _check(name in self.profiles,
                   f"experiment references unknown profile '{name}'")
        for name in self.experiment.facilities:
            _check(name in self.facilities,
                   f"experiment references unknown facility '{name}'")
        # The sweep and optimizer index into profiles/facilities by name; an
        # unknown name is a KeyError deep in a worker process rather than a
        # readable config error here.
        _check(self.sweep.profile in self.profiles,
               f"sweep references unknown profile '{self.sweep.profile}'")
        _check(self.sweep.facility in self.facilities,
               f"sweep references unknown facility '{self.sweep.facility}'")
        _check(self.optimization.facility in self.facilities,
               f"optimization references unknown facility "
               f"'{self.optimization.facility}'")
        for name in self.optimization.profiles:
            _check(name in self.profiles,
                   f"optimization references unknown profile '{name}'")
        for name in self.experiment.portfolios:
            from .defenses import PORTFOLIO_CATALOG
            _check(name in PORTFOLIO_CATALOG,
                   f"experiment references unknown portfolio '{name}'")


def _update_dataclass(obj: Any, values: dict[str, Any], where: str) -> None:
    """Overwrite dataclass fields from a dict, rejecting unknown keys."""
    for key, val in values.items():
        if not hasattr(obj, key):
            raise ConfigError(f"unknown key '{key}' in section '{where}'")
        current = getattr(obj, key)
        if isinstance(current, tuple) and isinstance(val, list):
            val = tuple(val)
        setattr(obj, key, val)


def load_config(path: str | Path) -> Config:
    """Load a YAML config file into a validated :class:`Config`."""
    path = Path(path)
    if not path.exists():
        raise ConfigError(f"config file not found: {path}")
    with open(path, "r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}

    cfg = Config()
    cfg.mode = raw.get("mode", cfg.mode)
    cfg.seed = int(raw.get("seed", cfg.seed))

    if "facilities" in raw:
        cfg.facilities = {
            name: FacilitySpec(**vals) for name, vals in
            raw["facilities"].items()
        }
    if "profiles" in raw:
        cfg.profiles = {
            name: ProfileSpec(**vals) for name, vals in
            raw["profiles"].items()
        }
    for section, attr in (
        ("network", cfg.network), ("simulation", cfg.simulation),
        ("experiment", cfg.experiment), ("sweep", cfg.sweep),
        ("optimization", cfg.optimization), ("output", cfg.output),
        ("service_weights", cfg.service_weights),
    ):
        if section in raw:
            _update_dataclass(attr, raw[section], section)

    cfg.validate()
    return cfg


def load_defense_costs(path: str | Path) -> dict[str, float]:
    """Load the abstract defense-cost table (normalized points, NOT dollars)."""
    with open(path, "r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)
    costs = raw.get("costs", raw)
    required = {
        "basic_segmentation", "least_privilege_segmentation",
        "patch_level_upgrade", "detection_improvement",
        "rapid_isolation", "protected_backups", "identity_controls",
    }
    missing = required - set(costs)
    if missing:
        raise ConfigError(f"defense cost file missing keys: {sorted(missing)}")
    for key, val in costs.items():
        if not isinstance(val, (int, float)) or val < 0:
            raise ConfigError(f"defense cost '{key}' must be a number >= 0")
    return {k: float(v) for k, v in costs.items()}


def default_config() -> Config:
    """A small, valid in-memory config used by unit tests."""
    cfg = Config()
    cfg.validate()
    return cfg
