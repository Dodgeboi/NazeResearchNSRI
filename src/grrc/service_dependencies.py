"""Critical-service dependency model.

Damage is NOT measured by counting compromised computers alone: each
critical healthcare service depends on a group of supporting nodes, a
designated core node, and (for most services) the identity service.

A service is AVAILABLE at a time step iff
  1. its core node is functional, AND
  2. at least ``service_functional_fraction`` of its supporting nodes are
     functional, AND
  3. its identity dependency (if any) is available.

'Functional' means: not actively compromised and not isolated. This makes
defensive isolation itself a source of service disruption, creating the
security-versus-availability tradeoff studied in the paper.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from .enums import Service, SERVICE_ZONE
from .models import HospitalNetwork

#: Services that require the identity service to be available
#: (authentication dependency). Identity and backup themselves do not.
IDENTITY_DEPENDENT: frozenset[Service] = frozenset({
    Service.EHR, Service.LABORATORY, Service.PHARMACY,
    Service.IMAGING, Service.SCHEDULING,
})


def build_service_map(net: HospitalNetwork,
                      core_nodes: dict[Service, int]) -> dict[Service, dict[str, Any]]:
    """Attach the service->nodes dependency map to a generated network."""
    services: dict[Service, dict[str, Any]] = {}
    for svc, svc_zone in SERVICE_ZONE.items():
        services[svc] = {
            "nodes": net.nodes_in_zone(svc_zone),
            "core": core_nodes[svc],
            "requires_identity": svc in IDENTITY_DEPENDENT,
        }
    return services


def service_availability(net: HospitalNetwork, functional: np.ndarray,
                         threshold: float) -> dict[Service, bool]:
    """Evaluate availability of all services given per-node functionality.

    Args:
        net: the network with its service map.
        functional: boolean array, True where a node is neither actively
            compromised nor isolated.
        threshold: minimum fraction of supporting nodes that must be
            functional (``service_functional_fraction``).

    Identity is evaluated first because other services depend on it.
    Networks without a service map (hand-built unit-test graphs) simply
    report no services.
    """
    avail: dict[Service, bool] = {}
    if not net.services:
        return avail

    def base_ok(svc: Service) -> bool:
        info = net.services[svc]
        nodes = info["nodes"]
        if not functional[info["core"]]:
            return False
        frac = float(functional[nodes].mean()) if nodes.size else 0.0
        return frac >= threshold

    identity_ok = (base_ok(Service.IDENTITY)
                   if Service.IDENTITY in net.services else True)
    for svc in net.services:
        ok = base_ok(svc)
        if net.services[svc]["requires_identity"]:
            ok = ok and identity_ok
        avail[svc] = ok
    return avail
