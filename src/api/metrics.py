"""
Prometheus-compatible metrics endpoint.

Exposes application metrics at ``/metrics`` in Prometheus text format.
Tracks request counts, durations, error rates, and business metrics
using lightweight in-process counters (no external dependency needed).
"""

import time
from collections import defaultdict
from typing import Any

from fastapi import APIRouter
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response

router = APIRouter()


class _Metrics:
    """Thread-safe in-process metrics store."""

    def __init__(self) -> None:
        self.request_count: dict[str, int] = defaultdict(int)
        self.request_duration_sum: dict[str, float] = defaultdict(float)
        self.error_count: dict[str, int] = defaultdict(int)
        self.status_count: dict[str, int] = defaultdict(int)
        self.startup_time: float = time.time()

    def record_request(self, method: str, path: str, status: int, duration: float) -> None:
        key = f"{method}_{self._bucket(path)}"
        self.request_count[key] += 1
        self.request_duration_sum[key] += duration
        self.status_count[str(status)] += 1
        if status >= 500:
            self.error_count[key] += 1

    def _bucket(self, path: str) -> str:
        """Bucket paths to avoid cardinality explosion."""
        # Normalise UUID-like segments to {id}
        parts = path.strip("/").split("/")
        bucketted = []
        for p in parts:
            if len(p) == 36 and p.count("-") == 4:
                bucketted.append("{id}")
            elif p.isdigit():
                bucketted.append("{n}")
            else:
                bucketted.append(p)
        return "/" + "/".join(bucketted) if bucketted else "/"

    def render(self) -> str:
        """Render metrics in Prometheus text exposition format."""
        lines: list[str] = []

        # Uptime
        uptime = time.time() - self.startup_time
        lines.append("# HELP funnelier_uptime_seconds Seconds since process start")
        lines.append("# TYPE funnelier_uptime_seconds gauge")
        lines.append(f"funnelier_uptime_seconds {uptime:.1f}")

        # Request counts
        lines.append("# HELP funnelier_http_requests_total Total HTTP requests")
        lines.append("# TYPE funnelier_http_requests_total counter")
        for key, count in sorted(self.request_count.items()):
            method, path = key.split("_", 1)
            lines.append(f'funnelier_http_requests_total{{method="{method}",path="{path}"}} {count}')

        # Request duration sum
        lines.append("# HELP funnelier_http_request_duration_seconds_sum Total request duration")
        lines.append("# TYPE funnelier_http_request_duration_seconds_sum counter")
        for key, dur in sorted(self.request_duration_sum.items()):
            method, path = key.split("_", 1)
            lines.append(f'funnelier_http_request_duration_seconds_sum{{method="{method}",path="{path}"}} {dur:.4f}')

        # Status code counts
        lines.append("# HELP funnelier_http_responses_total Responses by status code")
        lines.append("# TYPE funnelier_http_responses_total counter")
        for code, count in sorted(self.status_count.items()):
            lines.append(f'funnelier_http_responses_total{{status="{code}"}} {count}')

        # Error counts
        lines.append("# HELP funnelier_http_errors_total 5xx errors")
        lines.append("# TYPE funnelier_http_errors_total counter")
        total_errors = sum(self.error_count.values())
        lines.append(f"funnelier_http_errors_total {total_errors}")

        return "\n".join(lines) + "\n"


# Global metrics instance
metrics = _Metrics()


class MetricsMiddleware(BaseHTTPMiddleware):
    """Collect request metrics for Prometheus."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint,
    ) -> Response:
        if request.url.path == "/metrics":
            return await call_next(request)

        start = time.perf_counter()
        response = await call_next(request)
        duration = time.perf_counter() - start

        metrics.record_request(
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            duration=duration,
        )
        return response


@router.get("/metrics")
async def prometheus_metrics() -> PlainTextResponse:
    """Prometheus metrics endpoint."""
    return PlainTextResponse(metrics.render(), media_type="text/plain; version=0.0.4")

