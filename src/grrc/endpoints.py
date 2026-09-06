"""Central registry of study endpoints — the single source of truth.

Every outcome reported in a table, plotted in a figure, used as an
optimization objective, or described in the manuscript is defined *exactly
once* in this module. Analysis code, the manuscript claim audit, and the
figure captions all read their definitions from :data:`ENDPOINTS`, so a
definition cannot drift between the prose and the implementation without a
test failing.

Why this module exists
----------------------
The WP0 audit (``audit/baseline_forensic_report.md``, ISSUE-001) found that
the manuscript defined the sustained-outage endpoint as "more than two
modeled hours of continuous unavailability in at least four clinical
services" while :mod:`grrc.propagation` computed ``any()`` over a
four-member clinical set — that is, *k* = 1 where the prose said *k* = 4.
The endpoint was one of six Pareto objectives, so the inversion propagated
into the frontier, the finalist rule, and every reported outage percentage.
Nothing in a 70-test suite caught it, because no test asserted the
manuscript's definition of anything.

Two structural rules follow from that failure and are enforced here:

1. **One definition, read by everyone.** The prose in
   :attr:`EndpointSpec.definition` is the text that must appear in the
   manuscript. ``tests/test_endpoint_registry.py`` checks that the
   manuscript's endpoint table matches this registry verbatim.

2. **Every endpoint is recomputable from committed raw output.**
   :attr:`EndpointSpec.computed_from` names the raw columns an external
   auditor needs. A reviewer must never have to rerun 50,000 simulations to
   check an endpoint, and must be able to recompute it at parameter values
   the authors did not choose.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from .enums import CLINICAL_SERVICES, Service

#: Identification class for a reported quantity. Used by the manuscript and
#: by ``study/PUBLIC_EVIDENCE_PARAMETER_REGISTER.csv`` so that no quantity is
#: reported without stating what kind of thing it is.
IDENTIFICATION_CLASSES: tuple[str, ...] = (
    # Constrained by matched public evidence on a matching population.
    "evidence-constrained",
    # An observable output compared against a frozen external benchmark.
    "externally-validated",
    # A declared modeling choice; no evidence claim is made.
    "declared-assumption",
    # A model-internal quantity with no real-world referent.
    "model-internal",
    # Normalized scenario units; explicitly not dollars, staff time, or risk.
    "normalized-scenario-unit",
)


@dataclass(frozen=True)
class EndpointSpec:
    """A single reported outcome, defined once."""

    #: Stable machine identifier. Also the column/objective name.
    id: str
    #: Short label for tables and axes.
    display_name: str
    #: The exact definition sentence. This text must appear in the
    #: manuscript's endpoint table; the claim audit checks it verbatim.
    definition: str
    #: Measurement units, or the word describing the quantity.
    units: str
    #: ``"minimize"`` for Pareto objectives, ``None`` for diagnostics.
    direction: str | None
    #: What a reader must not conclude from this number.
    interpretation_boundary: str
    #: Raw output columns sufficient to recompute the endpoint offline.
    computed_from: tuple[str, ...]
    #: One of :data:`IDENTIFICATION_CLASSES`.
    identification: str
    #: Free-text rationale for any threshold or arbitrary constant.
    threshold_rationale: str = ""

    def __post_init__(self) -> None:
        if self.identification not in IDENTIFICATION_CLASSES:
            raise ValueError(
                f"endpoint '{self.id}' has unknown identification class "
                f"'{self.identification}'; expected one of "
                f"{IDENTIFICATION_CLASSES}")
        if self.direction not in (None, "minimize", "maximize"):
            raise ValueError(
                f"endpoint '{self.id}' has invalid direction "
                f"'{self.direction}'")
        if not self.definition.strip():
            raise ValueError(f"endpoint '{self.id}' has an empty definition")


# ---------------------------------------------------------------------------
# Sustained clinical outage
# ---------------------------------------------------------------------------
# The endpoint formerly named "catastrophic". The rename is deliberate: the
# handoff and the calibration memorandum both prohibit calling a
# mathematically chosen threshold a clinical catastrophe threshold, because no
# clinical validation of the 60% service-functional fraction, the two-hour
# duration, or the service count has been performed. The endpoint is a model
# indicator of multi-service clinical disruption and is named as one.

#: Number of clinical services that must each sustain a qualifying outage.
#: Declared in config as ``simulation.sustained_outage_min_services``.
DEFAULT_SUSTAINED_OUTAGE_MIN_SERVICES: int = 4

#: The full sensitivity ladder reported alongside the primary value. Every
#: results table carries all of these, so a reader who disagrees with the
#: primary *k* can read their own number off the same table.
SUSTAINED_OUTAGE_K_LADDER: tuple[int, ...] = tuple(
    range(1, len(CLINICAL_SERVICES) + 1))


def sustained_outage_column(k: int) -> str:
    """Raw/summary column name for the *k*-of-n sustained-outage indicator."""
    if not 1 <= k <= len(CLINICAL_SERVICES):
        raise ValueError(
            f"k must be in 1..{len(CLINICAL_SERVICES)}; got {k}")
    return f"sustained_clinical_outage_k{k}"


def max_streak_column(service: Service) -> str:
    """Raw column holding a service's longest continuous outage, in steps."""
    return f"{service.value}_max_outage_streak_steps"


