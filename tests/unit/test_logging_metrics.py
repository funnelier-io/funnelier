"""
Tests for Phase 29 — Structured Logging & Monitoring.
"""

import time
from unittest.mock import MagicMock

import pytest
import structlog


# ── Logging Setup Tests ─────────────────────────────


class TestLoggingSetup:
    def test_setup_logging_console(self):
        from src.core.logging import setup_logging
        # Should not raise
        setup_logging(log_level="DEBUG", json_format=False)

    def test_setup_logging_json(self):
        from src.core.logging import setup_logging
        setup_logging(log_level="INFO", json_format=True)

    def test_get_logger_returns_bound_logger(self):
        from src.core.logging import get_logger
        log = get_logger("test")
        assert log is not None

    def test_structlog_context_vars(self):
        """Context vars can be bound and cleared."""
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id="abc123")
        ctx = structlog.contextvars.get_contextvars()
        assert ctx.get("request_id") == "abc123"
        structlog.contextvars.clear_contextvars()
        ctx = structlog.contextvars.get_contextvars()
        assert "request_id" not in ctx


# ── Request Logging Middleware Tests ────────────────


class TestRequestLoggingMiddleware:
    def test_quiet_prefixes(self):
        from src.api.middleware.request_logging import _QUIET_PREFIXES
        assert "/health" in _QUIET_PREFIXES
        assert "/api/docs" in _QUIET_PREFIXES

    def test_middleware_class_exists(self):
        from src.api.middleware.request_logging import RequestLoggingMiddleware
        mw = RequestLoggingMiddleware(app=MagicMock())
        assert mw is not None


# ── Prometheus Metrics Tests ────────────────────────


class TestPrometheusMetrics:
    def test_record_request(self):
        from src.api.metrics import _Metrics
        m = _Metrics()
        m.record_request("GET", "/api/v1/analytics/funnel", 200, 0.5)
        assert m.request_count["GET_/api/v1/analytics/funnel"] == 1
        assert m.request_duration_sum["GET_/api/v1/analytics/funnel"] == 0.5
        assert m.status_count["200"] == 1

    def test_record_multiple_requests(self):
        from src.api.metrics import _Metrics
        m = _Metrics()
        m.record_request("GET", "/api/v1/leads/contacts", 200, 0.1)
        m.record_request("GET", "/api/v1/leads/contacts", 200, 0.2)
        m.record_request("POST", "/api/v1/leads/contacts", 201, 0.3)
        assert m.request_count["GET_/api/v1/leads/contacts"] == 2
        assert m.request_count["POST_/api/v1/leads/contacts"] == 1

    def test_5xx_counted_as_error(self):
        from src.api.metrics import _Metrics
        m = _Metrics()
        m.record_request("GET", "/api/v1/test", 500, 0.1)
        assert m.error_count["GET_/api/v1/test"] == 1
        m.record_request("GET", "/api/v1/test", 200, 0.1)
        assert m.error_count["GET_/api/v1/test"] == 1  # still 1

    def test_4xx_not_counted_as_error(self):
        from src.api.metrics import _Metrics
        m = _Metrics()
        m.record_request("GET", "/api/v1/test", 404, 0.1)
        assert m.error_count.get("GET_/api/v1/test", 0) == 0

    def test_uuid_path_bucketing(self):
        from src.api.metrics import _Metrics
        m = _Metrics()
        path = "/api/v1/leads/contacts/550e8400-e29b-41d4-a716-446655440000"
        bucket = m._bucket(path)
        assert "{id}" in bucket
        assert "550e8400" not in bucket

    def test_numeric_path_bucketing(self):
        from src.api.metrics import _Metrics
        m = _Metrics()
        bucket = m._bucket("/api/v1/page/42")
        assert "{n}" in bucket

    def test_render_prometheus_format(self):
        from src.api.metrics import _Metrics
        m = _Metrics()
        m.record_request("GET", "/health", 200, 0.01)
        output = m.render()
        assert "funnelier_uptime_seconds" in output
        assert "funnelier_http_requests_total" in output
        assert "funnelier_http_responses_total" in output
        assert "funnelier_http_errors_total" in output
        assert 'method="GET"' in output

    def test_render_empty_metrics(self):
        from src.api.metrics import _Metrics
        m = _Metrics()
        output = m.render()
        assert "funnelier_uptime_seconds" in output
        assert "funnelier_http_errors_total 0" in output

    def test_metrics_middleware_class(self):
        from src.api.metrics import MetricsMiddleware
        mw = MetricsMiddleware(app=MagicMock())
        assert mw is not None

    def test_uptime_increases(self):
        from src.api.metrics import _Metrics
        m = _Metrics()
        m.startup_time = time.time() - 100
        output = m.render()
        # uptime should be >= 100 seconds
        for line in output.split("\n"):
            if line.startswith("funnelier_uptime_seconds"):
                val = float(line.split()[-1])
                assert val >= 99

