"""
Response caching utilities.

Provides a Redis-backed cache decorator for expensive API endpoints and
a helper to invalidate cached responses when underlying data changes.

Usage on an endpoint:
    @router.get("/metrics")
    @cached(ttl=300, prefix="analytics")
    async def get_metrics(tenant_id: ..., session: ...):
        ...

Cache invalidation after data writes:
    await invalidate_tenant_cache(tenant_id, "analytics")
"""

import functools
import hashlib
import json
import logging
from typing import Any, Callable, Optional
from uuid import UUID

logger = logging.getLogger(__name__)


def cached(ttl: int = 300, prefix: str = "api") -> Callable:
    """
    Decorator that caches endpoint JSON responses in Redis.

    Cache key: ``funnelier:{prefix}:{func_name}:{hash_of_args}``

    Parameters
    ----------
    ttl : time-to-live in seconds (default 5 min)
    prefix : key namespace (e.g. "analytics", "segments")
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                from src.infrastructure.redis_pool import get_redis_pool
                redis = get_redis_pool()
            except (RuntimeError, Exception):
                # Redis unavailable — just call the function
                return await func(*args, **kwargs)

            # Build a deterministic cache key from the function arguments
            cache_key = _build_cache_key(prefix, func.__name__, kwargs)

            try:
                # Check cache
                cached_value = await redis.get(cache_key)
                if cached_value is not None:
                    logger.debug("Cache hit: %s", cache_key)
                    return json.loads(cached_value)
            except Exception as e:
                logger.warning("Cache read error: %s", e)

            # Cache miss — call the real function
            result = await func(*args, **kwargs)

            try:
                # Pydantic models → dict for JSON serialisation
                serialised = _serialise_result(result)
                await redis.setex(cache_key, ttl, json.dumps(serialised, default=str))
                logger.debug("Cache set: %s (ttl=%d)", cache_key, ttl)
            except Exception as e:
                logger.warning("Cache write error: %s", e)

            return result

        return wrapper

    return decorator


async def invalidate_tenant_cache(
    tenant_id: UUID | str,
    prefix: str = "*",
) -> int:
    """
    Delete all cached keys for a tenant matching the given prefix.

    Parameters
    ----------
    tenant_id : tenant whose cache to clear
    prefix : cache prefix to invalidate (e.g. "analytics")
             Use "*" to clear everything for the tenant.

    Returns
    -------
    int : number of keys deleted
    """
    try:
        from src.infrastructure.redis_pool import get_redis_pool
        redis = get_redis_pool()
    except (RuntimeError, Exception):
        return 0

    pattern = f"funnelier:{prefix}:*{tenant_id}*"
    deleted = 0

    try:
        cursor = "0"
        while True:
            cursor, keys = await redis.scan(cursor=cursor, match=pattern, count=100)
            if keys:
                await redis.delete(*keys)
                deleted += len(keys)
            if cursor == "0" or cursor == 0:
                break

        if deleted:
            logger.info("Invalidated %d cache keys for tenant %s (prefix=%s)", deleted, tenant_id, prefix)
    except Exception as e:
        logger.warning("Cache invalidation error: %s", e)

    return deleted


async def invalidate_all_cache() -> int:
    """Delete ALL Funnelier cache keys. Use sparingly."""
    try:
        from src.infrastructure.redis_pool import get_redis_pool
        redis = get_redis_pool()
    except (RuntimeError, Exception):
        return 0

    deleted = 0
    try:
        cursor = "0"
        while True:
            cursor, keys = await redis.scan(cursor=cursor, match="funnelier:*", count=200)
            if keys:
                await redis.delete(*keys)
                deleted += len(keys)
            if cursor == "0" or cursor == 0:
                break
        logger.info("Invalidated %d total cache keys", deleted)
    except Exception as e:
        logger.warning("Full cache invalidation error: %s", e)

    return deleted


# ── Internal helpers ──────────────────────────────────


def _build_cache_key(prefix: str, func_name: str, kwargs: dict[str, Any]) -> str:
    """Build a deterministic cache key from function arguments."""
    # Extract tenant_id if present (for per-tenant keying)
    tenant_id = ""
    for key in ("tenant_id", "x_tenant_id"):
        if key in kwargs:
            tenant_id = str(kwargs[key])
            break

    # Hash remaining arguments for uniqueness
    args_repr = {
        k: str(v) for k, v in sorted(kwargs.items())
        if k not in ("session", "request", "response") and v is not None
    }
    args_hash = hashlib.md5(json.dumps(args_repr, sort_keys=True).encode()).hexdigest()[:12]

    return f"funnelier:{prefix}:{func_name}:{tenant_id}:{args_hash}"


def _serialise_result(result: Any) -> Any:
    """Convert a Pydantic model or dict to JSON-serialisable form."""
    if hasattr(result, "model_dump"):
        return result.model_dump(mode="json")
    if hasattr(result, "dict"):
        return result.dict()
    if isinstance(result, dict):
        return result
    if isinstance(result, list):
        return [_serialise_result(item) for item in result]
    return result

