"""
Tests for Analytics Module — Sprint 2 P1 Gap Closure.

Covers:
- FunnelStageConfig, ContactFunnelProgress, DailyFunnelSnapshot entities
- FunnelMetrics calculation (conversion rates)
- CohortAnalysis, SalespersonMetrics, AlertRule, AlertInstance entities
- Analytics API schemas
"""

import pytest
from datetime import datetime, timedelta
from uuid import UUID, uuid4

from src.core.domain import FunnelStage
from src.modules.analytics.domain.entities import (
    FunnelStageConfig,
    ContactFunnelProgress,
    FunnelMetrics,
    DailyFunnelSnapshot,
    CohortAnalysis,
    SalespersonMetrics,
    AlertRule,
    AlertInstance,
)
from src.modules.analytics.api.schemas import (
    StageCountSchema,
    ConversionRateSchema,
    FunnelMetricsResponse,
    DailySnapshotSchema,
    FunnelTrendResponse,
)

TENANT_ID = UUID("00000000-0000-0000-0000-000000000001")


# ═══════════════════════════════════════════════════════════════════
# FunnelStageConfig Entity
# ═══════════════════════════════════════════════════════════════════


class TestFunnelStageConfig:
    def test_creation(self):
        config = FunnelStageConfig(
            tenant_id=TENANT_ID,
            name="call_answered",
            display_name="تماس پاسخ‌داده",
            order=5,
            criteria_type="threshold_based",
            criteria_config={"min_duration": 90},
            min_value=90.0,
            value_field="call_duration",
            color="#22C55E",
        )
        assert config.order == 5
        assert config.criteria_type == "threshold_based"
        assert config.is_active is True


# ═══════════════════════════════════════════════════════════════════
# ContactFunnelProgress Entity
# ═══════════════════════════════════════════════════════════════════


class TestContactFunnelProgress:
    def _make_progress(self) -> ContactFunnelProgress:
        return ContactFunnelProgress(
            tenant_id=TENANT_ID,
            contact_id=uuid4(),
            phone_number="9121234567",
        )

    def test_default_stage_is_lead_acquired(self):
        p = self._make_progress()
        assert p.current_stage == FunnelStage.LEAD_ACQUIRED
        assert p.is_converted is False

    def test_progress_to_stage(self):
        p = self._make_progress()
        p.progress_to_stage(FunnelStage.SMS_SENT)
        assert p.current_stage == FunnelStage.SMS_SENT
        assert len(p.stage_history) == 1
        assert p.stage_history[0]["stage"] == "sms_sent"

    def test_progress_through_multiple_stages(self):
        p = self._make_progress()
        p.progress_to_stage(FunnelStage.SMS_SENT)
        p.progress_to_stage(FunnelStage.CALL_ATTEMPTED)
        p.progress_to_stage(FunnelStage.CALL_ANSWERED)
        assert p.current_stage == FunnelStage.CALL_ANSWERED
        assert len(p.stage_history) == 3

    def test_progress_to_payment_marks_converted(self):
        p = self._make_progress()
        p.progress_to_stage(FunnelStage.SMS_SENT)
        p.progress_to_stage(FunnelStage.PAYMENT_RECEIVED)
        assert p.is_converted is True
        assert p.converted_at is not None
        assert p.days_to_convert is not None

    def test_stage_history_records_exit(self):
        p = self._make_progress()
        p.progress_to_stage(FunnelStage.SMS_SENT)
        p.progress_to_stage(FunnelStage.CALL_ATTEMPTED)
        # First entry should have exited_at and duration
        assert p.stage_history[0]["exited_at"] is not None
        assert p.stage_history[0]["duration_seconds"] is not None

    def test_get_stage_duration_returns_none_for_missing(self):
        p = self._make_progress()
        assert p.get_stage_duration(FunnelStage.INVOICE_ISSUED) is None


# ═══════════════════════════════════════════════════════════════════
# FunnelMetrics
# ═══════════════════════════════════════════════════════════════════


class TestFunnelMetrics:
    def _make_metrics(self) -> FunnelMetrics:
        return FunnelMetrics(
            period_start=datetime.utcnow() - timedelta(days=30),
            period_end=datetime.utcnow(),
            tenant_id=TENANT_ID,
            stage_counts={
                "lead_acquired": 1000,
                "sms_sent": 800,
                "sms_delivered": 700,
                "call_attempted": 300,
                "call_answered": 150,
                "invoice_issued": 80,
                "payment_received": 50,
            },
            total_leads=1000,
            total_conversions=50,
        )

    def test_calculate_conversion_rates(self):
        m = self._make_metrics()
        m.calculate_conversion_rates()

        assert "lead_acquired_to_sms_sent" in m.stage_conversion_rates
        assert m.stage_conversion_rates["lead_acquired_to_sms_sent"] == 0.8
        assert m.stage_conversion_rates["sms_sent_to_sms_delivered"] == pytest.approx(0.875)
        assert m.overall_conversion_rate == 0.05

    def test_conversion_rates_zero_division(self):
        m = FunnelMetrics(
            period_start=datetime.utcnow(),
            period_end=datetime.utcnow(),
            tenant_id=TENANT_ID,
            stage_counts={"lead_acquired": 0, "sms_sent": 0},
            total_leads=0,
            total_conversions=0,
        )
        m.calculate_conversion_rates()
        assert m.stage_conversion_rates.get("lead_acquired_to_sms_sent", 0) == 0.0
        assert m.overall_conversion_rate == 0.0


# ═══════════════════════════════════════════════════════════════════
# DailyFunnelSnapshot
# ═══════════════════════════════════════════════════════════════════


