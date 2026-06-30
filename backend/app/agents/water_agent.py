import asyncio
from typing import Any

from app.agents.base_agent import BaseAgent
from app.core.event_bus import subscribe_to_events
from app.core.logging import get_logger

logger = get_logger(__name__)


class WaterAgent(BaseAgent):
    """
    Water Agent monitors pressure systems, treatment valves,
    and aqueduct loops.
    """

    def __init__(self) -> None:
        super().__init__(name="water_agent", domain="water")
        self._listener_task: asyncio.Task[None] | None = None

    def get_capabilities(self) -> list[dict[str, Any]]:
        return [
            {
                "action": "adjust_pressure",
                "risk": "low",
                "requires_human": False,
                "rate_limit": "15/minute",
            },
            {
                "action": "isolate_zone",
                "risk": "high",
                "requires_human": True,
                "rate_limit": "2/hour",
            },
            {
                "action": "emergency_shutoff",
                "risk": "critical",
                "requires_human": True,
                "rate_limit": "1/hour",
            },
        ]

    async def start(self) -> None:
        await super().start()
        self._listener_task = asyncio.create_task(self._listen())

    async def _listen(self) -> None:
        try:
            await subscribe_to_events(["water.leak_detected"], self._handle_leak)
        except asyncio.CancelledError:
            pass

    async def _handle_leak(self, event: dict[str, Any]) -> None:
        logger.info("Water Agent received leak notification", event_data=event)
        await self.request_action(
            action_type="isolate_zone",
            payload={"zone_id": event["payload"].get("zone_id", "Zone C")},
            correlation_id=event.get("correlation_id"),
        )
