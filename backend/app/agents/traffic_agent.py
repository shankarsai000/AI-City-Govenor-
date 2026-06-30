import asyncio
from typing import Any

from app.agents.base_agent import BaseAgent
from app.core.event_bus import subscribe_to_events
from app.core.logging import get_logger

logger = get_logger(__name__)


class TrafficAgent(BaseAgent):
    """
    Traffic Agent manages smart streetlights, intersection timing,
    and road routing structures.
    """

    def __init__(self) -> None:
        super().__init__(name="traffic_agent", domain="traffic")
        self._listener_task: asyncio.Task[None] | None = None

    def get_capabilities(self) -> list[dict[str, Any]]:
        return [
            {
                "action": "reroute_traffic",
                "risk": "medium",
                "requires_human": False,
                "rate_limit": "10/minute",
            },
            {
                "action": "close_road",
                "risk": "high",
                "requires_human": True,
                "rate_limit": "2/hour",
            },
            {
                "action": "activate_emergency_corridor",
                "risk": "critical",
                "requires_human": True,
                "rate_limit": "1/hour",
            },
        ]

    async def start(self) -> None:
        await super().start()
        # Start subscribing to events of interest
        self._listener_task = asyncio.create_task(self._listen())

    async def _listen(self) -> None:
        try:
            await subscribe_to_events(["emergency.incident_declared"], self._handle_emergency)
        except asyncio.CancelledError:
            pass

    async def _handle_emergency(self, event: dict[str, Any]) -> None:
        logger.info("Traffic Agent received emergency event, preparing response...", event_data=event)
        # Automatically request emergency corridor
        payload = {
            "route_id": event["payload"].get("route_id", "default_corridor"),
            "priority": "critical",
        }
        await self.request_action(
            action_type="activate_emergency_corridor",
            payload=payload,
            correlation_id=event.get("correlation_id"),
        )
