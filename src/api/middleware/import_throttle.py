"""
Import endpoint throttling.

Limits concurrent imports per tenant using a Redis-based semaphore and also
applies a stricter per-tenant hourly rate limit for import operations.

Usage as a FastAPI dependency:
    dependencies=[Depends(import_throttle)]
"""

import logging
import time
from uuid import UUID

from fastapi import Depends, HTTPException

from src.api.dependencies import get_current_tenant_id
from src.core.config import settings

logger = logging.getLogger(__name__)

# Defaults — overridable via settings
MAX_CONCURRENT_IMPORTS = 2
MAX_IMPORTS_PER_HOUR = 30
SEMAPHORE_TTL = 1800  # 30 min safety expiry for stuck imports


async def import_throttle(
    tenant_id: UUID = Depends(get_current_tenant_id),
) -> None:
    """
    Dependency that enforces:
    1. Max concurrent imports per tenant (semaphore).
    2. Hourly import rate limit per tenant.

    Raises HTTP 429 if either limit is exceeded.
    """
    try:
        from src.infrastructure.redis_pool import get_redis_pool
        redis = get_redis_pool()
    except RuntimeError:
        # Redis not available — skip throttling
        return

    max_concurrent = getattr(settings, "import_max_concurrent", MAX_CONCURRENT_IMPORTS)
    max_per_hour = getattr(settings, "import_max_per_hour", MAX_IMPORTS_PER_HOUR)

    sem_key = f"import_semaphore:{tenant_id}"
    rate_key = f"import_rate:{tenant_id}:{int(time.time() // 3600)}"

    try:
        # 1. Check concurrent imports (semaphore)
        current_concurrent = await redis.get(sem_key)
        if current_concurrent and int(current_concurrent) >= max_concurrent:
            raise HTTPException(
                status_code=429,
                detail=f"Maximum {max_concurrent} concurrent imports per tenant. Please wait for current imports to finish.",
            )

        # 2. Check hourly rate
        hourly_count = await redis.get(rate_key)
        if hourly_count and int(hourly_count) >= max_per_hour:
            raise HTTPException(
                status_code=429,
                detail=f"Import limit of {max_per_hour}/hour exceeded. Please try again later.",
            )

        # Increment semaphore and hourly counter
        pipe = redis.pipeline(transaction=True)
        pipe.incr(sem_key)
        pipe.expire(sem_key, SEMAPHORE_TTL)
        pipe.incr(rate_key)
        pipe.expire(rate_key, 3660)  # 1 hour + 1 min buffer
        await pipe.execute()

    except HTTPException:
        raise
    except Exception as e:
        logger.warning("Import throttle Redis error: %s", e)
        # Don't block on Redis errors


async def release_import_semaphore(tenant_id: UUID) -> None:
    """
    Decrement the import semaphore after an import completes (success or failure).
    Call this from the import endpoint's finally block.
    """
    try:
        from src.infrastructure.redis_pool import get_redis_pool
        redis = get_redis_pool()
        sem_key = f"import_semaphore:{tenant_id}"
        current = await redis.get(sem_key)
        if current and int(current) > 0:
            await redis.decr(sem_key)
    except Exception as e:
        logger.warning("Failed to release import semaphore: %s", e)

