"""
Usage enforcement middleware.

Tracks API calls per tenant and blocks requests when daily API limit is exceeded.
Lighter than the rate limiter — this is about billing/plan enforcement, not DDoS.
"""

import logging

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

logger = logging.getLogger(__name__)

# Paths that skip usage metering
_SKIP_PREFIXES = (
    "/health",
    "/api/docs",
    "/api/redoc",
    "/api/openapi.json",
    "/api/v1/webhooks",
    "/api/v1/auth",
)


class UsageEnforcementMiddleware(BaseHTTPMiddleware):
    """
    Counts API calls per tenant and enforces daily plan limits.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint,
    ) -> Response:
        path = request.url.path

        # Skip non-API / public paths
        if any(path.startswith(p) for p in _SKIP_PREFIXES):
            return await call_next(request)

        if not path.startswith("/api/"):
            return await call_next(request)

        # Extract tenant_id from JWT
        tenant_id = None
        plan = "professional"  # default; look up from cache/DB in production

        auth_header = request.headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            try:
                from src.modules.auth.domain.auth_service import decode_access_token
                payload = decode_access_token(auth_header[7:])
                tenant_id = payload.tenant_id
            except Exception:
                pass

        if tenant_id is None:
            return await call_next(request)

        # Increment and check
        try:
            from src.modules.tenants.application.billing_service import (
                UsageMeteringService,
                get_plan_limits,
            )
            count = await UsageMeteringService.increment_api_calls(tenant_id)
            limits = get_plan_limits(plan)

            if count > limits.max_api_calls_per_day:
                return JSONResponse(
                    status_code=429,
                    content={
                        "detail": "Daily API call limit exceeded for your plan",
                        "plan": plan,
                        "limit": limits.max_api_calls_per_day,
                        "current": count,
                        "upgrade_url": "/api/v1/tenants/me/billing/plans",
                    },
                )
        except Exception as e:
            logger.debug("Usage enforcement error: %s", e)

        return await call_next(request)

