"""
ArmorIQ Plan Builder.

Responsibility: Translate our internal domain objects (agent_id, action_type,
params) into the exact plan dict structure required by ArmorIQ's capture_plan().

The plan dict structure per ArmorIQ docs:
{
    "steps": [
        {
            "mcp": "<mcp-server-name>",       # registered MCP server name
            "action": "<tool-name>",           # tool within that MCP
            "params": { ... }                  # optional parameter hints
        }
    ]
}

MCP Naming Convention:
  City infrastructure MCPs follow "city-<domain>-mcp" naming.
  These names must match exactly what is registered on the ArmorIQ platform.
  Mapping is defined in AGENT_MCP_MAP below — update this when MCPs are
  registered on the platform dashboard.
"""
import logging
from typing import Any

logger = logging.getLogger(__name__)

# Maps agent_type prefix → MCP server name registered on ArmorIQ platform.
# Key: agent_type value stored in our Agent model (e.g. "traffic_agent")
# Value: MCP server name as registered in ArmorIQ dashboard
AGENT_MCP_MAP: dict[str, str] = {
    "traffic_agent": "city-traffic-mcp",
    "power_agent": "city-power-mcp",
    "water_agent": "city-water-mcp",
    "emergency_agent": "city-emergency-mcp",
    # Fallback for unknown agent types
    "default": "city-infrastructure-mcp",
}

# Maps high-level action_type → tool name within the MCP.
# These are the atomic tool names exposed by each MCP server.
ACTION_TOOL_MAP: dict[str, str] = {
    # Traffic
    "adjust_signal_timing": "set_signal_phase",
    "reroute_traffic": "update_routing_table",
    "close_intersection": "control_intersection",
    "enable_emergency_corridor": "activate_emergency_route",
    # Power
    "reduce_grid_load": "adjust_load_balance",
    "activate_backup_power": "enable_backup_generator",
    "shed_load_zone": "execute_load_shedding",
    "restore_power_zone": "restore_grid_segment",
    # Water
    "increase_pump_pressure": "set_pump_pressure",
    "isolate_pipe_segment": "control_valve",
    "activate_emergency_supply": "switch_supply_source",
    "reduce_distribution_pressure": "set_distribution_pressure",
    # Emergency
    "declare_emergency_zone": "activate_emergency_protocol",
    "coordinate_evacuation": "initiate_evacuation_plan",
    "dispatch_response_units": "deploy_response_team",
    "alert_population": "broadcast_emergency_alert",
    # Generic
    "execute_action": "execute_infrastructure_command",
}


def build_plan(
    agent_type: str,
    action_type: str,
    params: dict[str, Any] | None = None,
    risk_level: str = "medium",
) -> dict:
    """
    Build the ArmorIQ plan dict for a given city infrastructure action.

    Args:
        agent_type: The type of agent making the request (e.g. "traffic_agent").
        action_type: The action being requested (e.g. "adjust_signal_timing").
        params: Optional action parameters to include as hints in the plan.
        risk_level: Risk level — included in plan metadata for policy evaluation.

    Returns:
        A plan dict conforming to ArmorIQ's required structure.
    """
    mcp_name = AGENT_MCP_MAP.get(agent_type, AGENT_MCP_MAP["default"])
    tool_name = ACTION_TOOL_MAP.get(action_type, action_type)

    # Include safe, non-sensitive param keys as hints (omit values that may
    # contain PII or infrastructure secrets)
    param_hints: dict[str, Any] = {}
    if params:
        # Include only structural hints — actual values go via secure channel
        param_hints = {k: type(v).__name__ for k, v in params.items()}

    plan = {
        "steps": [
            {
                "mcp": mcp_name,
                "action": tool_name,
                "params": param_hints,
            }
        ],
        "metadata": {
            "risk_level": risk_level,
            "domain": "city_infrastructure",
            "agent_type": agent_type,
            "action_type": action_type,
        },
    }

    logger.debug(
        "Built ArmorIQ plan: agent=%s action=%s mcp=%s tool=%s",
        agent_type,
        action_type,
        mcp_name,
        tool_name,
    )
    return plan


def build_prompt(agent_type: str, action_type: str, params: dict[str, Any] | None = None) -> str:
    """
    Build a human-readable prompt string describing the agent's intent.

    This is the 'prompt' parameter for capture_plan() — it describes
    what the agent intends to accomplish in natural language for the
    ArmorIQ audit trail.
    """
    action_readable = action_type.replace("_", " ").title()
    domain = agent_type.replace("_agent", "").replace("_", " ").title()

    base = f"{domain} Agent: {action_readable}"
    if params:
        # Include non-sensitive context
        location = params.get("zone") or params.get("sector") or params.get("location")
        if location:
            base += f" in zone {location}"

    return base