def sustained_clinical_outage(
        max_streak_steps: Mapping[Service, int],
        threshold_steps: int,
        min_services: int,
        clinical_services: Sequence[Service] = CLINICAL_SERVICES,
) -> bool:
    """Return whether a trial met the sustained clinical-outage endpoint.

    The endpoint is true when **at least** ``min_services`` of the clinical
    services each experienced a continuous unavailability run **strictly
    longer than** ``threshold_steps`` steps at some point in the horizon.

    Two properties of this definition are deliberate and must be stated
    wherever the endpoint is reported:

    * The comparison is strict (``>``), so ``threshold_steps`` is the longest
      outage that does *not* qualify. This matches the manuscript's "more
      than two modeled hours".
    * The runs are **not required to be concurrent**. Each service is scored
      on its own longest outage over the whole horizon. A trial in which the
      laboratory is down for three hours in the morning and pharmacy for
      three hours in the evening qualifies at *k* = 2. This is the weaker of
      the two readings; a concurrency requirement would need per-step service
      states retained for every trial, which the raw schema does not carry.

    :param max_streak_steps: longest continuous outage per service, in steps.
    :param threshold_steps: qualifying duration; runs must exceed it.
    :param min_services: the *k* in *k*-of-n.
    :param clinical_services: the *n*; defaults to the four clinical services.
    """
    n = len(clinical_services)
    if not 1 <= min_services <= n:
        raise ValueError(
            f"min_services must be in 1..{n}; got {min_services}")
    if threshold_steps < 1:
        raise ValueError(
            f"threshold_steps must be >= 1; got {threshold_steps}")
    missing = [s for s in clinical_services if s not in max_streak_steps]
    if missing:
        raise ValueError(
            f"max_streak_steps is missing clinical services: "
            f"{[s.value for s in missing]}")
    qualifying = sum(
        1 for s in clinical_services
        if max_streak_steps[s] > threshold_steps)
    return qualifying >= min_services


def sustained_outage_ladder(
        max_streak_steps: Mapping[Service, int],
        threshold_steps: int,
        clinical_services: Sequence[Service] = CLINICAL_SERVICES,
) -> dict[int, bool]:
    """Evaluate the endpoint at every *k*, for prespecified sensitivity.

    Returned indicators are monotone non-increasing in *k* by construction,
    which ``tests/test_endpoint_registry.py`` asserts as an invariant.
    """
    return {
        k: sustained_clinical_outage(
            max_streak_steps, threshold_steps, k, clinical_services)
        for k in range(1, len(clinical_services) + 1)
    }


# ---------------------------------------------------------------------------
# The registry
# ---------------------------------------------------------------------------

_CLINICAL_NAMES = ", ".join(s.value for s in CLINICAL_SERVICES)

