from __future__ import annotations

from datetime import datetime, timezone

from app.config import get_settings
from app.core.redis_client import get_redis

TOKEN_PREFIX = "security:revoked_token"
_memory_revoked_tokens: dict[str, datetime] = {}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _get_key(token_id: str) -> str:
    return f"{TOKEN_PREFIX}:{token_id}"


def _is_test_mode() -> bool:
    return get_settings().APP_ENV == "test"


async def revoke_token(token_id: str, expires_at: datetime) -> None:
    """Revoke a JWT until its natural expiry."""
    ttl_seconds = max(int((expires_at - _utc_now()).total_seconds()), 1)
    try:
        redis = get_redis()
        await redis.set(_get_key(token_id), "revoked", ex=ttl_seconds)
    except RuntimeError:
        if not _is_test_mode():
            raise
        _memory_revoked_tokens[token_id] = expires_at


async def is_token_revoked(token_id: str) -> bool:
    """Check whether a JWT has been explicitly revoked."""
    try:
        redis = get_redis()
        value = await redis.get(_get_key(token_id))
        return bool(value)
    except RuntimeError:
        if not _is_test_mode():
            raise
        expires_at = _memory_revoked_tokens.get(token_id)
        if expires_at is None:
            return False
        if expires_at <= _utc_now():
            _memory_revoked_tokens.pop(token_id, None)
            return False
        return True
