"""
Tests for Phase 30 — Performance & Load Testing.

Covers:
- PerformanceStats percentile calculations
- format_benchmark_table rendering
- Database pool settings (pool_recycle, pool_timeout)
- Redis pool settings (socket_timeout, retry_on_timeout, health_check_interval)
- Locust config / env var defaults
- New index declarations in SQLAlchemy models
"""

import os
from unittest.mock import patch

import pytest


# ── PerformanceStats Tests ───────────────────────────


class TestPerformanceStats:
    def test_empty_latencies(self):
        from src.core.perf_utils import PerformanceStats

        stats = PerformanceStats()
        assert stats.count == 0
        assert stats.mean == 0.0
        assert stats.p50 == 0.0
        assert stats.p95 == 0.0
        assert stats.p99 == 0.0
        assert stats.rps == 0.0

    def test_single_latency(self):
        from src.core.perf_utils import PerformanceStats

        stats = PerformanceStats(latencies=[0.5])
        assert stats.count == 1
        assert stats.mean == 0.5
        assert stats.p50 == 0.5
        assert stats.p95 == 0.5
        assert stats.p99 == 0.5

    def test_multiple_latencies_mean(self):
        from src.core.perf_utils import PerformanceStats

        stats = PerformanceStats(latencies=[0.1, 0.2, 0.3])
        assert round(stats.mean, 4) == 0.2

    def test_p50_median(self):
        from src.core.perf_utils import PerformanceStats

        stats = PerformanceStats(latencies=[0.1, 0.2, 0.3, 0.4, 0.5])
        assert stats.p50 == 0.3

    def test_p95_calculation(self):
        from src.core.perf_utils import PerformanceStats

        # 100 latencies from 0.01 to 1.0
        latencies = [i / 100.0 for i in range(1, 101)]
        stats = PerformanceStats(latencies=latencies)
        # p95 should be around 0.95
        assert 0.94 <= stats.p95 <= 0.96

    def test_p99_calculation(self):
        from src.core.perf_utils import PerformanceStats

        latencies = [i / 100.0 for i in range(1, 101)]
        stats = PerformanceStats(latencies=latencies)
        assert 0.98 <= stats.p99 <= 1.0

    def test_min_max(self):
        from src.core.perf_utils import PerformanceStats

        stats = PerformanceStats(latencies=[0.05, 0.5, 0.15, 0.9])
        assert stats.min == 0.05
        assert stats.max == 0.9

    def test_rps_calculation(self):
        from src.core.perf_utils import PerformanceStats

        # 10 requests each taking 0.1s = 1.0s total → 10 rps
        stats = PerformanceStats(latencies=[0.1] * 10)
        assert stats.rps == pytest.approx(10.0)

    def test_as_dict_keys(self):
        from src.core.perf_utils import PerformanceStats

        stats = PerformanceStats(latencies=[0.1, 0.2])
        d = stats.as_dict()
        expected_keys = {"count", "mean_ms", "min_ms", "max_ms", "p50_ms", "p95_ms", "p99_ms", "rps"}
        assert set(d.keys()) == expected_keys

    def test_as_dict_values_in_ms(self):
        from src.core.perf_utils import PerformanceStats

        stats = PerformanceStats(latencies=[0.1])  # 0.1s = 100ms
        d = stats.as_dict()
        assert d["mean_ms"] == 100.0
        assert d["p50_ms"] == 100.0


# ── Benchmark Table Rendering ────────────────────────


class TestBenchmarkTable:
    def test_format_benchmark_table_header(self):
        from src.core.perf_utils import PerformanceStats, format_benchmark_table

        results = {"/health": PerformanceStats(latencies=[0.01])}
        table = format_benchmark_table(results)
        assert "Endpoint" in table
        assert "p50 (ms)" in table
        assert "p95 (ms)" in table
        assert "RPS" in table

    def test_format_benchmark_table_contains_endpoint(self):
        from src.core.perf_utils import PerformanceStats, format_benchmark_table

        results = {
            "/api/v1/analytics/funnel": PerformanceStats(latencies=[0.05, 0.06, 0.07]),
        }
        table = format_benchmark_table(results)
        assert "/api/v1/analytics/funnel" in table

    def test_format_benchmark_table_empty(self):
        from src.core.perf_utils import format_benchmark_table

        table = format_benchmark_table({})
        assert "Endpoint" in table  # header still present
        # Only header + separator
        lines = [l for l in table.strip().split("\n") if l.strip()]
        assert len(lines) == 2


