"""Parameter uncertainty over the coefficients no public evidence identifies.

The rebuilt study classifies every quantity by what identifies it, and finds
that most of the model's internal coefficients are identified by nothing: a
per-edge transmission rate, a patch effectiveness, an isolation success
probability, a restoration throughput. Labelling those as declared
assumptions is honest, but a declared assumption held at a single point value
cannot propagate into the results. The reader is then told the number is
uncertain and shown a result computed as though it were not.

This module closes that gap. Each unidentified coefficient carries a
**prespecified range**, and one parameter vector is drawn per *scenario* --
shared by every candidate in that scenario, exactly as the topology and the
entry point are. Parameter uncertainty therefore becomes another latent
dimension of the common random numbers design: portfolio comparisons stay
matched, and reported objectives are marginal over the declared ranges rather
than conditional on a point estimate nobody can defend.

Two consequences worth stating:

* Every objective widens, because it now carries parameter uncertainty as
  well as aleatory variation. That is the honest width.
* The drawn values are written into every raw row, so an analyst can
  recompute results conditional on any parameter, or regress outcomes on the
  draws to get a variance-based sensitivity, without rerunning anything.

The ranges are declared assumptions. Where public evidence bounds a quantity
loosely it is noted in the config; where it does not, the range is wide on
purpose. A wide range that says "we do not know" is worth more than a narrow
one that implies we do.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping
from typing import Any

from .config import Config
from .utilities import event_uniform

#: Event stream reserved for parameter draws. Distinct from every stream used
#: for topology, entry, patching, or step-level events, so adding parameter
#: uncertainty cannot perturb any other draw.
PARAMETER_STREAM = 16


def _sample_range(low: float, high: float, unit: float) -> float:
    """Map a uniform variate onto a declared range."""
    return float(low) + unit * (float(high) - float(low))


def sample_parameters(cfg: Config, master_seed: int, scenario_id: int
                      ) -> dict[str, float]:
    """Draw one parameter vector for a scenario.

    Deterministic in ``(master_seed, scenario_id)``, so every candidate that
    replays this scenario sees the same parameters and the paired comparison
    stays matched. Returns an empty mapping when uncertainty is disabled, so
    a point-estimate run remains exactly reproducible.
    """
    spec = cfg.parameter_uncertainty
    if not spec.enabled:
        return {}
    names = spec.ordered_names()
    if not names:
        return {}
    units = event_uniform(master_seed, scenario_id, PARAMETER_STREAM, 0,
                          len(names))
    drawn: dict[str, float] = {}
    for index, (section, field_name, (low, high)) in enumerate(names):
        drawn[f"{section}.{field_name}"] = _sample_range(
            low, high, float(units[index]))
    return drawn


def apply_parameters(cfg: Config, drawn: Mapping[str, float]) -> Config:
    """Return a config with the drawn values substituted in.

    Uses ``dataclasses.replace`` on the two affected sub-specs rather than a
    deep copy, because this runs once per trial and a deep copy of the whole
    config would dominate the cost of a short trial.
    """
    if not drawn:
        return cfg
    updates: dict[str, dict[str, Any]] = {"simulation": {}, "network": {}}
    for key, value in drawn.items():
        section, field_name = key.split(".", 1)
        updates.setdefault(section, {})[field_name] = value

    replacements: dict[str, Any] = {}
    for section, values in updates.items():
        if not values:
            continue
        current = getattr(cfg, section)
        replacements[section] = dataclasses.replace(current, **values)
    return dataclasses.replace(cfg, **replacements) if replacements else cfg
