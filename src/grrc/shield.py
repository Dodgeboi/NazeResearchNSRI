"""Dependency-closure shield for autonomous defenders.

A runtime monitor that sits between an autonomous defender and the network
it defends. The defender proposes a network response mode; the shield admits
it only if the mode, by itself, makes no clinical service unavailable.

Specification
-------------
Let ``A_m(s, x)`` be the availability of service ``s`` in state ``x`` under
response mode ``m``, given by the service dependency model
(:mod:`grrc.service_dependencies`, and :mod:`grrc.islanding` for modes that
sever dependencies). The shield enforces, at **every simulation step** ``t``,

    for every clinical service s:  A_connected(s, x_t) = 1  =>  A_mode(s, x_t) = 1

where ``x_t`` is the realised state at step ``t`` and ``mode`` is the mode in
force when availability is recorded. In words: the defender's network response
never makes a clinical service unavailable that would be available on the same
node states with no network response. Call a violation *self-inflicted
unavailability*.

Why this is enforceable exactly. Availability is a deterministic function of
node states and the declared dependency graph, both known to the monitor. The
monitor runs after each step's state update and before availability is
recorded (``RansomwareSimulation.step_monitor``). If the active mode would
violate the property, it is replaced by the fallback, ``connected``, which
satisfies it trivially because it is the reference. So the property holds at
every recorded step by construction. ``tests/test_shield.py`` checks it on
every step of every episode it runs, rather than trusting the construction.

What it does not guarantee
--------------------------
* **Not fewer outages overall.** It constrains what the defender's action
  does to *this* state. Blocking a cut lets the attacker keep spreading, and
  that can cause more outage later. Whether shielding helps on balance is an
  empirical question, measured on paired scenarios.
* **Nothing about undeclared dependencies.** The shield knows the dependency
  graph it is given and nothing else. A lockdown that breaks a dependency the
  graph does not declare — an application server and its database in one
  zone, say — passes. The shield is exactly as good as the dependency
  specification, which is therefore a deployment prerequisite, not a detail.
* **Nothing between steps of a coarser real system.** The guarantee is
  per simulation step of this model.
"""

from __future__ import annotations

from .agent_env import CONNECTED


class DependencyClosureShield:
    """Admits a response mode only if it causes no self-inflicted outage.

    ``admit`` screens the agent's proposal when it is made. The environment's
    per-step monitor re-checks the mode in force on every later step and falls
    back to ``fallback`` the moment the property would fail. That second check
    is what makes the guarantee hold between decisions, when the state has
    moved on since the agent chose.
    """

    fallback = CONNECTED

    def __init__(self) -> None:
        self.proposals = 0
        self.rejections = 0

    def admit(self, env, proposed: str) -> str:
        self.proposals += 1
        if env.self_inflicted(proposed):
            self.rejections += 1
            return self.fallback
        return proposed
