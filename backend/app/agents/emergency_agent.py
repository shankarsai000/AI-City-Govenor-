import asyncio
from typing import Any

from app.agents.base_agent import BaseAgent
from app.core.event_bus import subscribe_to_events
from app.core.logging import get_logger

logger = get_logger(__name__)


class EmergencyAgent(BaseAgent):
    """
    Emergency Agent coordinates disaster response, police/fire dispatch,
    and municipal civil defense structures.
    """

    def __init__(self) -> None:
        super().__init__(name="emergency_agent", domain="emergency")
        self._listener_task: asyncio.Task[None] | None = None

    def get_capabilities(self) -> list[dict[str, Any]]:
        return [
            {
                "action": "dispatch_unit",
                "risk": "medium",
                "requires_human": False,
                "rate_limit": "30/minute",
            },
            {
                "action": "declare_emergency",
                "risk": "critical",
                "requires_human": True,
                "rate_limit": "1/hour",
            },
            {
                "action": "request_mutual_aid",
                "risk": "high",
                "requires_human": True,
                "rate_limit": "5/hour",
            },
        ]

    async def start(self) -> None:
        await super().start()
        self._listener_task = asyncio.create_task(self._listen())

    async def _listen(self) -> None:
        try:
            await subscribe_to_events(["emergency.incident_reported"], self._handle_report)
        except asyncio.CancelledError:
            pass

    async def _handle_report(self, event: dict[str, Any]) -> None:
        logger.info("Emergency Agent received active report, dispatching...", event_data=event)
        await self.request_action(
            action_type="dispatch_unit",
            payload={
                "type": event["payload"].get("incident_type", "fire"),
                "location": event["payload"].get("location", "Intersection 5"),
            },
            correlation_id=event.get("correlation_id"),
        )
