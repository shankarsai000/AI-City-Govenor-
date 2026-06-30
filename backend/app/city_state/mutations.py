"""
State mutation applications for all agent action types.

This module houses:
1. Mutation functions that transform a domain state immutably.
2. Mutation metadata builders used by governance and the state manager.
3. Resource inference logic so locking can reflect real-world infrastructure
   assets instead of relying only on coarse domain-wide serialization.
"""
from typing import Any, Callable
from copy import deepcopy

from app.city_state.domains import (
    TrafficState,
    PowerState,
    WaterState,
    EmergencyState,
    IntersectionState,
    IncidentRecord,
    DispatchedUnit,
    StateMutation,
)

# ── Traffic Mutations ────────────────────────────────────────────────────────

def apply_reroute_traffic(state: TrafficState, payload: dict[str, Any]) -> TrafficState:
    new_state = deepcopy(state)
    route_id = payload.get("route_id", "REROUTE-001")
    new_state.active_reroutes.append({
        "route_id": route_id,
        "source": payload.get("source", "Zone A"),
        "destination": payload.get("destination", "Zone B"),
        "reason": payload.get("reason", "congestion")
    })
    # Congestion might shift slightly
    new_state.congestion_level = min(1.0, max(0.0, new_state.congestion_level - 0.05))
    return new_state

def apply_close_road(state: TrafficState, payload: dict[str, Any]) -> TrafficState:
    new_state = deepcopy(state)
    road_id = payload.get("road_id", "MAIN_ST")
    if road_id not in new_state.closed_roads:
        new_state.closed_roads.append(road_id)
    # Closing a road increases congestion
    new_state.congestion_level = min(1.0, new_state.congestion_level + 0.1)
    return new_state

def apply_activate_emergency_corridor(state: TrafficState, payload: dict[str, Any]) -> TrafficState:
    new_state = deepcopy(state)
    route_id = payload.get("route_id", "EMERGENCY_CORRIDOR")
    if route_id not in new_state.active_corridors:
        new_state.active_corridors.append(route_id)
        
    # Preempt any intersections along the corridor
    intersections_to_preempt = payload.get("intersections", ["INT-001", "INT-002"])
    for int_id in intersections_to_preempt:
        if int_id in new_state.intersections:
            new_state.intersections[int_id].emergency_preempt = True
            new_state.intersections[int_id].signal_phase = "flashing"
            
    return new_state


# ── Power Mutations ──────────────────────────────────────────────────────────

def apply_load_balance(state: PowerState, payload: dict[str, Any]) -> PowerState:
    new_state = deepcopy(state)
    source = payload.get("source_zone")
    target = payload.get("target_zone")
    mw = payload.get("mw", 5.0)
    
    # Adjust substation loads if substation exists
    if source in new_state.substations:
        new_state.substations[source].load_mw = max(0.0, new_state.substations[source].load_mw - mw)
    if target in new_state.substations:
        new_state.substations[target].load_mw = min(
            new_state.substations[target].capacity_mw, 
            new_state.substations[target].load_mw + mw
        )
        
    return new_state

def apply_shed_load(state: PowerState, payload: dict[str, Any]) -> PowerState:
    new_state = deepcopy(state)
    zone = payload.get("zone", "Zone A")
    percentage = payload.get("percentage", 10.0)
    
    # Update shed operations
    new_state.active_shedding.append({
        "zone": zone,
        "percentage": percentage
    })
    
    # Decrease load based on shedding percentage
    reduction = state.grid_load_mw * (percentage / 100.0)
    new_state.grid_load_mw = max(0.0, new_state.grid_load_mw - reduction)
    
    return new_state

def apply_emergency_shutdown(state: PowerState, payload: dict[str, Any]) -> PowerState:
    new_state = deepcopy(state)
    zone = payload.get("zone", "Zone A")
    if zone not in new_state.blackout_zones:
        new_state.blackout_zones.append(zone)
        
    # Mark substations in that zone as offline
    substation_id = f"SUB-{zone.upper()}"
    if substation_id in new_state.substations:
        new_state.substations[substation_id].status = "offline"
        new_state.substations[substation_id].load_mw = 0.0
        
    # Drop grid load
    new_state.grid_load_mw = max(0.0, new_state.grid_load_mw - 30.0)
    return new_state


