"""
Physical constraint validation and conflict detection.

Design decisions:
1. A rule-based registry (CONFLICT_RULES) of functions evaluating proposed mutations against CityState.
2. Cross-domain validation ensures physical interactions are caught (e.g. cutting power stops water pumps).
3. Conflict structures return detailed descriptors, severity, and resolution hints.
"""
from typing import Any
from app.city_state.domains import CityState, StateMutation, Conflict


def _normalize(value: Any) -> str:
    return str(value or "").strip().lower()

class ConflictDetector:
    """Detects physical, logic, and resource conflicts for proposed mutations."""

    @staticmethod
    async def check(domain: str, mutation: StateMutation, current_state: CityState) -> list[Conflict]:
        """
        Check a proposed state mutation against current city state.
        Returns a list of Conflict objects if conflicts are found.
        """
        conflicts: list[Conflict] = []
        action_type = mutation.action_type
        payload = mutation.payload

        # ── Rule 1: Capacity Checks (Power) ──────────────────────────────────
        if domain == "power":
            if action_type == "load_balance":
                target_zone = payload.get("target_zone")
                mw = payload.get("mw", 0.0)
                if target_zone in current_state.power.substations:
                    sub = current_state.power.substations[target_zone]
                    if sub.status == "offline":
                        conflicts.append(Conflict(
                            severity="critical",
                            description=f"Cannot route {mw} MW to offline substation '{target_zone}'.",
                            conflicting_domain="power",
                            resolution_hint="Abort or bring substation online first."
                        ))
                    elif sub.load_mw + mw > sub.capacity_mw:
                        conflicts.append(Conflict(
                            severity="high",
                            description=f"Routing {mw} MW to '{target_zone}' exceeds capacity of {sub.capacity_mw} MW.",
                            conflicting_domain="power",
                            resolution_hint="Trigger load-shed or route to a different target."
                        ))

            elif action_type == "shed_load":
                zone = _normalize(payload.get("zone"))
                if zone and any(zone in _normalize(incident.location) for incident in current_state.emergency.active_incidents):
                    conflicts.append(Conflict(
                        severity="high",
                        description=f"Load shedding in '{payload.get('zone')}' would impact an active emergency response area.",
                        conflicting_domain="emergency",
                        resolution_hint="Coordinate with emergency operations before shedding load in that zone."
                    ))

            elif action_type == "emergency_shutdown":
                zone = payload.get("zone")
                if zone in current_state.power.blackout_zones:
                    conflicts.append(Conflict(
                        severity="medium",
                        description=f"Zone '{zone}' is already in blackout state.",
                        conflicting_domain="power",
                        resolution_hint="Avoid duplicate shutdown and verify restoration intent."
                    ))

        # ── Rule 2: Physical Dependency Check (Water / Power) ─────────────────
        if domain == "water" and action_type in ("adjust_pressure", "emergency_shutoff"):
            # If pumps require power, check substation status
            zone_id = payload.get("zone_id", "Zone C")
            substation_id = f"SUB-{zone_id.upper()}"
            if substation_id in current_state.power.substations:
                sub = current_state.power.substations[substation_id]
                if sub.status == "offline" or zone_id in current_state.power.blackout_zones:
                    conflicts.append(Conflict(
                        severity="high",
                        description=f"Water operation in '{zone_id}' relies on offline power substation '{substation_id}'.",
                        conflicting_domain="power",
                        resolution_hint="Restore power before resuming water pump operations."
                    ))

            if action_type == "adjust_pressure":
                projected_pressure = current_state.water.pressure_psi + payload.get("pressure_change", -5.0)
                if projected_pressure < 35.0:
                    conflicts.append(Conflict(
                        severity="medium",
                        description=f"Projected water pressure would fall below safe operating threshold ({projected_pressure} PSI).",
                        conflicting_domain="water",
                        resolution_hint="Reduce pressure drop or isolate the affected zone first."
                    ))

        # ── Rule 3: Cross-Domain Safety Checks (Traffic / Emergency) ──────────
        if domain == "traffic" and action_type == "close_road":
            road_id = payload.get("road_id")
            # If there is an active emergency scene matching the location, blocking road is critical
            for incident in current_state.emergency.active_incidents:
                if road_id in incident.location or incident.location in road_id:
                    conflicts.append(Conflict(
                        severity="critical",
                        description=f"Cannot close road '{road_id}' due to active emergency incident '{incident.incident_id}' nearby.",
                        conflicting_domain="emergency",
                        resolution_hint="Keep corridor open for responders or dispatch via alternate route."
                    ))
            if road_id in current_state.traffic.active_corridors:
                conflicts.append(Conflict(
                    severity="high",
                    description=f"Road '{road_id}' is part of an active emergency corridor.",
                    conflicting_domain="traffic",
                    resolution_hint="Deactivate or reroute the emergency corridor before closing this road."
                ))

        if domain == "traffic" and action_type == "activate_emergency_corridor":
            route_id = payload.get("route_id")
            if route_id in current_state.traffic.closed_roads:
                conflicts.append(Conflict(
                    severity="high",
                    description=f"Emergency corridor '{route_id}' overlaps a currently closed road.",
                    conflicting_domain="traffic",
                    resolution_hint="Reopen the road or pick a different corridor."
                ))

        # ── Rule 4: Water Isolations ──────────────────────────────────────────
        if domain == "water" and action_type == "isolate_zone":
            zone_id = payload.get("zone_id")
            if zone_id in current_state.water.active_isolations:
                conflicts.append(Conflict(
                    severity="low",
                    description=f"Zone '{zone_id}' is already isolated.",
                    conflicting_domain="water",
                    resolution_hint="No action required."
                ))
            if any(_normalize(zone_id) in _normalize(incident.location) for incident in current_state.emergency.active_incidents):
                conflicts.append(Conflict(
                    severity="high",
                    description=f"Cannot isolate water zone '{zone_id}' while responders are addressing an incident in the same area.",
                    conflicting_domain="emergency",
                    resolution_hint="Coordinate with emergency command before isolating this zone."
                ))

        # ── Rule 5: Emergency Level Conflicts ─────────────────────────────────
        if domain == "emergency" and action_type == "dispatch_unit":
            unit_type = payload.get("type")
            # Emergency alert red/orange might block low-risk dispatches or flag warnings
            if current_state.emergency.alert_level == "red" and unit_type == "medical":
                conflicts.append(Conflict(
                    severity="medium",
                    description="Medical dispatch requested while the city remains at red alert.",
                    conflicting_domain="emergency",
                    resolution_hint="Confirm resource availability with emergency command."
                ))

        if domain == "emergency" and action_type == "declare_emergency":
            incident_id = payload.get("incident_id")
            for incident in current_state.emergency.active_incidents:
                if incident.incident_id == incident_id and incident.status == "active":
                    conflicts.append(Conflict(
                        severity="medium",
                        description=f"Incident '{incident_id}' is already declared and active.",
                        conflicting_domain="emergency",
                        resolution_hint="Update the existing incident instead of declaring a duplicate."
                    ))

        return conflicts
