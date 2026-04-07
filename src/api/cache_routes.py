"""
Cache Management API Routes

Admin endpoints for inspecting and invalidating the response cache.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from src.api.dependencies import get_current_tenant_id

router = APIRouter(prefix="/cache", tags=["cache"])


@router.delete("/invalidate")
async def invalidate_cache(
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
    prefix: str = "*",
):
    """Invalidate cached responses for the current tenant."""
    from src.core.cache import invalidate_tenant_cache
    deleted = await invalidate_tenant_cache(tenant_id, prefix)
    return {"deleted": deleted, "tenant_id": str(tenant_id), "prefix": prefix}


@router.get("/stats")
async def cache_stats(
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
):
    """Get cache statistics."""
    try:
        from src.infrastructure.redis_pool import get_redis_pool
        redis = get_redis_pool()

        info = await redis.info("memory")
        db_size = await redis.dbsize()

        # Count funnelier cache keys
        cache_count = 0
        cursor = "0"
        while True:
            cursor, keys = await redis.scan(cursor=cursor, match="funnelier:cache:*", count=200)
            cache_count += len(keys)
            if cursor == "0" or cursor == 0:
                break

        return {
            "cache_keys": cache_count,
            "total_keys": db_size,
            "used_memory": info.get("used_memory_human", "N/A"),
            "used_memory_peak": info.get("used_memory_peak_human", "N/A"),
        }
    except Exception as e:
        return {"error": str(e)}

