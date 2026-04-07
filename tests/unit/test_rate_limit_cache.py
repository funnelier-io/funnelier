"""
Tests for Phase 27 — Rate Limiting, Caching & Import Throttling.
"""

import asyncio
import hashlib
import json
import time
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest


# ── Rate Limit Middleware Tests ─────────────────────


class TestRateLimitKeyResolution:
    """Test rate limit key resolution logic."""

    def test_skip_health_paths(self):
        from src.api.middleware.rate_limit import _SKIP_PREFIXES
        assert "/health" in _SKIP_PREFIXES
        assert "/api/docs" in _SKIP_PREFIXES
        assert "/api/v1/webhooks" in _SKIP_PREFIXES

    def test_auth_rate_limit_constant(self):
        from src.api.middleware.rate_limit import _AUTH_RATE_LIMIT, _AUTH_PREFIXES
        assert _AUTH_RATE_LIMIT == 20
        assert "/api/v1/auth/login" in _AUTH_PREFIXES

    def test_middleware_defaults(self):
        from src.api.middleware.rate_limit import RateLimitMiddleware
        mw = RateLimitMiddleware(app=MagicMock(), requests_per_minute=60)
        assert mw.rpm == 60
        assert mw.burst == 90  # 60 * 1.5
        assert mw.window == 60

    def test_burst_multiplier(self):
        from src.api.middleware.rate_limit import RateLimitMiddleware
        mw = RateLimitMiddleware(app=MagicMock(), requests_per_minute=100, burst_multiplier=2.0)
        assert mw.burst == 200


# ── Response Cache Middleware Tests ─────────────────


class TestResponseCacheMiddleware:
    """Test cache rules and key building."""

    def test_default_cache_rules_exist(self):
        from src.api.middleware.response_cache import DEFAULT_CACHE_RULES
        assert "/api/v1/analytics/funnel" in DEFAULT_CACHE_RULES
        assert "/api/v1/analytics/predictive/churn" in DEFAULT_CACHE_RULES
        assert "/api/v1/segments/distribution" in DEFAULT_CACHE_RULES

    def test_ttl_values(self):
        from src.api.middleware.response_cache import DEFAULT_CACHE_RULES
        assert DEFAULT_CACHE_RULES["/api/v1/analytics/funnel"] == 300
        assert DEFAULT_CACHE_RULES["/api/v1/analytics/reports/daily"] == 120
        assert DEFAULT_CACHE_RULES["/api/v1/analytics/cohorts"] == 600

    def test_match_ttl_exact_path(self):
        from src.api.middleware.response_cache import ResponseCacheMiddleware
        mw = ResponseCacheMiddleware(app=MagicMock())
        assert mw._match_ttl("/api/v1/analytics/funnel") == 300
        assert mw._match_ttl("/api/v1/unknown/path") is None

    def test_match_ttl_with_query(self):
        from src.api.middleware.response_cache import ResponseCacheMiddleware
        mw = ResponseCacheMiddleware(app=MagicMock())
        assert mw._match_ttl("/api/v1/analytics/funnel?start=2026-01-01") == 300

    def test_no_match_for_non_cached_paths(self):
        from src.api.middleware.response_cache import ResponseCacheMiddleware
        mw = ResponseCacheMiddleware(app=MagicMock())
        assert mw._match_ttl("/api/v1/leads/contacts") is None
        assert mw._match_ttl("/api/v1/auth/login") is None

    def test_custom_cache_rules(self):
        from src.api.middleware.response_cache import ResponseCacheMiddleware
        mw = ResponseCacheMiddleware(app=MagicMock(), cache_rules={"/custom": 60})
        assert mw._match_ttl("/custom") == 60
        assert mw._match_ttl("/api/v1/analytics/funnel") is None


# ── Cache Utility Tests ─────────────────────────────


class TestCacheUtils:
    """Test cache key building and serialisation helpers."""

    def test_build_cache_key_includes_prefix(self):
        from src.core.cache import _build_cache_key
        key = _build_cache_key("analytics", "get_funnel", {"tenant_id": "abc123"})
        assert key.startswith("funnelier:analytics:get_funnel:")
        assert "abc123" in key

    def test_build_cache_key_deterministic(self):
        from src.core.cache import _build_cache_key
        kwargs = {"tenant_id": "t1", "start_date": "2026-01-01", "end_date": "2026-01-31"}
        k1 = _build_cache_key("a", "f", kwargs)
        k2 = _build_cache_key("a", "f", kwargs)
        assert k1 == k2

    def test_build_cache_key_differs_by_args(self):
        from src.core.cache import _build_cache_key
        k1 = _build_cache_key("a", "f", {"tenant_id": "t1", "page": "1"})
        k2 = _build_cache_key("a", "f", {"tenant_id": "t1", "page": "2"})
        assert k1 != k2

    def test_build_cache_key_excludes_session(self):
        from src.core.cache import _build_cache_key
        k1 = _build_cache_key("a", "f", {"tenant_id": "t1", "session": "obj"})
        k2 = _build_cache_key("a", "f", {"tenant_id": "t1"})
        # session is excluded so keys should be same
        assert k1 == k2

    def test_serialise_dict(self):
        from src.core.cache import _serialise_result
        assert _serialise_result({"a": 1}) == {"a": 1}

    def test_serialise_list(self):
        from src.core.cache import _serialise_result
        result = _serialise_result([{"a": 1}, {"b": 2}])
        assert result == [{"a": 1}, {"b": 2}]

    def test_serialise_pydantic_model(self):
        from pydantic import BaseModel
        from src.core.cache import _serialise_result

        class Dummy(BaseModel):
            x: int = 5
            y: str = "hello"

        result = _serialise_result(Dummy())
        assert result == {"x": 5, "y": "hello"}


# ── Import Throttle Tests ───────────────────────────


class TestImportThrottle:
    """Test import throttle constants and structure."""

    def test_defaults(self):
        from src.api.middleware.import_throttle import (
            MAX_CONCURRENT_IMPORTS,
            MAX_IMPORTS_PER_HOUR,
            SEMAPHORE_TTL,
        )
        assert MAX_CONCURRENT_IMPORTS == 2
        assert MAX_IMPORTS_PER_HOUR == 30
        assert SEMAPHORE_TTL == 1800

    @pytest.mark.asyncio
    async def test_release_semaphore_handles_no_redis(self):
        """release_import_semaphore should not raise when Redis is unavailable."""
        from src.api.middleware.import_throttle import release_import_semaphore
        # Should not raise even without Redis
        await release_import_semaphore(uuid4())


# ── Redis Pool Tests ────────────────────────────────


class TestRedisPool:
    def test_get_pool_raises_before_init(self):
        from src.infrastructure.redis_pool import get_redis_pool, _pool
        import src.infrastructure.redis_pool as rp
        original = rp._pool
        rp._pool = None
        try:
            with pytest.raises(RuntimeError, match="not initialised"):
                get_redis_pool()
        finally:
            rp._pool = original


# ── Config Tests ────────────────────────────────────


class TestConfigRateLimiting:
    def test_rate_limit_settings(self):
        from src.core.config import settings
        assert settings.rate_limit_requests_per_minute == 100
        assert settings.import_max_concurrent == 2
        assert settings.import_max_per_hour == 30

    def test_redis_pool_size(self):
        from src.core.config import settings
        assert settings.redis.pool_size == 20

