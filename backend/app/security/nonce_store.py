from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.config import get_settings
from app.core.redis_client import get_redis

NONCE_PREFIX = "security:nonce"
_memory_nonces: dict[str, datetime] = {}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _get_key(subject: str, nonce: str) -> str:
    return f"{NONCE_PREFIX}:{subject}:{nonce}"


def _is_test_mode() -> bool:
    return get_settings().APP_ENV == "test"


class NonceStore:
    """Replay-protection store for one-time agent nonces."""

    @classmethod
    async def register(cls, subject: str, nonce: str, ttl_seconds: int | None = None) -> bool:
        ttl_seconds = ttl_seconds or get_settings().NONCE_TTL_SECONDS
        key = _get_key(subject, nonce)
        try:
            redis = get_redis()
            return bool(await redis.set(key, "used", nx=True, ex=ttl_seconds))
        except RuntimeError:
            if not _is_test_mode():
                raise
            expires_at = _memory_nonces.get(key)
            if expires_at and expires_at > _utc_now():
                return False
            _memory_nonces[key] = _utc_now() + timedelta(seconds=ttl_seconds)
            return True