ENDPOINTS: dict[str, EndpointSpec] = {spec.id: spec for spec in (
    EndpointSpec(
        id="mean_hours_lost",
        display_name="Mean disruption",
        definition=(
            "Mean weighted service-hours lost across the seven modeled "
            "services, where each service is binary at each step and is "
            "weighted by its declared service weight."),
        units="weighted service-hours",
        direction="minimize",
        interpretation_boundary=(
            "Expected service unavailability within the synthetic model. Not "
            "patient harm, not degraded-capacity operation, and not an "
            "estimate for any real hospital."),
        computed_from=("weighted_service_hours_lost",),
        identification="model-internal",
    ),
    EndpointSpec(
        id="tail_hours_lost_cvar90",
        display_name="Tail disruption (CVaR90)",
        definition=(
            "Conditional mean weighted service-hours lost among trials at or "
            "above the empirical 90th percentile of weighted service-hours "
            "lost."),
        units="weighted service-hours",
        direction="minimize",
        interpretation_boundary=(
            "Severity of the worst simulated decile under the model's own "
            "scenario bank. Not a probable-maximum-loss estimate."),
        computed_from=("weighted_service_hours_lost",),
        identification="model-internal",
    ),
    EndpointSpec(
        id="sustained_outage_probability",
        display_name="Sustained clinical outage",
        definition=(
            "Fraction of trials in which at least k of the four clinical "
            f"services ({_CLINICAL_NAMES}) each experienced a continuous "
            "unavailability run of more than two modeled hours, with the "
            "primary analysis fixing k = 4 and every results table also "
            "reporting k = 1, 2, and 3."),
        units="probability",
        direction="minimize",
        interpretation_boundary=(
            "A model indicator of multi-service clinical disruption. It is "
            "not an incident probability, not a clinical catastrophe "
            "threshold, and it has received no clinical validation. The "
            "qualifying runs need not be concurrent."),
        computed_from=tuple(
            max_streak_column(s) for s in CLINICAL_SERVICES),
        identification="declared-assumption",
        threshold_rationale=(
            "k = 4 restores the definition the manuscript always stated: "
            "more than two modeled hours of continuous unavailability in at "
            "least four clinical services, which, because the clinical set "
            "has exactly four members, means all four. The implementation "
            "used any() — k = 1 — and the discrepancy propagated into six "
            "objectives (audit ISSUE-001).\n\n"
            "An earlier draft of this registry set the primary k to 2 on the "
            "grounds that k = 1 would saturate and k = 4 would be too rare to "
            "estimate. The rebuilt discovery bank does not support that "
            "reasoning and it was withdrawn. A later interpretation audit "
            "also rejected the claim that changing k has uniformly small "
            "effects. Frequency differences must be reported by stage and "
            "profile; pooled partial-service frequencies cannot establish "
            "profile-specific insensitivity. See data/interpretation and "
            "study/INTERPRETATION_ANALYSIS_PLAN.md.\n\n"
            "The primary k remains a declared construct choice: a "
            "trial counts as a sustained clinical outage only when the "
            "whole modeled clinical estate — EHR, laboratory, pharmacy and "
            "imaging — was each down for more than two hours. This does "
            "not make the threshold clinically validated.\n\n"
            "Binary per-step service availability over a shared network "
            "can concentrate mass at extreme service counts, "
            "whereas real incidents show partial and degraded operation. "
            "This limits what the endpoint can represent regardless of k, "
            "and is separate from sensitivity to k. Because the "
            "full ladder is reported everywhere, a reader who prefers a "
            "different k reads it off the same table."),    ),
    EndpointSpec(
        id="nonrecovery_probability",
        display_name="Non-recovery at horizon",
        definition=(
            "Fraction of trials in which weighted clinical service "
            "availability had not returned to full at the final simulated "
            "step of the declared horizon."),
        units="probability",
        direction="minimize",
        interpretation_boundary=(
            "Right-censored *technical* recovery of modeled services within "
            "the horizon. It is not organizational recovery, not return to "
            "normal clinical operations, and it is bounded by the horizon: a "
            "72-hour horizon cannot express the weeks-to-months recovery tail "
            "documented in the public incident record."),
        computed_from=("recovered_within_horizon", "recovery_step",
                       "horizon_steps"),
        identification="model-internal",
    ),
    EndpointSpec(
        id="implementation_cost_points",
        display_name="Implementation cost",
        definition=(
            "Sum of declared control cost points for the increment a "
            "portfolio adds to its profile's exogenous baseline posture."),
        units="normalized scenario points",
        direction="minimize",
        interpretation_boundary=(
            "A relative scenario weight. Not dollars, not procurement "
            "evidence, and not comparable across studies."),
        computed_from=("profile", "portfolio"),
        identification="normalized-scenario-unit",
    ),
    EndpointSpec(
        id="operational_burden_points",
        display_name="Operational burden",
        definition=(
            "Sum of declared workflow and implementation burden points for "
            "the increment a portfolio adds to its profile's exogenous "
            "baseline posture."),
        units="normalized scenario points",
        direction="minimize",
        interpretation_boundary=(
            "A declared scenario preference. Not measured staff time, alert "
            "volume, or clinical workflow impact."),
        computed_from=("profile", "portfolio"),
        identification="normalized-scenario-unit",
    ),
    EndpointSpec(
        id="mean_defensive_isolation_hours_per_node",
        display_name="Defensive isolation burden",
        definition=(
            "Mean node-hours per node spent isolated while not compromised, "
            "including false-positive isolations."),
        units="node-hours per node",
        direction=None,
        interpretation_boundary=(
            "A diagnostic for over-isolation within the model. Reported but "
            "not used as a Pareto dimension, and not a measure of clinical "
            "workflow disruption."),
        computed_from=("defensive_isolation_node_steps", "step_minutes",
                       "n_nodes"),
        identification="model-internal",
    ),
)}

#: Objectives of the multi-objective decision analysis, in reporting order.
#: All are minimized. Read by :mod:`grrc.multiobjective` so the objective set
#: and the registry cannot disagree.
PARETO_OBJECTIVES: tuple[str, ...] = tuple(
    spec.id for spec in ENDPOINTS.values() if spec.direction == "minimize")


def endpoint(endpoint_id: str) -> EndpointSpec:
    """Look up an endpoint, with a helpful error for typos."""
    try:
        return ENDPOINTS[endpoint_id]
    except KeyError:
        raise KeyError(
            f"unknown endpoint '{endpoint_id}'; registered: "
            f"{sorted(ENDPOINTS)}") from None


def objective_directions() -> dict[str, str]:
    """Map each Pareto objective to its optimization direction."""
    return {name: ENDPOINTS[name].direction for name in PARETO_OBJECTIVES}
