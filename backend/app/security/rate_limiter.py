from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import Request

from app.config import get_settings
from app.core.exceptions import RateLimitExceededError
from app.core.redis_client import get_redis

RATE_LIMIT_PREFIX = "security:rate_limit"
_memory_buckets: dict[str, tuple[int, datetime]] = {}


@dataclass(slots=True)
class RateLimitDecision:
    allowed: bool
    limit: int
    remaining: int
    reset_seconds: int


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _is_test_mode() -> bool:
    return get_settings().APP_ENV == "test"


def parse_rate_limit(limit_expression: str) -> tuple[int, int]:
    """Parse expressions like `5/minute` or `100/hour`."""
    amount_text, window_text = [part.strip().lower() for part in limit_expression.split("/", maxsplit=1)]
    amount = int(amount_text)
    window_seconds = {
        "second": 1,
        "minute": 60,
        "hour": 3600,
        "day": 86400,
    }.get(window_text.rstrip("s"))
    if window_seconds is None:
        raise ValueError(f"Unsupported rate limit window: {window_text}")
    return amount, window_seconds


def build_bucket(scope: str, identifier: str) -> str:
    return f"{RATE_LIMIT_PREFIX}:{scope}:{identifier}"


def get_client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


class RateLimiter:
    """Redis-backed fixed-window rate limiter."""

    @classmethod
    async def check_limit(cls, bucket: str, limit_expression: str) -> RateLimitDecision:
        limit, window_seconds = parse_rate_limit(limit_expression)
        try:
            redis = get_redis()
            current_count = await redis.incr(bucket)
            if current_count == 1:
                await redis.expire(bucket, window_seconds)
            ttl = await redis.ttl(bucket)
            remaining = max(limit - current_count, 0)
            return RateLimitDecision(
                allowed=current_count <= limit,
                limit=limit,
                remaining=remaining,
                reset_seconds=max(ttl, 0),
            )
        except RuntimeError:
            if not _is_test_mode():
                raise
            count, expires_at = _memory_buckets.get(bucket, (0, _utc_now()))
            if expires_at <= _utc_now():
                count = 0
                expires_at = _utc_now() + timedelta(seconds=window_seconds)
            count += 1
            _memory_buckets[bucket] = (count, expires_at)
            remaining = max(limit - count, 0)
            reset_seconds = max(int((expires_at - _utc_now()).total_seconds()), 0)
            return RateLimitDecision(
                allowed=count <= limit,
                limit=limit,
                remaining=remaining,
                reset_seconds=reset_seconds,
            )

    @classmethod
    async def enforce(cls, bucket: str, limit_expression: str, details: dict[str, Any] | None = None) -> RateLimitDecision:
        decision = await cls.check_limit(bucket, limit_expression)
        if not decision.allowed:
            raise RateLimitExceededError(
                f"Rate limit exceeded for '{bucket}'.",
                details={
                    "bucket": bucket,
                    "limit": limit_expression,
                    "reset_seconds": decision.reset_seconds,
                    **(details or {}),
                },
            )
        return decision
