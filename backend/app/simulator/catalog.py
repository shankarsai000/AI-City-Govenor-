from __future__ import annotations

from dataclasses import dataclass
from random import Random
from typing import Any, Callable

from app.simulator.models import SimulatorDomain, SimulatorSeverity

PayloadFactory = Callable[[Random], dict[str, Any]]
TelemetryFactory = Callable[[Random], dict[str, Any]]


TRAFFIC_ROADS = ["MAIN_ST", "RING_RD", "AIRPORT_LINK", "METRO_AVE", "TECH_CORRIDOR"]
TRAFFIC_ROUTE_PAIRS = [
    ("CBD", "Airport"),
    ("North Hub", "Tech Park"),
    ("Metro East", "Riverfront"),
    ("South Zone", "Civic Center"),
]
INTERSECTION_GROUPS = [
    ["INT-001", "INT-002", "INT-003"],
    ["INT-004", "INT-005", "INT-006"],
    ["INT-007", "INT-008", "INT-009"],
]
POWER_ZONES = ["SUB-NORTH", "SUB-SOUTH", "SUB-EAST", "SUB-WEST"]
WATER_ZONES = ["north", "south", "east", "west", "industrial"]
PUMPS = ["PUMP-01", "PUMP-02", "PUMP-03", "PUMP-04", "PUMP-05", "PUMP-06"]
INCIDENT_LOCATIONS = ["Central Market", "Metro East", "Airport Link", "Riverfront", "Old Town", "Tech Park"]
INCIDENT_TYPES = ["fire", "medical", "flood", "hazmat", "civil"]
DISPATCH_UNIT_TYPES = ["fire", "police", "ambulance", "hazmat"]


@dataclass(frozen=True)
class ScenarioTemplate:
    scenario_id: str
    domain: SimulatorDomain
    action_type: str
    source: str
    severity: SimulatorSeverity
    risk_level: SimulatorSeverity
    requires_human: bool
    weight: int
    payload_factory: PayloadFactory
    telemetry_factory: TelemetryFactory
    location_factory: Callable[[Random], str]
    description: str


def _choice(randomizer: Random, values: list[str]) -> str:
    return values[randomizer.randrange(0, len(values))]


def _build_reroute_payload(randomizer: Random) -> dict[str, Any]:
    source, destination = TRAFFIC_ROUTE_PAIRS[randomizer.randrange(0, len(TRAFFIC_ROUTE_PAIRS))]
    return {
        "route_id": f"RTR-{randomizer.randint(1000, 9999)}",
        "source": source,
        "destination": destination,
        "reason": _choice(randomizer, ["congestion", "event surge", "scheduled maintenance"]),
    }


def _build_reroute_telemetry(randomizer: Random) -> dict[str, Any]:
    return {
        "average_speed_kph": round(randomizer.uniform(14.0, 32.0), 2),
        "lane_occupancy_ratio": round(randomizer.uniform(0.62, 0.91), 3),
        "queue_length_vehicles": randomizer.randint(28, 140),
    }


def _build_close_road_payload(randomizer: Random) -> dict[str, Any]:
    return {
        "road_id": _choice(randomizer, TRAFFIC_ROADS),
    }


def _build_close_road_telemetry(randomizer: Random) -> dict[str, Any]:
    return {
        "incident_clearance_eta_minutes": randomizer.randint(15, 120),
        "detour_capacity_ratio": round(randomizer.uniform(0.55, 0.88), 3),
        "vehicle_density": randomizer.randint(120, 460),
    }


def _build_corridor_payload(randomizer: Random) -> dict[str, Any]:
    group = INTERSECTION_GROUPS[randomizer.randrange(0, len(INTERSECTION_GROUPS))]
    return {
        "route_id": f"EMERG-{randomizer.randint(100, 999)}",
        "intersections": group,
        "priority": "critical",
    }