# ── Water Mutations ──────────────────────────────────────────────────────────

def apply_adjust_pressure(state: WaterState, payload: dict[str, Any]) -> WaterState:
    new_state = deepcopy(state)
    pressure_change = payload.get("pressure_change", -5.0)
    new_state.pressure_psi = min(120.0, max(0.0, new_state.pressure_psi + pressure_change))
    return new_state

def apply_isolate_zone(state: WaterState, payload: dict[str, Any]) -> WaterState:
    new_state = deepcopy(state)
    zone_id = payload.get("zone_id", "Zone C")
    if zone_id not in new_state.active_isolations:
        new_state.active_isolations.append(zone_id)
        
    # Isolate zone leak mitigation
    if zone_id in new_state.leak_zones:
        new_state.leak_zones.remove(zone_id)
        
    return new_state

def apply_emergency_shutoff(state: WaterState, payload: dict[str, Any]) -> WaterState:
    new_state = deepcopy(state)
    zone_id = payload.get("zone_id", "Zone C")
    if zone_id not in new_state.active_isolations:
        new_state.active_isolations.append(zone_id)
        
    # Shut down pumps associated with this zone
    pump_id = payload.get("pump_id", "PUMP-01")
    if pump_id in new_state.pumps:
        new_state.pumps[pump_id].status = "stopped"
        new_state.pumps[pump_id].flow_rate_lpm = 0.0
        
    # Pressure drops sharply
    new_state.pressure_psi = max(0.0, new_state.pressure_psi - 20.0)
    return new_state


# ── Emergency Mutations ───────────────────────────────────────────────────────

def apply_dispatch_unit(state: EmergencyState, payload: dict[str, Any]) -> EmergencyState:
    new_state = deepcopy(state)
    unit_id = f"UNIT-{len(new_state.dispatched_units) + 1:03d}"
    new_state.dispatched_units.append(DispatchedUnit(
        unit_id=unit_id,
        unit_type=payload.get("type", "fire"),
        location=payload.get("location", "Intersection 5"),
        status="en_route"
    ))
    return new_state

def apply_declare_emergency(state: EmergencyState, payload: dict[str, Any]) -> EmergencyState:
    new_state = deepcopy(state)
    incident_id = payload.get("incident_id", "INC-001")
    
    new_state.active_incidents.append(IncidentRecord(
        incident_id=incident_id,
        incident_type=payload.get("type", "fire"),
        location=payload.get("location", "Zone A"),
        severity=payload.get("severity", "high"),
        status="active"
    ))
    
    new_state.alert_level = payload.get("alert_level", "orange")
    if incident_id not in new_state.declared_emergencies:
        new_state.declared_emergencies.append(incident_id)
        
    return new_state

def apply_request_mutual_aid(state: EmergencyState, payload: dict[str, Any]) -> EmergencyState:
    new_state = deepcopy(state)
    new_state.alert_level = "red"
    return new_state


# ── Registry ─────────────────────────────────────────────────────────────────

ACTION_DOMAIN_MAP: dict[str, str] = {
    "reroute_traffic": "traffic",
    "close_road": "traffic",
    "activate_emergency_corridor": "traffic",
    "load_balance": "power",
    "shed_load": "power",
    "emergency_shutdown": "power",
    "adjust_pressure": "water",
    "isolate_zone": "water",
    "emergency_shutoff": "water",
    "dispatch_unit": "emergency",
    "declare_emergency": "emergency",
    "request_mutual_aid": "emergency",
}


def _normalize_resource_value(value: str | None, fallback: str) -> str:
    normalized = (value or fallback).strip().lower().replace(" ", "_")
    return normalized or fallback


