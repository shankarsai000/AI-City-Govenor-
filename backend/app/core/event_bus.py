"""
Internal event bus abstraction over Redis Pub/Sub.

Design decision: We wrap Redis Pub/Sub behind an EventBus abstraction so:
1. Agents publish/subscribe to typed events, not raw Redis channels
2. We can swap the transport (e.g., to Kafka) without touching agent code
3. All events are serialized consistently (JSON) with mandatory fields

Event envelope structure:
{
  "event_id": "uuid",
  "event_type": "traffic.reroute_requested",
  "source_agent": "traffic_agent",
  "timestamp": "2024-01-01T00:00:00Z",
  "payload": {...},
  "correlation_id": "optional-trace-id"
}
"""
import asyncio
import json
import uuid
from collections.abc import AsyncGenerator, Callable, Coroutine
from datetime import datetime, timezone
from typing import Any

from app.core.logging import get_logger
from app.core.redis_client import get_redis, get_redis_pubsub

logger = get_logger(__name__)

# Channel prefix for all city governor events
CHANNEL_PREFIX = "city_governor"

EventHandler = Callable[[dict[str, Any]], Coroutine[Any, Any, None]]


def _build_channel(event_type: str) -> str:
    """Convert event_type like 'traffic.reroute' to Redis channel name."""
    return f"{CHANNEL_PREFIX}:{event_type}"


def _build_envelope(
    event_type: str,
    source_agent: str,
    payload: dict[str, Any],
    correlation_id: str | None = None,
) -> dict[str, Any]:
    return {
        "event_id": str(uuid.uuid4()),
        "event_type": event_type,
        "source_agent": source_agent,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "payload": payload,
        "correlation_id": correlation_id or str(uuid.uuid4()),
    }


async def publish_event(
    event_type: str,
    source_agent: str,
    payload: dict[str, Any],
    correlation_id: str | None = None,
) -> str:
    """
    Publish a typed event to the event bus.
    Returns the event_id for tracing.
    """
    redis = get_redis()
    envelope = _build_envelope(event_type, source_agent, payload, correlation_id)
    channel = _build_channel(event_type)

    await redis.publish(channel, json.dumps(envelope))

    logger.debug(
        "Event published",
        event_type=event_type,
        event_id=envelope["event_id"],
        channel=channel,
        source=source_agent,
    )

    return envelope["event_id"]


async def subscribe_to_events(
    event_patterns: list[str],
    handler: EventHandler,
) -> None:
    """
    Subscribe to one or more event type patterns and invoke handler for each.
    Uses Redis pattern subscribe (psubscribe) to support wildcard patterns.

    Example patterns:
      ["traffic.*"]           — all traffic events
      ["*.emergency"]         — any emergency events
      ["power.shed_load"]     — specific event type
    """
    pubsub = await get_redis_pubsub()
    channels = [_build_channel(p) for p in event_patterns]

    await pubsub.psubscribe(*[f"{CHANNEL_PREFIX}:{p}" for p in event_patterns])

    logger.info("Subscribed to event patterns", patterns=event_patterns)

    try:
        async for message in pubsub.listen():
            if message["type"] not in ("pmessage", "message"):
                continue
            try:
                envelope = json.loads(message["data"])
                await handler(envelope)
            except json.JSONDecodeError:
                logger.error("Invalid JSON in event message", raw=message["data"])
            except Exception:
                logger.exception("Event handler raised exception", message=message)
    finally:
        await pubsub.unsubscribe()
        await pubsub.close()
