"""Enumerations shared across the GRRC simulation.

Everything here describes *abstract model categories*, not real hospital
inventory. Zone names follow common healthcare IT architecture
descriptions (see docs/assumptions.md for sources and rationale).
"""

from __future__ import annotations

from enum import Enum, IntEnum


class Zone(IntEnum):
    """Network zones of a synthetic healthcare facility (10 zones)."""

    WORKSTATION = 0       # ordinary employee / clinical workstations
    EHR = 1               # electronic health record application + databases
    LAB = 2               # laboratory information systems
    PHARMACY = 3          # pharmacy / medication management systems
    IMAGING = 4           # medical imaging (PACS-like) systems
    MEDICAL_DEVICE = 5    # connected medical & IoT devices
    ADMIN = 6             # administration, scheduling, billing
    IDENTITY = 7          # identity & authentication services
    BACKUP = 8            # backup & recovery systems
    INTERNET_FACING = 9   # patient portal, remote access, vendor gateways


class NodeState(IntEnum):
    """Abstract per-node compromise lifecycle.

    HEALTHY    - patched, functioning normally
    VULNERABLE - functioning normally but unpatched (higher susceptibility)
    COMPROMISED- abstract 'ransomware present' flag (no payload is modeled)
    DETECTED   - compromise noticed by monitoring; node still active
    ISOLATED   - disconnected by defenders; cannot spread or be reached
    RESTORING  - being rebuilt/restored from backups
    RESTORED   - returned to service
    """

    HEALTHY = 0
    VULNERABLE = 1
    COMPROMISED = 2
    DETECTED = 3
    ISOLATED = 4
    RESTORING = 5
    RESTORED = 6


class Privilege(IntEnum):
    """Access privilege tier of the account context on a node."""

    LOW = 0
    STANDARD = 1
    ADMIN = 2


class SegmentationLevel(str, Enum):
    """Network architecture / segmentation defense tiers."""

    FLAT = "flat"
    BASIC = "basic"
    LEAST_PRIVILEGE = "least_privilege"


class BackupStrategy(str, Enum):
    """How backup systems are connected to the rest of the network."""

    CONNECTED = "connected"      # always network-reachable
    PERIODIC = "periodic"        # reachable only in periodic windows
    ISOLATED = "isolated"        # offline / immutable; no network path in


class EntryPoint(str, Enum):
    """Category of the initial foothold (abstract; no real technique)."""

    WORKSTATION = "workstation"
    INTERNET_FACING = "internet_facing"
    PRIVILEGED_SYSTEM = "privileged_system"
    MEDICAL_DEVICE = "medical_device"
    VENDOR_CONNECTION = "vendor_connection"


class Service(str, Enum):
    """Modeled critical healthcare services."""

    EHR = "ehr"
    LABORATORY = "laboratory"
    PHARMACY = "pharmacy"
    IMAGING = "imaging"
    SCHEDULING = "scheduling"
    IDENTITY = "identity"
    BACKUP_RECOVERY = "backup_recovery"


#: Services whose loss directly interrupts clinical care; used for the
#: "catastrophic disruption" definition (see docs/assumptions.md A14).
CLINICAL_SERVICES: tuple[Service, ...] = (
    Service.EHR,
    Service.LABORATORY,
    Service.PHARMACY,
    Service.IMAGING,
)

#: Zone that hosts each service's supporting nodes.
SERVICE_ZONE: dict[Service, Zone] = {
    Service.EHR: Zone.EHR,
    Service.LABORATORY: Zone.LAB,
    Service.PHARMACY: Zone.PHARMACY,
    Service.IMAGING: Zone.IMAGING,
    Service.SCHEDULING: Zone.ADMIN,
    Service.IDENTITY: Zone.IDENTITY,
    Service.BACKUP_RECOVERY: Zone.BACKUP,
}