class TestDailyFunnelSnapshot:
    def test_creation(self):
        snap = DailyFunnelSnapshot(
            tenant_id=TENANT_ID,
            snapshot_date=datetime.utcnow(),
            stage_counts={"lead_acquired": 500},
            new_leads=20,
            new_conversions=5,
            daily_revenue=50_000_000,
            conversion_rate=0.25,
        )
        assert snap.new_leads == 20
        assert snap.daily_revenue == 50_000_000

    def test_defaults(self):
        snap = DailyFunnelSnapshot(
            tenant_id=TENANT_ID,
            snapshot_date=datetime.utcnow(),
        )
        assert snap.new_leads == 0
        assert snap.stage_counts == {}


# ═══════════════════════════════════════════════════════════════════
# CohortAnalysis
# ═══════════════════════════════════════════════════════════════════


class TestCohortAnalysis:
    def test_creation(self):
        cohort = CohortAnalysis(
            cohort_date=datetime(2026, 4, 1),
            cohort_size=100,
            tenant_id=TENANT_ID,
            conversion_by_period={0: 5, 7: 15, 14: 25},
            cumulative_conversion_rates={0: 0.05, 7: 0.15, 14: 0.25},
        )
        assert cohort.cohort_size == 100
        assert cohort.cumulative_conversion_rates[14] == 0.25


# ═══════════════════════════════════════════════════════════════════
# SalespersonMetrics
# ═══════════════════════════════════════════════════════════════════


class TestSalespersonMetrics:
    def test_creation(self):
        now = datetime.utcnow()
        m = SalespersonMetrics(
            salesperson_id=uuid4(),
            salesperson_name="بردبار",
            tenant_id=TENANT_ID,
            period_start=now - timedelta(days=30),
            period_end=now,
            total_calls=200,
            answered_calls=50,
            total_revenue=150_000_000,
            contact_rate=0.75,
            conversion_rate=0.25,
        )
        assert m.salesperson_name == "بردبار"
        assert m.conversion_rate == 0.25

    def test_defaults(self):
        m = SalespersonMetrics(
            salesperson_id=uuid4(),
            salesperson_name="test",
            tenant_id=TENANT_ID,
            period_start=datetime.utcnow(),
            period_end=datetime.utcnow(),
        )
        assert m.total_calls == 0
        assert m.total_revenue == 0
        assert m.rank_by_revenue is None


# ═══════════════════════════════════════════════════════════════════
# AlertRule & AlertInstance
# ═══════════════════════════════════════════════════════════════════


class TestAlertRule:
    def test_creation(self):
        rule = AlertRule(
            tenant_id=TENANT_ID,
            name="Conversion Drop Alert",
            metric_name="conversion_rate",
            condition="below",
            threshold_value=0.1,
            severity="critical",
            notification_channels=["email", "sms"],
        )
        assert rule.is_active is True
        assert rule.trigger_count == 0
        assert "email" in rule.notification_channels

    def test_defaults(self):
        rule = AlertRule(
            tenant_id=TENANT_ID,
            name="test",
            metric_name="daily_leads",
            condition="above",
            threshold_value=100,
        )
        assert rule.severity == "warning"
        assert rule.recipient_emails == []
        assert rule.webhook_url is None


class TestAlertInstance:
    def test_creation(self):
        rule_id = uuid4()
        alert = AlertInstance(
            tenant_id=TENANT_ID,
            rule_id=rule_id,
            rule_name="Conversion Drop",
            metric_name="conversion_rate",
            metric_value=0.05,
            threshold_value=0.1,
            severity="critical",
            message="Conversion rate dropped below 10%",
        )
        assert alert.is_acknowledged is False
        assert alert.severity == "critical"

    def test_acknowledge(self):
        alert = AlertInstance(
            tenant_id=TENANT_ID,
            rule_id=uuid4(),
            rule_name="test",
            metric_name="test",
            metric_value=0,
            threshold_value=0,
            severity="info",
            message="test",
        )
        alert.is_acknowledged = True
        alert.acknowledged_at = datetime.utcnow()
        alert.acknowledged_by = uuid4()
        assert alert.is_acknowledged is True


# ═══════════════════════════════════════════════════════════════════
# Analytics API Schemas
# ═══════════════════════════════════════════════════════════════════


class TestAnalyticsSchemas:
    def test_stage_count_schema(self):
        s = StageCountSchema(stage="lead_acquired", count=500, percentage=35.0)
        assert s.count == 500

    def test_conversion_rate_schema(self):
        c = ConversionRateSchema(from_stage="sms_sent", to_stage="call_attempted", rate=0.375)
        assert c.rate == 0.375

    def test_funnel_metrics_response(self):
        now = datetime.utcnow()
        resp = FunnelMetricsResponse(
            period_start=now - timedelta(days=30),
            period_end=now,
            tenant_id=TENANT_ID,
            stage_counts=[StageCountSchema(stage="lead_acquired", count=100)],
            conversion_rates=[],
            total_leads=100,
            total_conversions=10,
            overall_conversion_rate=0.1,
        )
        assert resp.total_leads == 100

    def test_daily_snapshot_schema(self):
        s = DailySnapshotSchema(
            date=datetime.utcnow(),
            new_leads=20,
            new_conversions=5,
            daily_revenue=50_000_000,
            conversion_rate=0.25,
        )
        assert s.daily_revenue == 50_000_000

    def test_funnel_trend_response(self):
        now = datetime.utcnow()
        resp = FunnelTrendResponse(
            period_start=now - timedelta(days=7),
            period_end=now,
            snapshots=[],
        )
        assert resp.snapshots == []