def _build_corridor_telemetry(randomizer: Random) -> dict[str, Any]:
    return {
        "response_eta_minutes": randomizer.randint(3, 12),
        "ambulance_density": randomizer.randint(1, 4),
        "cross_traffic_delay_seconds": randomizer.randint(90, 420),
    }


def _build_load_balance_payload(randomizer: Random) -> dict[str, Any]:
    source_zone = _choice(randomizer, POWER_ZONES)
    target_options = [zone for zone in POWER_ZONES if zone != source_zone]
    return {
        "source_zone": source_zone,
        "target_zone": _choice(randomizer, target_options),
        "mw": round(randomizer.uniform(2.0, 9.0), 2),
    }


def _build_load_balance_telemetry(randomizer: Random) -> dict[str, Any]:
    return {
        "grid_frequency_hz": round(randomizer.uniform(49.7, 50.2), 3),
        "load_ratio": round(randomizer.uniform(0.48, 0.83), 3),
        "reserve_margin_mw": round(randomizer.uniform(18.0, 54.0), 2),
    }


def _build_shed_load_payload(randomizer: Random) -> dict[str, Any]:
    return {
        "zone": _choice(randomizer, ["north", "south", "east", "west", "industrial"]),
        "percentage": round(randomizer.uniform(8.0, 25.0), 2),
    }


def _build_shed_load_telemetry(randomizer: Random) -> dict[str, Any]:
    return {
        "transformer_temperature_c": round(randomizer.uniform(82.0, 116.0), 2),
        "load_ratio": round(randomizer.uniform(0.9, 1.12), 3),
        "projected_recovery_minutes": randomizer.randint(10, 55),
    }


def _build_shutdown_payload(randomizer: Random) -> dict[str, Any]:
    return {
        "zone": _choice(randomizer, ["north", "south", "east", "west"]),
    }


def _build_shutdown_telemetry(randomizer: Random) -> dict[str, Any]:
    return {
        "arc_fault_probability": round(randomizer.uniform(0.71, 0.96), 3),
        "breaker_trip_count": randomizer.randint(2, 11),
        "substation_alarm_score": round(randomizer.uniform(85.0, 99.5), 2),
    }


def _build_adjust_pressure_payload(randomizer: Random) -> dict[str, Any]:
    return {
        "zone_id": _choice(randomizer, WATER_ZONES),
        "pressure_change": round(randomizer.uniform(-9.0, 6.0), 2),
    }


def _build_adjust_pressure_telemetry(randomizer: Random) -> dict[str, Any]:
    return {
        "pressure_psi": round(randomizer.uniform(52.0, 72.0), 2),
        "flow_variance": round(randomizer.uniform(0.05, 0.32), 3),
        "demand_forecast_lpm": randomizer.randint(360, 920),
    }


def _build_isolate_zone_payload(randomizer: Random) -> dict[str, Any]:
    return {
        "zone_id": _choice(randomizer, WATER_ZONES),
    }


def _build_isolate_zone_telemetry(randomizer: Random) -> dict[str, Any]:
    return {
        "chlorine_ppm": round(randomizer.uniform(0.7, 1.8), 2),
        "leak_flow_lpm": randomizer.randint(140, 880),
        "repair_eta_minutes": randomizer.randint(20, 180),
    }


def _build_shutoff_payload(randomizer: Random) -> dict[str, Any]:
    return {
        "zone_id": _choice(randomizer, WATER_ZONES),
        "pump_id": _choice(randomizer, PUMPS),
    }


def _build_shutoff_telemetry(randomizer: Random) -> dict[str, Any]:
    return {
        "contaminant_index": round(randomizer.uniform(0.74, 0.98), 3),
        "pump_vibration_score": round(randomizer.uniform(78.0, 98.0), 2),
        "public_health_risk": _choice(randomizer, ["high", "critical"]),
    }


def _build_dispatch_payload(randomizer: Random) -> dict[str, Any]:
    return {
        "type": _choice(randomizer, DISPATCH_UNIT_TYPES),
        "location": _choice(randomizer, INCIDENT_LOCATIONS),
    }


