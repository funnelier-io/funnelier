"""
Notification Database Models

NotificationModel — user-scoped notifications (alerts, imports, campaigns, system)
NotificationPreferenceModel — per-user notification delivery preferences
"""

from datetime import datetime, time
from uuid import UUID

from sqlalchemy import (
    Boolean, DateTime, Enum, Index, Integer, JSON, String, Text, Time,
    ForeignKey, func,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.database.session import Base
from src.infrastructure.database.base_models import UUIDMixin, TimestampMixin, TenantMixin


class NotificationModel(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """Persisted user notification."""

    __tablename__ = "notifications"

    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), nullable=False, index=True,
    )

    # Type: alert, import, campaign, system, sync, report, sms
    type: Mapped[str] = mapped_column(String(50), nullable=False, default="system")

    # Severity: info, success, warning, error, critical
    severity: Mapped[str] = mapped_column(String(20), nullable=False, default="info")

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Polymorphic link to source entity (alert_instances, campaigns, import_logs, etc.)
    source_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    source_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)

    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Extra structured data (counts, links, etc.)
    metadata_json: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)

    __table_args__ = (
        Index("ix_notifications_user_unread", "user_id", "is_read"),
        Index("ix_notifications_user_created", "user_id", "created_at"),
        Index("ix_notifications_tenant_user", "tenant_id", "user_id"),
    )


class NotificationPreferenceModel(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """Per-user notification delivery preferences."""

    __tablename__ = "notification_preferences"

    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), nullable=False, unique=True,
    )

    in_app_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    email_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    sms_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    push_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Quiet hours (no notifications during this window)
    quiet_hours_start: Mapped[time | None] = mapped_column(Time, nullable=True)
    quiet_hours_end: Mapped[time | None] = mapped_column(Time, nullable=True)

    # JSON array of notification type strings to mute, e.g. ["import", "sync"]
    disabled_types: Mapped[list | None] = mapped_column(JSON, nullable=True, default=list)

    # Web Push subscription JSON (PushSubscription object from browser)
    push_subscription: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    __table_args__ = (
        Index("ix_notif_pref_tenant_user", "tenant_id", "user_id"),
    )

