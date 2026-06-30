"""
Redis connection pool and client management.

Design decision: Single connection pool shared across the application.
Redis serves dual purpose:
1. City state cache — sub-millisecond reads for dashboard
2. Pub/Sub message bus — agent event distribution without direct coupling

Using redis-py async client (redis.asyncio) for non-blocking I/O.
"""
import redis.asyncio as aioredis
from redis.asyncio import Redis
from redis.asyncio.connection import ConnectionPool

from app.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_redis_pool: ConnectionPool | None = None
_redis_client: Redis | None = None


async def init_redis() -> None:
    """
    Initialize Redis connection pool.
    Called once during application startup.
    """
    global _redis_pool, _redis_client
    settings = get_settings()

    logger.info("Initializing Redis connection", url=settings.REDIS_URL)

    _redis_pool = ConnectionPool.from_url(
        settings.REDIS_URL,
        max_connections=settings.REDIS_MAX_CONNECTIONS,
        decode_responses=True,  # All values are strings
    )

    _redis_client = Redis(connection_pool=_redis_pool)

    # Verify connection
    await _redis_client.ping()
    logger.info("Redis connection established")


async def close_redis() -> None:
    """Gracefully close Redis connections. Called on application shutdown."""
    global _redis_pool
    if _redis_pool:
        await _redis_pool.disconnect()
        logger.info("Redis connections closed")


def get_redis() -> Redis:
    """
    Get the shared Redis client.
    Use as FastAPI dependency: redis: Redis = Depends(get_redis)
    """
    if _redis_client is None:
        raise RuntimeError("Redis not initialized. Call init_redis() first.")
    return _redis_client


async def get_redis_pubsub() -> aioredis.client.PubSub:
    """
    Create a new Pub/Sub connection.
    Each subscriber needs its own connection — do not share across tasks.
    """
    client = get_redis()
    return client.pubsub()
