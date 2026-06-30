import asyncio
from typing import Any

from app.agents.base_agent import BaseAgent
from app.core.event_bus import subscribe_to_events
from app.core.logging import get_logger

logger = get_logger(__name__)


class PowerAgent(BaseAgent):
    """
    Power Agent coordinates substations, grid load balancing,
    and microgrid management.
    """

    def __init__(self) -> None:
        super().__init__(name="power_agent", domain="power")
        self._listener_task: asyncio.Task[None] | None = None

    def get_capabilities(self) -> list[dict[str, Any]]:
        return [
            {
                "action": "load_balance",
                "risk": "low",
                "requires_human": False,
                "rate_limit": "20/minute",
            },
            {
                "action": "shed_load",
                "risk": "high",
                "requires_human": True,
                "rate_limit": "5/hour",
            },
            {
                "action": "emergency_shutdown",
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
            await subscribe_to_events(["grid.overload_detected"], self._handle_overload)
        except asyncio.CancelledError:
            pass

    async def _handle_overload(self, event: dict[str, Any]) -> None:
        logger.info("Power Agent received overload event, determining strategy...", event_data=event)
        severity = event["payload"].get("severity", "medium")

        if severity == "critical":
            await self.request_action(
                action_type="shed_load",
                payload={"zone": event["payload"].get("zone", "Zone A"), "percentage": 30},
                correlation_id=event.get("correlation_id"),
            )
        else:
            await self.request_action(
                action_type="load_balance",
                payload={"source_zone": "Zone A", "target_zone": "Zone B", "mw": 5.0},
                correlation_id=event.get("correlation_id"),
            )
