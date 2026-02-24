"""
Unit Tests for Celery Tasks

Tests task logic without requiring Celery broker or database.
Uses mocking to isolate task functions.
"""

import base64
import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest


# ─── Phone Normalization ────────────────────────────────────────────────────

class TestPhoneNormalization:
    """Tests for phone normalization used in tasks."""

    def test_normalize_10_digit(self):
        from src.infrastructure.messaging.tasks import _normalize_phone
        assert _normalize_phone("9123456789") == "9123456789"

    def test_normalize_11_digit_with_zero(self):
        from src.infrastructure.messaging.tasks import _normalize_phone
        assert _normalize_phone("09123456789") == "9123456789"

    def test_normalize_12_digit_with_98(self):
        from src.infrastructure.messaging.tasks import _normalize_phone
        assert _normalize_phone("989123456789") == "9123456789"

    def test_normalize_with_plus_98(self):
        from src.infrastructure.messaging.tasks import _normalize_phone
        assert _normalize_phone("+989123456789") == "9123456789"

    def test_normalize_invalid_short(self):
        from src.infrastructure.messaging.tasks import _normalize_phone
        assert _normalize_phone("12345") is None

    def test_normalize_empty(self):
        from src.infrastructure.messaging.tasks import _normalize_phone
        assert _normalize_phone("") is None

    def test_normalize_non_mobile(self):
        from src.infrastructure.messaging.tasks import _normalize_phone
        # Landline starting with 2 (not 9)
        assert _normalize_phone("02112345678") is None

    def test_normalize_with_dashes(self):
        from src.infrastructure.messaging.tasks import _normalize_phone
        assert _normalize_phone("0912-345-6789") == "9123456789"


# ─── Helper Function Tests ──────────────────────────────────────────────────

class TestHelperFunctions:
    """Tests for task helper functions."""

    def test_extract_salesperson_with_dash(self):
        from src.infrastructure.messaging.tasks import _extract_salesperson
        assert _extract_salesperson(
            "report_All_01_Mar-16_Feb - asadollahi.csv") == "asadollahi"

    def test_extract_salesperson_no_dash(self):
        from src.infrastructure.messaging.tasks import _extract_salesperson
        assert _extract_salesperson("some_file.csv") == "some_file"

    def test_find_phone_column_by_name(self):
        import pandas as pd
        from src.infrastructure.messaging.tasks import _find_phone_column
        df = pd.DataFrame({"نام": ["علی"], "شماره": ["09123456789"]})
        assert _find_phone_column(df) == "شماره"

    def test_find_phone_column_by_content(self):
        import pandas as pd
        from src.infrastructure.messaging.tasks import _find_phone_column
        df = pd.DataFrame({
            "col_a": ["text1"] * 10,
            "col_b": [f"0912345678{i}" for i in range(10)],
        })
        assert _find_phone_column(df) == "col_b"

    def test_find_phone_column_not_found(self):
        import pandas as pd
        from src.infrastructure.messaging.tasks import _find_phone_column
        df = pd.DataFrame({"name": ["Ali"], "city": ["Tehran"]})
        assert _find_phone_column(df) is None

    def test_find_name_column(self):
        import pandas as pd
        from src.infrastructure.messaging.tasks import _find_name_column
        df = pd.DataFrame({"نام": ["علی"], "phone": ["09123456789"]})
        assert _find_name_column(df) == "نام"

    def test_find_column_generic(self):
        import pandas as pd
        from src.infrastructure.messaging.tasks import _find_column
        df = pd.DataFrame({"Duration": [120], "phone": ["091"]})
        assert _find_column(df, ["duration", "مدت"]) == "Duration"


# ─── WebSocket Notification ─────────────────────────────────────────────────

class TestWSNotification:
    """Tests for WebSocket notification helper."""

    @patch("redis.Redis")
    def test_notify_ws_publishes_to_redis(self, mock_redis_cls):
        from src.infrastructure.messaging.tasks import _notify_ws

        mock_client = MagicMock()
        mock_redis_cls.from_url.return_value = mock_client

        _notify_ws("test_event", {"key": "value"})

        mock_redis_cls.from_url.assert_called_once()
        mock_client.publish.assert_called_once()
        call_args = mock_client.publish.call_args
        assert call_args[0][0] == "funnelier:ws:events"
        data = json.loads(call_args[0][1])
        assert data["type"] == "test_event"
        assert data["payload"]["key"] == "value"

    @patch("redis.Redis")
    def test_notify_ws_handles_error(self, mock_redis_cls):
        from src.infrastructure.messaging.tasks import _notify_ws

        mock_redis_cls.from_url.side_effect = Exception("connection refused")
        # Should not raise
        _notify_ws("test_event", {"key": "value"})


