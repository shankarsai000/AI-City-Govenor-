"""
City State domain models — the digital twin schema.

Each domain (traffic, power, water, emergency) has a typed Pydantic model
representing its current physical state. These models serve three purposes:

1. Schema validation: Mutations are validated against the model before apply
2. Serialization: JSON round-trip to/from Redis (hot cache) and PostgreSQL (cold audit)
3. Documentation: The model IS the specification of what "city state" means

Design decision: Pydantic v2 models with strict defaults representing
"normal operations" — the system initializes into a safe baseline without
requiring seed data from an external source.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    """Consistent UTC timestamp factory for all state metadata."""
    return datetime.now(timezone.utc)


class VersionedDomainState(BaseModel):
    """Shared synchronization metadata for every infrastructure domain."""
    version: int = Field(default=0, description="Domain state version counter")
    updated_at: datetime = Field(
        default_factory=utc_now,
        description="Timestamp of the last successful mutation for this domain",
    )


# ── Traffic Domain ───────────────────────────────────────────────────────────

class IntersectionState(BaseModel):
    """State of a single traffic intersection."""
    intersection_id: str
    signal_phase: Literal["green_ns", "green_ew", "yellow", "red_all", "flashing"] = "green_ns"
    pedestrian_active: bool = False
    emergency_preempt: bool = False


class TrafficState(VersionedDomainState):
    """Complete traffic domain state."""
    intersections: dict[str, IntersectionState] = Field(
        default_factory=lambda: {
            f"INT-{i:03d}": IntersectionState(intersection_id=f"INT-{i:03d}")
            for i in range(1, 13)  # 12 intersections
        },
        description="Map of intersection_id → signal state",
    )
    congestion_level: float = Field(
        default=0.15,
        ge=0.0,
        le=1.0,
        description="City-wide congestion index (0=empty, 1=gridlock)",
    )
    active_corridors: list[str] = Field(
        default_factory=list,
        description="Currently activated emergency corridors",
    )
    closed_roads: list[str] = Field(
        default_factory=list,
        description="Roads currently closed to traffic",
    )
    active_reroutes: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Active traffic reroute directives",
    )
# ── Power Domain ─────────────────────────────────────────────────────────────

class SubstationState(BaseModel):
    """State of a single power substation."""
    substation_id: str
    status: Literal["online", "offline", "maintenance", "overloaded"] = "online"
    load_mw: float = 0.0
    capacity_mw: float = 50.0


class PowerState(VersionedDomainState):
    """Complete power grid domain state."""
    grid_load_mw: float = Field(
        default=120.0,
        ge=0.0,
        description="Current total grid load in megawatts",
    )
    capacity_mw: float = Field(
        default=200.0,
        ge=0.0,
        description="Total grid capacity in megawatts",
    )
    substations: dict[str, SubstationState] = Field(
        default_factory=lambda: {
            f"SUB-{c}": SubstationState(
                substation_id=f"SUB-{c}",
                load_mw=30.0,
                capacity_mw=50.0,
            )
            for c in ["NORTH", "SOUTH", "EAST", "WEST"]
        },
        description="Map of substation_id → substation state",
    )
    active_shedding: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Active load-shedding operations (zone, percentage)",
    )
    blackout_zones: list[str] = Field(
        default_factory=list,
        description="Zones currently experiencing blackout",
    )
# ── Water Domain ─────────────────────────────────────────────────────────────

class PumpState(BaseModel):
    """State of a single water pump."""
    pump_id: str
    status: Literal["running", "stopped", "maintenance", "failed"] = "running"
    flow_rate_lpm: float = 500.0  # liters per minute


class WaterState(VersionedDomainState):
    """Complete water system domain state."""
    pressure_psi: float = Field(
        default=65.0,
        ge=0.0,
        description="System-wide water pressure in PSI",
    )
    treatment_status: Literal["normal", "elevated", "emergency", "offline"] = "normal"
    active_isolations: list[str] = Field(
        default_factory=list,
        description="Zone IDs currently isolated from the water grid",
    )
    pumps: dict[str, PumpState] = Field(
        default_factory=lambda: {
            f"PUMP-{i:02d}": PumpState(pump_id=f"PUMP-{i:02d}")
            for i in range(1, 7)  # 6 pumps
        },
        description="Map of pump_id → pump state",
    )
    leak_zones: list[str] = Field(
        default_factory=list,
        description="Zones with detected water leaks",
    )
# ── Emergency Domain ─────────────────────────────────────────────────────────

class IncidentRecord(BaseModel):
    """An active emergency incident."""
    incident_id: str
    incident_type: Literal["fire", "flood", "earthquake", "hazmat", "civil", "medical"] = "fire"
    location: str = "Unknown"
    severity: Literal["low", "medium", "high", "critical"] = "medium"
    status: Literal["active", "contained", "resolved"] = "active"


class DispatchedUnit(BaseModel):
    """A dispatched emergency response unit."""
    unit_id: str
    unit_type: Literal["fire", "police", "ambulance", "hazmat"] = "fire"
    location: str = "Unknown"
    status: Literal["dispatched", "en_route", "on_scene", "returning"] = "dispatched"


class EmergencyState(VersionedDomainState):
    """Complete emergency management domain state."""
    alert_level: Literal["green", "yellow", "orange", "red"] = "green"
    active_incidents: list[IncidentRecord] = Field(
        default_factory=list,
        description="Currently active emergency incidents",
    )
    dispatched_units: list[DispatchedUnit] = Field(
        default_factory=list,
        description="Emergency units currently deployed",
    )
    declared_emergencies: list[str] = Field(
        default_factory=list,
        description="Formally declared emergency identifiers",
    )
# ── Composite City State ─────────────────────────────────────────────────────

class CityState(BaseModel):
    """
    Complete city state — the digital twin.
    Wraps all four domain states into a single queryable snapshot.
    """
    traffic: TrafficState = Field(default_factory=TrafficState)
    power: PowerState = Field(default_factory=PowerState)
    water: WaterState = Field(default_factory=WaterState)
    emergency: EmergencyState = Field(default_factory=EmergencyState)
    version: int = Field(default=0, description="Monotonically increasing version counter")
    updated_at: datetime = Field(
        default_factory=utc_now,
        description="Timestamp of last state mutation",
    )


class CityStateSyncStatus(BaseModel):
    """Synchronization metadata for the composite city digital twin."""
    global_version: int = Field(
        default=0,
        description="Monotonically increasing global city-state version",
    )
    updated_at: datetime = Field(
        default_factory=utc_now,
        description="Timestamp of the latest successful mutation across all domains",
    )
    domain_versions: dict[str, int] = Field(
        default_factory=lambda: {
            "traffic": 0,
            "power": 0,
            "water": 0,
            "emergency": 0,
        },
        description="Latest version number tracked per domain",
    )
    active_locks: dict[str, dict[str, Any]] = Field(
        default_factory=dict,
        description="Currently active resource locks visible to operators",
    )


# ── Mutation Descriptor ──────────────────────────────────────────────────────

class StateMutation(BaseModel):
    """
    Describes a proposed change to city state.
    Created by the mutation registry from an action_type + payload.
    """
    domain: Literal["traffic", "power", "water", "emergency"]
    action_type: str
    description: str
    payload: dict[str, Any] = Field(default_factory=dict)
    # Resources this mutation touches (for lock acquisition)
    affected_resources: list[str] = Field(default_factory=list)


class Conflict(BaseModel):
    """A detected conflict between a proposed mutation and current state."""
    severity: Literal["low", "medium", "high", "critical"]
    description: str
    conflicting_domain: str
    resolution_hint: str


class Resolution(BaseModel):
    """Result of conflict resolution."""
    action: Literal["proceed", "defer", "escalate", "block"]
    reason: str
    resolved_conflicts: list[Conflict] = Field(default_factory=list)


# ── Domain lookup helper ─────────────────────────────────────────────────────

DOMAIN_STATE_TYPES: dict[str, type[BaseModel]] = {
    "traffic": TrafficState,
    "power": PowerState,
    "water": WaterState,
    "emergency": EmergencyState,
}

DOMAIN_PRIORITY: dict[str, int] = {
    "emergency": 100,
    "power": 75,
    "water": 50,
    "traffic": 25,
}
