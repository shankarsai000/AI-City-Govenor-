"""
ArmorIQ SDK client singleton factory.

Design decisions:
- Single client instance per process (thread-safe, matches SDK design intent).
- Initialized during FastAPI lifespan startup — never lazily on first request
  to avoid race conditions in concurrent request handling.
- The client is intentionally NOT async: the SDK's Python implementation uses
  synchronous HTTP (httpx in sync mode). We wrap the blocking calls in
  asyncio.to_thread() inside intent_service.py to stay non-blocking.
- If ARMORIQ_API_KEY is not set, client initialization is skipped and all
  ArmorIQ calls become no-ops (graceful degradation for local development).
"""
import logging
from typing import Optional

from armoriq_sdk import ArmorIQClient as _ArmorIQClient

from app.armoriq.exceptions import ArmorIQClientNotInitialized
from app.config import get_settings

logger = logging.getLogger(__name__)

_client: Optional[_ArmorIQClient] = None


def initialize_client() -> None:
    """
    Initialize the ArmorIQ client singleton.

    Must be called once during application startup (FastAPI lifespan).
    Idempotent — safe to call multiple times.
    """
    global _client

    settings = get_settings()
    api_key = settings.ARMORIQ_API_KEY

    if not api_key:
        logger.warning(
            "ARMORIQ_API_KEY is not set. ArmorIQ integration is DISABLED. "
            "All governance actions will proceed without external intent enforcement. "
            "This is only acceptable in local development."
        )
        return

    if not api_key.startswith(("ak_live_", "ak_test_", "ak_claw_")):
        logger.error(
            "ARMORIQ_API_KEY has an invalid format. Must start with ak_live_, "
            "ak_test_, or ak_claw_. ArmorIQ integration will be DISABLED."
        )
        return

    try:
        _client = _ArmorIQClient(
            api_key=api_key,
            timeout=float(settings.ARMORIQ_TIMEOUT_SECONDS),
        )
        logger.info("ArmorIQ client initialized. Intent enforcement is ACTIVE.")
    except Exception as exc:
        logger.error("Failed to initialize ArmorIQ client: %s", exc, exc_info=True)
        _client = None


def get_client() -> _ArmorIQClient:
    """
    Return the initialized ArmorIQ client singleton.

    Raises:
        ArmorIQClientNotInitialized: If the client was not initialized at startup.
    """
    if _client is None:
        raise ArmorIQClientNotInitialized(
            "ArmorIQ client is not initialized. Ensure ARMORIQ_API_KEY is set "
            "and initialize_client() was called during application startup."
        )
    return _client


def is_enabled() -> bool:
    """Return True if the ArmorIQ client is initialized and active."""
    return _client is not None


def shutdown_client() -> None:
    """
    Gracefully shut down the client.

    Called during FastAPI lifespan shutdown.
    """
    global _client
    _client = None
    logger.info("ArmorIQ client shut down.")
