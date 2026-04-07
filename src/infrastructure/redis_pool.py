"""
Shared async Redis connection pool.

Centralizes Redis connections used by rate-limiting, caching, WebSocket pub/sub, etc.
Initialised once during app lifespan and closed on shutdown.
"""

import logging
from typing import Optional

import redis.asyncio as aioredis

from src.core.config import settings

logger = logging.getLogger(__name__)

_pool: Optional[aioredis.Redis] = None


async def init_redis_pool() -> aioredis.Redis:
    """Create and return the shared Redis client backed by a connection pool."""
    global _pool
    if _pool is None:
        _pool = aioredis.from_url(
            settings.redis.url,
            decode_responses=True,
            max_connections=settings.redis.pool_size,
        )
        # Verify connectivity
        try:
            await _pool.ping()
            logger.info("Redis pool initialised (%s)", settings.redis.url)
        except Exception as e:
            logger.warning("Redis pool ping failed: %s", e)
    return _pool


async def close_redis_pool() -> None:
    """Gracefully close the shared Redis pool."""
    global _pool
    if _pool is not None:
        await _pool.aclose()  # type: ignore[union-attr]
        _pool = None
        logger.info("Redis pool closed")


def get_redis_pool() -> aioredis.Redis:
    """Return the current pool. Raises if not initialised."""
    if _pool is None:
        raise RuntimeError("Redis pool not initialised — call init_redis_pool() first")
    return _pool

