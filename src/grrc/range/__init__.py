"""A certified cyber-range benchmark for automated defenders.

The certificate machinery in :mod:`grrc.control_certificate` and
:mod:`grrc.hospital_attack_model` turns a security-control portfolio into a
*provable* residual-risk verdict on real MITRE ATT&CK structure. This package
wraps that as a small **cyber range**: an agent-agnostic defender API
(:class:`~grrc.range.environment.DefenseRange`) whose ``score`` returns a
distribution-free adequacy certificate rather than an empirical attack-success
rate, a set of reference **automated defenders** (:mod:`grrc.range.policies`),
and an **adaptive regime sweep** (:mod:`grrc.range.regimes`) over threat
configurations. A future agentic / LLM defender consumes the same API unchanged.

Honest scope: a first-of-kind evaluation-environment / benchmark (workshop / WIP
tier), not a new theorem and not a validated real-world defense. The hospital is
synthetic; ATT&CK and CIPHER are real; effectiveness/degradation are analyst-prior
intervals, and certificate verdicts are conditional worst-case frequencies, not
statistical confidence levels.
"""
from grrc.range.environment import DefenseRange
from grrc.range.regimes import Regime, default_regimes, effectiveness_bounds
from grrc.range import policies

__all__ = ["DefenseRange", "Regime", "default_regimes", "effectiveness_bounds", "policies"]