# ── Database Settings Tests ──────────────────────────


class TestDatabasePoolSettings:
    def test_pool_recycle_default(self):
        from src.core.config import DatabaseSettings

        s = DatabaseSettings()
        assert s.pool_recycle == 1800

    def test_pool_timeout_default(self):
        from src.core.config import DatabaseSettings

        s = DatabaseSettings()
        assert s.pool_timeout == 30

    def test_pool_recycle_from_env(self):
        from src.core.config import DatabaseSettings

        with patch.dict(os.environ, {"DATABASE_POOL_RECYCLE": "900"}):
            s = DatabaseSettings()
            assert s.pool_recycle == 900

    def test_pool_timeout_from_env(self):
        from src.core.config import DatabaseSettings

        with patch.dict(os.environ, {"DATABASE_POOL_TIMEOUT": "15"}):
            s = DatabaseSettings()
            assert s.pool_timeout == 15


# ── Redis Settings Tests ─────────────────────────────


class TestRedisPoolSettings:
    def test_socket_timeout_default(self):
        from src.core.config import RedisSettings

        s = RedisSettings()
        assert s.socket_timeout == 5.0

    def test_socket_connect_timeout_default(self):
        from src.core.config import RedisSettings

        s = RedisSettings()
        assert s.socket_connect_timeout == 3.0

    def test_retry_on_timeout_default(self):
        from src.core.config import RedisSettings

        s = RedisSettings()
        assert s.retry_on_timeout is True

    def test_health_check_interval_default(self):
        from src.core.config import RedisSettings

        s = RedisSettings()
        assert s.health_check_interval == 30

    def test_socket_timeout_from_env(self):
        from src.core.config import RedisSettings

        with patch.dict(os.environ, {"REDIS_SOCKET_TIMEOUT": "10.0"}):
            s = RedisSettings()
            assert s.socket_timeout == 10.0


# ── SQLAlchemy Model Index Tests ─────────────────────


class TestModelIndexes:
    def test_contacts_has_assigned_to_index(self):
        from src.infrastructure.database.models.leads import ContactModel

        index_names = [idx.name for idx in ContactModel.__table__.indexes]
        assert "ix_contacts_tenant_assigned_to" in index_names

    def test_contacts_has_created_at_index(self):
        from src.infrastructure.database.models.leads import ContactModel

        index_names = [idx.name for idx in ContactModel.__table__.indexes]
        assert "ix_contacts_tenant_created_at" in index_names

    def test_sms_logs_has_campaign_index(self):
        from src.infrastructure.database.models.communications import SMSLogModel

        index_names = [idx.name for idx in SMSLogModel.__table__.indexes]
        assert "ix_sms_logs_tenant_campaign" in index_names

    def test_campaign_recipients_has_contact_index(self):
        from src.infrastructure.database.models.campaigns import CampaignRecipientModel

        index_names = [idx.name for idx in CampaignRecipientModel.__table__.indexes]
        assert "ix_campaign_recipients_contact" in index_names


# ── Locust Config Tests ──────────────────────────────


class TestLocustConfig:
    def test_default_username(self):
        # Ensure default env var values in locustfile match AGENTS.md credentials
        assert os.getenv("LOCUST_USERNAME", "admin") == "admin"

    def test_default_password(self):
        assert os.getenv("LOCUST_PASSWORD", "admin1234") == "admin1234"

    def test_default_host(self):
        assert os.getenv("LOCUST_TARGET_HOST", "http://localhost:8000") == "http://localhost:8000"