def _build_dispatch_telemetry(randomizer: Random) -> dict[str, Any]:
    return {
        "dispatch_eta_minutes": randomizer.randint(2, 14),
        "available_units": randomizer.randint(4, 18),
        "crowd_density": round(randomizer.uniform(0.08, 0.72), 3),
    }


def _build_declare_payload(randomizer: Random) -> dict[str, Any]:
    incident_type = _choice(randomizer, INCIDENT_TYPES)
    severity = _choice(randomizer, ["high", "critical"])
    return {
        "incident_id": f"INC-{randomizer.randint(1000, 9999)}",
        "type": incident_type,
        "location": _choice(randomizer, INCIDENT_LOCATIONS),
        "severity": severity,
        "alert_level": "red" if severity == "critical" else "orange",
    }


def _build_declare_telemetry(randomizer: Random) -> dict[str, Any]:
    return {
        "casualty_risk_index": round(randomizer.uniform(0.65, 0.97), 3),
        "evacuation_radius_m": randomizer.randint(150, 950),
        "response_complexity_score": round(randomizer.uniform(78.0, 99.0), 2),
    }


def _build_mutual_aid_payload(randomizer: Random) -> dict[str, Any]:
    return {
        "region": _choice(randomizer, ["north", "south", "east", "west"]),
        "location": _choice(randomizer, INCIDENT_LOCATIONS),
        "requested_units": randomizer.randint(2, 8),
    }


def _build_mutual_aid_telemetry(randomizer: Random) -> dict[str, Any]:
    return {
        "active_incident_count": randomizer.randint(3, 11),
        "resource_exhaustion_ratio": round(randomizer.uniform(0.71, 0.95), 3),
        "mutual_aid_eta_minutes": randomizer.randint(12, 45),
    }