# ─── Celery App Configuration ───────────────────────────────────────────────

class TestCeleryAppConfig:
    """Tests for Celery app configuration."""

    def test_celery_app_exists(self):
        from src.infrastructure.messaging.celery_app import celery_app
        assert celery_app is not None
        assert celery_app.main == "funnelier"

    def test_celery_beat_schedule_has_daily_funnel(self):
        from src.infrastructure.messaging.celery_app import celery_app
        schedule = celery_app.conf.beat_schedule
        assert "daily-funnel-snapshot" in schedule
        assert schedule["daily-funnel-snapshot"]["task"] == \
            "src.infrastructure.messaging.tasks.calculate_daily_funnel_snapshot"

    def test_celery_beat_schedule_has_rfm(self):
        from src.infrastructure.messaging.celery_app import celery_app
        schedule = celery_app.conf.beat_schedule
        assert "daily-rfm-calculation" in schedule

    def test_celery_beat_schedule_has_alerts(self):
        from src.infrastructure.messaging.celery_app import celery_app
        schedule = celery_app.conf.beat_schedule
        assert "hourly-alert-check" in schedule

    def test_celery_beat_schedule_has_daily_report(self):
        from src.infrastructure.messaging.celery_app import celery_app
        schedule = celery_app.conf.beat_schedule
        assert "daily-report" in schedule

    def test_celery_task_routes(self):
        from src.infrastructure.messaging.celery_app import celery_app
        routes = celery_app.conf.task_routes
        assert "src.infrastructure.messaging.tasks.import_*" in routes
        assert routes["src.infrastructure.messaging.tasks.import_*"]["queue"] == "imports"


# ─── Task Registration ──────────────────────────────────────────────────────

class TestTaskRegistration:
    """Verify all tasks are properly registered."""

    def test_import_leads_excel_is_registered(self):
        from src.infrastructure.messaging.tasks import import_leads_excel
        assert import_leads_excel.name == \
            "src.infrastructure.messaging.tasks.import_leads_excel"

    def test_import_call_logs_csv_is_registered(self):
        from src.infrastructure.messaging.tasks import import_call_logs_csv
        assert import_call_logs_csv.name == \
            "src.infrastructure.messaging.tasks.import_call_logs_csv"

    def test_import_sms_logs_csv_is_registered(self):
        from src.infrastructure.messaging.tasks import import_sms_logs_csv
        assert import_sms_logs_csv.name == \
            "src.infrastructure.messaging.tasks.import_sms_logs_csv"

    def test_import_voip_json_is_registered(self):
        from src.infrastructure.messaging.tasks import import_voip_json
        assert import_voip_json.name == \
            "src.infrastructure.messaging.tasks.import_voip_json"

    def test_calculate_daily_funnel_snapshot_is_registered(self):
        from src.infrastructure.messaging.tasks import calculate_daily_funnel_snapshot
        assert calculate_daily_funnel_snapshot.name == \
            "src.infrastructure.messaging.tasks.calculate_daily_funnel_snapshot"

    def test_calculate_rfm_segments_is_registered(self):
        from src.infrastructure.messaging.tasks import calculate_rfm_segments
        assert calculate_rfm_segments.name == \
            "src.infrastructure.messaging.tasks.calculate_rfm_segments"

    def test_check_alerts_is_registered(self):
        from src.infrastructure.messaging.tasks import check_alerts
        assert check_alerts.name == \
            "src.infrastructure.messaging.tasks.check_alerts"

    def test_generate_daily_report_is_registered(self):
        from src.infrastructure.messaging.tasks import generate_daily_report
        assert generate_daily_report.name == \
            "src.infrastructure.messaging.tasks.generate_daily_report"

    def test_sync_mongodb_invoices_is_registered(self):
        from src.infrastructure.messaging.tasks import sync_mongodb_invoices
        assert sync_mongodb_invoices.name == \
            "src.infrastructure.messaging.tasks.sync_mongodb_invoices"

    def test_send_sms_notification_is_registered(self):
        from src.infrastructure.messaging.tasks import send_sms_notification
        assert send_sms_notification.name == \
            "src.infrastructure.messaging.tasks.send_sms_notification"

