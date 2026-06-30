from typing import Any

from app.core.exceptions import CapabilityDeniedError
from app.core.logging import get_logger
from app.models.agent import Agent

logger = get_logger(__name__)


def validate_capability(agent: Agent, action_type: str) -> dict[str, Any]:
    """
    Verify that the requested action is declared inside the agent's capability list.
    Returns the capability dictionary if valid.
    """
    for cap in agent.capabilities:
        if cap.get("action") == action_type:
            logger.debug(
                "Capability validated",
                agent=agent.name,
                action=action_type,
                risk=cap.get("risk"),
            )
            return cap

    raise CapabilityDeniedError(
        f"Agent {agent.name} does not possess capability to perform '{action_type}'."
    )
