"""
Response-level caching middleware.

Caches full HTTP JSON responses for GET requests on specified path prefixes.
Cache keys include the tenant ID (from JWT or header) and full query string.

Usage: add to app via ``app.add_middleware(ResponseCacheMiddleware, ...)``
"""

import hashlib
import json
import logging
import time
from typing import Optional

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

logger = logging.getLogger(__name__)

# Endpoint prefix → TTL in seconds
DEFAULT_CACHE_RULES: dict[str, int] = {
    "/api/v1/analytics/funnel": 300,          # 5 min
    "/api/v1/analytics/funnel/trend": 300,
    "/api/v1/analytics/funnel/by-source": 300,
    "/api/v1/analytics/cohorts": 600,         # 10 min
    "/api/v1/analytics/optimization": 300,
    "/api/v1/analytics/reports/daily": 120,   # 2 min
    "/api/v1/analytics/reports/weekly": 300,
    "/api/v1/analytics/salespeople": 300,
    "/api/v1/analytics/predictive/churn": 300,
    "/api/v1/analytics/predictive/lead-scores": 300,
    "/api/v1/analytics/predictive/retention": 300,
    "/api/v1/segments/distribution": 300,
    "/api/v1/segments/recommendations": 600,
}


class ResponseCacheMiddleware(BaseHTTPMiddleware):
    """
    Redis-backed GET response cache.

    Only caches GET requests that match configured path prefixes and return 200.
    Adds X-Cache: HIT/MISS header.
    """

    def __init__(self, app, cache_rules: Optional[dict[str, int]] = None):
        super().__init__(app)
        self.cache_rules = cache_rules or DEFAULT_CACHE_RULES

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint,
    ) -> Response:
        # Only cache GET requests
        if request.method != "GET":
            return await call_next(request)

        path = request.url.path
        ttl = self._match_ttl(path)
        if ttl is None:
            return await call_next(request)

        try:
            from src.infrastructure.redis_pool import get_redis_pool
            redis = get_redis_pool()
        except (RuntimeError, Exception):
            return await call_next(request)

        # Build cache key from path + query + tenant
        cache_key = self._build_key(request)

        # Check cache
        try:
            cached = await redis.get(cache_key)
            if cached is not None:
                data = json.loads(cached)
                response = JSONResponse(content=data["body"], status_code=data["status"])
                response.headers["X-Cache"] = "HIT"
                response.headers["X-Cache-TTL"] = str(ttl)
                return response
        except Exception as e:
            logger.debug("Cache read error: %s", e)

        # Cache miss — call the real handler
        response = await call_next(request)

        # Only cache successful JSON responses
        if response.status_code == 200 and hasattr(response, "body_iterator"):
            try:
                body_bytes = b""
                async for chunk in response.body_iterator:
                    if isinstance(chunk, str):
                        body_bytes += chunk.encode()
                    else:
                        body_bytes += chunk

                body_json = json.loads(body_bytes.decode())

                # Store in Redis
                cache_data = json.dumps({
                    "body": body_json,
                    "status": 200,
                    "cached_at": time.time(),
                }, default=str)
                await redis.setex(cache_key, ttl, cache_data)

                # Rebuild response (body_iterator is consumed)
                new_response = JSONResponse(content=body_json, status_code=200)
                # Copy original headers
                for key, value in response.headers.items():
                    if key.lower() not in ("content-length", "content-type"):
                        new_response.headers[key] = value
                new_response.headers["X-Cache"] = "MISS"
                new_response.headers["X-Cache-TTL"] = str(ttl)
                return new_response

            except Exception as e:
                logger.debug("Cache write error: %s", e)
                # Return original body if caching fails
                return JSONResponse(content=json.loads(body_bytes.decode()), status_code=200)

        return response

    def _match_ttl(self, path: str) -> Optional[int]:
        """Return TTL if the path matches a cache rule, else None."""
        for prefix, ttl in self.cache_rules.items():
            if path == prefix or path.startswith(prefix + "?"):
                return ttl
        return None

    def _build_key(self, request: Request) -> str:
        """Build deterministic cache key from request."""
        path = request.url.path
        query = str(sorted(request.query_params.items()))

        # Extract tenant_id from JWT or header
        tenant_id = ""
        auth_header = request.headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            try:
                from src.modules.auth.domain.auth_service import decode_access_token
                payload = decode_access_token(auth_header[7:])
                tenant_id = str(payload.tenant_id)
            except Exception:
                pass
        if not tenant_id:
            tenant_id = request.headers.get("x-tenant-id", "default")

        raw = f"{path}:{query}:{tenant_id}"
        key_hash = hashlib.md5(raw.encode()).hexdigest()
        return f"funnelier:cache:{key_hash}"