SCENARIO_LIBRARY: list[ScenarioTemplate] = [
    ScenarioTemplate(
        scenario_id="traffic_congestion_reroute",
        domain="traffic",
        action_type="reroute_traffic",
        source="traffic_agent",
        severity="medium",
        risk_level="medium",
        requires_human=False,
        weight=20,
        payload_factory=_build_reroute_payload,
        telemetry_factory=_build_reroute_telemetry,
        location_factory=lambda randomizer: _choice(randomizer, TRAFFIC_ROADS),
        description="Traffic sensor cluster detects congestion and requests a reroute plan.",
    ),
    ScenarioTemplate(
        scenario_id="traffic_accident_closure",
        domain="traffic",
        action_type="close_road",
        source="traffic_agent",
        severity="high",
        risk_level="high",
        requires_human=True,
        weight=10,
        payload_factory=_build_close_road_payload,
        telemetry_factory=_build_close_road_telemetry,
        location_factory=lambda randomizer: _choice(randomizer, TRAFFIC_ROADS),
        description="A road accident triggers closure workflow and detour validation.",
    ),
    ScenarioTemplate(
        scenario_id="traffic_emergency_corridor",
        domain="traffic",
        action_type="activate_emergency_corridor",
        source="traffic_agent",
        severity="critical",
        risk_level="critical",
        requires_human=True,
        weight=6,
        payload_factory=_build_corridor_payload,
        telemetry_factory=_build_corridor_telemetry,
        location_factory=lambda randomizer: _choice(randomizer, INCIDENT_LOCATIONS),
        description="Emergency responders require corridor preemption through multiple intersections.",
    ),
    ScenarioTemplate(
        scenario_id="power_load_balance",
        domain="power",
        action_type="load_balance",
        source="power_agent",
        severity="low",
        risk_level="low",
        requires_human=False,
        weight=18,
        payload_factory=_build_load_balance_payload,
        telemetry_factory=_build_load_balance_telemetry,
        location_factory=lambda randomizer: _choice(randomizer, POWER_ZONES),
        description="Substation telemetry indicates a routine need for power re-balancing.",
    ),
    ScenarioTemplate(
        scenario_id="power_shed_load",
        domain="power",
        action_type="shed_load",
        source="power_agent",
        severity="high",
        risk_level="high",
        requires_human=True,
        weight=9,
        payload_factory=_build_shed_load_payload,
        telemetry_factory=_build_shed_load_telemetry,
        location_factory=lambda randomizer: _choice(randomizer, ["north", "south", "east", "west"]),
        description="Transformer stress causes governance to consider selective load shedding.",
    ),
    ScenarioTemplate(
        scenario_id="power_emergency_shutdown",
        domain="power",
        action_type="emergency_shutdown",
        source="power_agent",
        severity="critical",
        risk_level="critical",
        requires_human=True,
        weight=4,
        payload_factory=_build_shutdown_payload,
        telemetry_factory=_build_shutdown_telemetry,
        location_factory=lambda randomizer: _choice(randomizer, ["north", "south", "east", "west"]),
        description="Severe electrical fault requires emergency shutdown of a power zone.",
    ),
    ScenarioTemplate(
        scenario_id="water_pressure_tuning",
        domain="water",
        action_type="adjust_pressure",
        source="water_agent",
        severity="low",
        risk_level="low",
        requires_human=False,
        weight=17,
        payload_factory=_build_adjust_pressure_payload,
        telemetry_factory=_build_adjust_pressure_telemetry,
        location_factory=lambda randomizer: _choice(randomizer, WATER_ZONES),
        description="Water pressure trends trigger automatic pressure tuning.",
    ),
    ScenarioTemplate(
        scenario_id="water_zone_isolation",
        domain="water",
        action_type="isolate_zone",
        source="water_agent",
        severity="high",
        risk_level="high",
        requires_human=True,
        weight=8,
        payload_factory=_build_isolate_zone_payload,
        telemetry_factory=_build_isolate_zone_telemetry,
        location_factory=lambda randomizer: _choice(randomizer, WATER_ZONES),
        description="Leak detection requires isolation of a water distribution zone.",
    ),
    ScenarioTemplate(
        scenario_id="water_emergency_shutoff",
        domain="water",
        action_type="emergency_shutoff",
        source="water_agent",
        severity="critical",
        risk_level="critical",
        requires_human=True,
        weight=4,
        payload_factory=_build_shutoff_payload,
        telemetry_factory=_build_shutoff_telemetry,
        location_factory=lambda randomizer: _choice(randomizer, WATER_ZONES),
        description="Contamination or pump failure triggers a full emergency shutoff.",
    ),
    ScenarioTemplate(
        scenario_id="emergency_dispatch",
        domain="emergency",
        action_type="dispatch_unit",
        source="emergency_agent",
        severity="medium",
        risk_level="medium",
        requires_human=False,
        weight=18,
        payload_factory=_build_dispatch_payload,
        telemetry_factory=_build_dispatch_telemetry,
        location_factory=lambda randomizer: _choice(randomizer, INCIDENT_LOCATIONS),
        description="Emergency command receives an incident report and dispatches units.",
    ),
    ScenarioTemplate(
        scenario_id="emergency_declaration",
        domain="emergency",
        action_type="declare_emergency",
        source="emergency_agent",
        severity="critical",
        risk_level="critical",
        requires_human=True,
        weight=5,
        payload_factory=_build_declare_payload,
        telemetry_factory=_build_declare_telemetry,
        location_factory=lambda randomizer: _choice(randomizer, INCIDENT_LOCATIONS),
        description="A major incident escalates to formal emergency declaration.",
    ),
    ScenarioTemplate(
        scenario_id="emergency_mutual_aid",
        domain="emergency",
        action_type="request_mutual_aid",
        source="emergency_agent",
        severity="high",
        risk_level="high",
        requires_human=True,
        weight=5,
        payload_factory=_build_mutual_aid_payload,
        telemetry_factory=_build_mutual_aid_telemetry,
        location_factory=lambda randomizer: _choice(randomizer, INCIDENT_LOCATIONS),
        description="Local resources are strained and mutual aid is requested.",
    ),
]
