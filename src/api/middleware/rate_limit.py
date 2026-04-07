"""
Per-tenant API rate limiting middleware.

Uses Redis sliding-window counters keyed by tenant_id (from JWT) or client IP
for unauthenticated requests.  Returns 429 with Retry-After and X-RateLimit-*
headers when the limit is exceeded.

Skips: /health, /api/docs, /api/redoc, /api/openapi.json, webhooks.
"""

import logging
import time
from typing import Optional

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

logger = logging.getLogger(__name__)

# Paths that bypass rate limiting entirely
_SKIP_PREFIXES = (
    "/health",
    "/api/docs",
    "/api/redoc",
    "/api/openapi.json",
    "/api/v1/webhooks",
)

# Stricter per-IP limit for auth endpoints (brute-force protection)
_AUTH_PREFIXES = ("/api/v1/auth/login", "/api/v1/auth/register")
_AUTH_RATE_LIMIT = 20  # per minute


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Sliding-window Redis rate limiter.

    Parameters
    ----------
    app : ASGI app
    requests_per_minute : default per-tenant limit
    burst_multiplier : multiplier applied on top of base limit for short bursts
    """

    def __init__(
        self,
        app,
        requests_per_minute: int = 100,
        burst_multiplier: float = 1.5,
    ):
        super().__init__(app)
        self.rpm = requests_per_minute
        self.burst = int(requests_per_minute * burst_multiplier)
        self.window = 60  # seconds

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint,
    ) -> Response:
        path = request.url.path

        # Skip paths that don't need rate limiting
        if any(path.startswith(p) for p in _SKIP_PREFIXES):
            return await call_next(request)

        # Determine key and limit
        key, limit = self._resolve_key_and_limit(request)

        if key is None:
            # No key could be resolved — let the request through
            return await call_next(request)

        try:
            from src.infrastructure.redis_pool import get_redis_pool
            redis = get_redis_pool()
        except RuntimeError:
            # Redis not ready — don't block requests
            return await call_next(request)

        now = time.time()
        window_key = f"ratelimit:{key}:{int(now // self.window)}"

        try:
            pipe = redis.pipeline(transaction=True)
            pipe.incr(window_key)
            pipe.expire(window_key, self.window + 5)
            results = await pipe.execute()
            current_count = results[0]
        except Exception as e:
            logger.warning("Rate limit Redis error: %s", e)
            return await call_next(request)

        # Set rate-limit headers
        remaining = max(0, limit - current_count)
        response = await call_next(request) if current_count <= limit else None

        if response is None:
            retry_after = self.window - int(now % self.window)
            response = JSONResponse(
                status_code=429,
                content={
                    "detail": "Rate limit exceeded",
                    "retry_after": retry_after,
                },
            )
            response.headers["Retry-After"] = str(retry_after)
            remaining = 0

        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(int((now // self.window + 1) * self.window))
        return response

    def _resolve_key_and_limit(self, request: Request) -> tuple[Optional[str], int]:
        """Determine the rate-limit key (tenant or IP) and the applicable limit."""
        path = request.url.path

        # Auth endpoints: IP-based, stricter limit
        if any(path.startswith(p) for p in _AUTH_PREFIXES):
            client_ip = request.client.host if request.client else "unknown"
            return f"ip:{client_ip}", _AUTH_RATE_LIMIT

        # Try to extract tenant_id from JWT
        auth_header = request.headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
            try:
                from src.modules.auth.domain.auth_service import decode_access_token
                payload = decode_access_token(token)
                return f"tenant:{payload.tenant_id}", self.rpm
            except Exception:
                pass

        # Fall back to IP-based limiting for unauthenticated requests
        client_ip = request.client.host if request.client else "unknown"
        return f"ip:{client_ip}", self.rpm

