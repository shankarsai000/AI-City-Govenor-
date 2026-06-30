"""
Distributed resource locking using Redis.

Design decisions:
1. SET NX EX pattern ensures atomicity of acquiring locks.
2. TTL-based expiry prevents deadlocks if a client fails or crashes.
3. Lock releasing is safeguarded using a Lua script to verify ownership
   (the holder ID) before deleting the key.
4. Active lock query endpoints support dashboard visibility.
"""
from typing import Any

from app.core.redis_client import get_redis
from app.core.logging import get_logger

logger = get_logger(__name__)

LOCK_PREFIX = "city:lock"

# Lua script to release lock atomically ONLY if the holder matches
RELEASE_LUA_SCRIPT = """
if redis.call('get', KEYS[1]) == ARGV[1] then
    return redis.call('del', KEYS[1])
else
    return 0
end
"""

class ResourceLock:
    """Distributed lock manager for city state resources."""

    @staticmethod
    def _get_key(resource_id: str) -> str:
        return f"{LOCK_PREFIX}:{resource_id}"

    @classmethod
    async def acquire(cls, resource_id: str, holder: str, ttl_seconds: int = 30) -> bool:
        """
        Acquire a lock on a specific resource.
        Returns True if successful, False if already locked.
        """
        redis = get_redis()
        key = cls._get_key(resource_id)
        
        # Try to set the key if it doesn't exist (NX) with expiration (EX)
        success = await redis.set(
            key, 
            holder, 
            nx=True, 
            ex=ttl_seconds
        )
        
        if success:
            logger.info("Resource lock acquired", resource_id=resource_id, holder=holder, ttl=ttl_seconds)
            return True
        
        logger.debug("Failed to acquire resource lock", resource_id=resource_id, holder=holder)
        return False

    @classmethod
    async def release(cls, resource_id: str, holder: str) -> bool:
        """
        Release a lock on a specific resource if caller is the holder.
        Returns True if released successfully, False otherwise.
        """
        redis = get_redis()
        key = cls._get_key(resource_id)
        
        # Use Lua script to release lock atomically only if holder matches
        result = await redis.eval(RELEASE_LUA_SCRIPT, 1, key, holder)
        success = bool(result)
        
        if success:
            logger.info("Resource lock released", resource_id=resource_id, holder=holder)
        else:
            logger.warning("Resource lock release rejected or already released", resource_id=resource_id, holder=holder)
        return success

    @classmethod
    async def is_locked(cls, resource_id: str) -> dict[str, Any] | None:
        """
        Check if a resource is locked.
        Returns LockInfo dict if locked, None otherwise.
        """
        redis = get_redis()
        key = cls._get_key(resource_id)
        value = await redis.get(key)
        
        if not value:
            return None
            
        return {
            "holder": value,
        }

    @classmethod
    async def force_release(cls, resource_id: str) -> bool:
        """Force release a lock (operator override)."""
        redis = get_redis()
        key = cls._get_key(resource_id)
        result = await redis.delete(key)
        logger.info("Resource lock force-released", resource_id=resource_id)
        return bool(result)

    @classmethod
    async def get_all_locks(cls) -> dict[str, dict[str, Any]]:
        """Get all active locks."""
        redis = get_redis()
        # Scan for keys matching pattern
        pattern = f"{LOCK_PREFIX}:*"
        keys = await redis.keys(pattern)
        
        locks = {}
        for key in keys:
            resource_id = key.replace(f"{LOCK_PREFIX}:", "")
            value = await redis.get(key)
            if value:
                locks[resource_id] = {"holder": value}
        return locks
