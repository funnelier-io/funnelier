"""
Request logging middleware.

Assigns a unique ``request_id`` to each request, binds ``tenant_id`` and
``user_id`` from the JWT token into structlog context vars, and logs request
start / finish with duration.

All downstream loggers automatically inherit these context vars.
"""

import time
import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

logger = structlog.get_logger("request")

# Paths that produce minimal log output (avoid noise)
_QUIET_PREFIXES = ("/health", "/api/docs", "/api/redoc", "/api/openapi.json")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Structured request/response logger with context propagation."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint,
    ) -> Response:
        request_id = str(uuid.uuid4())[:8]
        path = request.url.path
        method = request.method

        # Extract auth context
        tenant_id = ""
        user_id = ""
        auth_header = request.headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            try:
                from src.modules.auth.domain.auth_service import decode_access_token
                payload = decode_access_token(auth_header[7:])
                tenant_id = str(payload.tenant_id)
                user_id = str(payload.sub)
            except Exception:
                pass

        # Bind context for all downstream loggers
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            method=method,
            path=path,
            tenant_id=tenant_id or None,
            user_id=user_id or None,
            client_ip=request.client.host if request.client else None,
        )

        # Add request_id to response headers for traceability
        quiet = any(path.startswith(p) for p in _QUIET_PREFIXES)

        if not quiet:
            logger.info("request_started")

        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception as exc:
            duration_ms = round((time.perf_counter() - start) * 1000, 1)
            logger.error(
                "request_failed",
                duration_ms=duration_ms,
                error=str(exc),
            )
            raise

        duration_ms = round((time.perf_counter() - start) * 1000, 1)
        status_code = response.status_code

        if not quiet:
            log_method = logger.warning if status_code >= 400 else logger.info
            log_method(
                "request_completed",
                status_code=status_code,
                duration_ms=duration_ms,
            )

        response.headers["X-Request-ID"] = request_id
        return response