def infer_affected_resources(action_type: str, payload: dict[str, Any]) -> list[str]:
    """Infer the infrastructure resources a mutation touches for lock scoping."""
    resources: list[str] = []
    domain = ACTION_DOMAIN_MAP.get(action_type)
    if domain:
        resources.append(f"{domain}:domain")

    if action_type == "close_road":
        road_id = _normalize_resource_value(payload.get("road_id"), "unknown_road")
        resources.append(f"traffic:road:{road_id}")

    elif action_type == "reroute_traffic":
        route_id = _normalize_resource_value(payload.get("route_id"), "default_route")
        resources.append(f"traffic:route:{route_id}")

    elif action_type == "activate_emergency_corridor":
        route_id = _normalize_resource_value(payload.get("route_id"), "emergency_corridor")
        resources.append(f"traffic:corridor:{route_id}")
        for intersection_id in payload.get("intersections", []):
            resources.append(
                f"traffic:intersection:{_normalize_resource_value(intersection_id, 'unknown_intersection')}"
            )

    elif action_type == "load_balance":
        source_zone = _normalize_resource_value(payload.get("source_zone"), "unknown_source")
        target_zone = _normalize_resource_value(payload.get("target_zone"), "unknown_target")
        resources.append(f"power:substation:{source_zone}")
        resources.append(f"power:substation:{target_zone}")

    elif action_type == "shed_load":
        zone = _normalize_resource_value(payload.get("zone"), "unknown_zone")
        resources.append(f"power:zone:{zone}")

    elif action_type == "emergency_shutdown":
        zone = _normalize_resource_value(payload.get("zone"), "unknown_zone")
        resources.append(f"power:zone:{zone}")
        resources.append(f"power:substation:sub_{zone}")

    elif action_type == "adjust_pressure":
        zone = _normalize_resource_value(payload.get("zone_id"), "system")
        resources.append(f"water:zone:{zone}")

    elif action_type == "isolate_zone":
        zone = _normalize_resource_value(payload.get("zone_id"), "unknown_zone")
        resources.append(f"water:zone:{zone}")

    elif action_type == "emergency_shutoff":
        zone = _normalize_resource_value(payload.get("zone_id"), "unknown_zone")
        pump_id = _normalize_resource_value(payload.get("pump_id"), "unknown_pump")
        resources.append(f"water:zone:{zone}")
        resources.append(f"water:pump:{pump_id}")

    elif action_type == "dispatch_unit":
        location = _normalize_resource_value(payload.get("location"), "unknown_location")
        resources.append(f"emergency:location:{location}")

    elif action_type == "declare_emergency":
        incident_id = _normalize_resource_value(payload.get("incident_id"), "unknown_incident")
        location = _normalize_resource_value(payload.get("location"), "unknown_location")
        resources.append(f"emergency:incident:{incident_id}")
        resources.append(f"emergency:location:{location}")

    elif action_type == "request_mutual_aid":
        resources.append("emergency:mutual_aid")

    # Preserve order but remove duplicates.
    return list(dict.fromkeys(resources))


def build_state_mutation(action_type: str, payload: dict[str, Any]) -> StateMutation:
    """Create a typed mutation descriptor shared by governance and state sync."""
    domain = ACTION_DOMAIN_MAP.get(action_type)
    if not domain:
        raise ValueError(f"Unknown action type for city state mutation: {action_type}")

    return StateMutation(
        domain=domain,
        action_type=action_type,
        description=f"Mutation triggered by {action_type}",
        payload=payload,
        affected_resources=infer_affected_resources(action_type, payload),
    )

MUTATION_REGISTRY: dict[str, Callable[[Any, dict[str, Any]], Any]] = {
    "reroute_traffic": apply_reroute_traffic,
    "close_road": apply_close_road,
    "activate_emergency_corridor": apply_activate_emergency_corridor,
    "load_balance": apply_load_balance,
    "shed_load": apply_shed_load,
    "emergency_shutdown": apply_emergency_shutdown,
    "adjust_pressure": apply_adjust_pressure,
    "isolate_zone": apply_isolate_zone,
    "emergency_shutoff": apply_emergency_shutoff,
    "dispatch_unit": apply_dispatch_unit,
    "declare_emergency": apply_declare_emergency,
    "request_mutual_aid": apply_request_mutual_aid,
}
