"""
SQLAlchemy Models - Analytics Module
FunnelSnapshot, AlertRule, AlertInstance for persisting analytics data.
"""

from datetime import datetime, date

from sqlalchemy import (
    Boolean, Date, DateTime, Float, ForeignKey, Integer,
    String, Text, JSON, Index, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from ..session import Base
from ..base_models import UUIDMixin, TimestampMixin


class FunnelSnapshotModel(Base, UUIDMixin, TimestampMixin):
    """Daily funnel snapshot — stores stage counts and metrics per day."""

    __tablename__ = "funnel_snapshots"

    tenant_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)

    # Per-stage counts  {"lead_acquired": 1200, "sms_sent": 980, ...}
    stage_counts: Mapped[dict] = mapped_column(JSON, default=dict)

    # Daily deltas
    new_leads: Mapped[int] = mapped_column(Integer, default=0)
    new_sms_sent: Mapped[int] = mapped_column(Integer, default=0)
    new_sms_delivered: Mapped[int] = mapped_column(Integer, default=0)
    new_calls: Mapped[int] = mapped_column(Integer, default=0)
    new_answered_calls: Mapped[int] = mapped_column(Integer, default=0)
    new_successful_calls: Mapped[int] = mapped_column(Integer, default=0)
    new_invoices: Mapped[int] = mapped_column(Integer, default=0)
    new_payments: Mapped[int] = mapped_column(Integer, default=0)
    new_conversions: Mapped[int] = mapped_column(Integer, default=0)

    # Revenue
    daily_revenue: Mapped[int] = mapped_column(Integer, default=0)  # Rial

    # Conversion rates  {"lead_to_sms": 0.82, "sms_to_call": 0.65, ...}
    conversion_rates: Mapped[dict] = mapped_column(JSON, default=dict)
    overall_conversion_rate: Mapped[float] = mapped_column(Float, default=0.0)

    # Stage transitions  [{"from": "sms_sent", "to": "call_attempted", "count": 45}, ...]
    stage_transitions: Mapped[list] = mapped_column(JSON, default=list)

    __table_args__ = (
        UniqueConstraint("tenant_id", "snapshot_date", name="uq_funnel_snapshot_tenant_date"),
        Index("ix_funnel_snapshots_tenant_date", "tenant_id", "snapshot_date"),
    )


class AlertRuleModel(Base, UUIDMixin, TimestampMixin):
    """Configurable alert rule — triggers when a metric crosses a threshold."""

    __tablename__ = "alert_rules"

    tenant_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)

    # What to monitor
    metric_name: Mapped[str] = mapped_column(String(100), nullable=False)
    # e.g. "conversion_rate", "daily_leads", "sms_delivery_rate", "call_answer_rate"

    # Condition
    condition: Mapped[str] = mapped_column(String(20), nullable=False)
    # "gt", "lt", "gte", "lte", "eq", "change_gt", "change_lt"
    threshold_value: Mapped[float] = mapped_column(Float, nullable=False)

    # Severity
    severity: Mapped[str] = mapped_column(String(20), default="warning")
    # "info", "warning", "critical"

    # Notification channels  ["dashboard", "sms", "email", "webhook"]
    notification_channels: Mapped[list] = mapped_column(JSON, default=list)
    notification_recipients: Mapped[list] = mapped_column(JSON, default=list)
    # e.g. phone numbers or emails

    # Cooldown (minutes) — avoid spamming
    cooldown_minutes: Mapped[int] = mapped_column(Integer, default=60)
    last_triggered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    metadata_: Mapped[dict] = mapped_column("metadata", JSON, default=dict)

    __table_args__ = (
        Index("ix_alert_rules_tenant_metric", "tenant_id", "metric_name"),
    )


class AlertInstanceModel(Base, UUIDMixin, TimestampMixin):
    """A triggered alert instance."""

    __tablename__ = "alert_instances"

    tenant_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    rule_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("alert_rules.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Snapshot of what triggered
    metric_name: Mapped[str] = mapped_column(String(100), nullable=False)
    metric_value: Mapped[float] = mapped_column(Float, nullable=False)
    threshold_value: Mapped[float] = mapped_column(Float, nullable=False)
    condition: Mapped[str] = mapped_column(String(20), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)

    message: Mapped[str] = mapped_column(Text, nullable=False)

    # Status
    status: Mapped[str] = mapped_column(String(20), default="active", index=True)
    # "active", "acknowledged", "resolved"
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    acknowledged_by: Mapped[UUID | None] = mapped_column(UUID(as_uuid=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Notification tracking
    notifications_sent: Mapped[list] = mapped_column(JSON, default=list)
    # [{"channel": "dashboard", "sent_at": "...", "success": true}, ...]

    metadata_: Mapped[dict] = mapped_column("metadata", JSON, default=dict)

    __table_args__ = (
        Index("ix_alert_instances_tenant_status", "tenant_id", "status"),
        Index("ix_alert_instances_tenant_rule", "tenant_id", "rule_id"),
    )

