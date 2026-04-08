"""
SQLAlchemy Models - Communications Module
"""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, JSON, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from ..session import Base
from ..base_models import UUIDMixin, TimestampMixin


class SMSTemplateModel(Base, UUIDMixin, TimestampMixin):
    """SMS message template."""

    __tablename__ = "sms_templates"

    tenant_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(String(100))
    target_segments: Mapped[list] = mapped_column(JSON, default=list)
    # Which RFM segments this template targets

    # Performance metrics
    times_used: Mapped[int] = mapped_column(Integer, default=0)
    total_delivered: Mapped[int] = mapped_column(Integer, default=0)
    total_conversions: Mapped[int] = mapped_column(Integer, default=0)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    metadata_: Mapped[dict] = mapped_column("metadata", JSON, default=dict)

    __table_args__ = (
        Index("ix_sms_templates_tenant_name", "tenant_id", "name"),
    )


class SMSLogModel(Base, UUIDMixin, TimestampMixin):
    """SMS message log - tracks all SMS sent."""

    __tablename__ = "sms_logs"

    tenant_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    contact_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("contacts.id", ondelete="SET NULL"),
        index=True,
    )
    phone_number: Mapped[str] = mapped_column(String(20), nullable=False, index=True)

    # Template used
    template_id: Mapped[UUID | None] = mapped_column(UUID(as_uuid=True))
    template_name: Mapped[str | None] = mapped_column(String(255))

    # Message details
    message_content: Mapped[str] = mapped_column(Text, nullable=False)
    message_id: Mapped[str | None] = mapped_column(String(100))
    # External provider message ID

    # Provider info
    provider: Mapped[str] = mapped_column(String(50), default="kavenegar")
    sender_number: Mapped[str | None] = mapped_column(String(20))

    # Status tracking
    status: Mapped[str] = mapped_column(String(50), default="pending", index=True)
    # pending, sent, delivered, failed, blocked
    status_code: Mapped[int | None] = mapped_column(Integer)
    status_message: Mapped[str | None] = mapped_column(String(255))

    # Timestamps
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Cost tracking
    cost: Mapped[int] = mapped_column(Integer, default=0)
    sms_parts: Mapped[int] = mapped_column(Integer, default=1)

    # Campaign reference
    campaign_id: Mapped[UUID | None] = mapped_column(UUID(as_uuid=True))

    metadata_: Mapped[dict] = mapped_column("metadata", JSON, default=dict)

    __table_args__ = (
        Index("ix_sms_logs_tenant_phone", "tenant_id", "phone_number"),
        Index("ix_sms_logs_tenant_status", "tenant_id", "status"),
        Index("ix_sms_logs_tenant_sent_at", "tenant_id", "sent_at"),
        Index("ix_sms_logs_tenant_campaign", "tenant_id", "campaign_id"),
    )


class CallLogModel(Base, UUIDMixin, TimestampMixin):
    """Call log - tracks all calls (mobile + VoIP)."""

    __tablename__ = "call_logs"

    tenant_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    contact_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("contacts.id", ondelete="SET NULL"),
        index=True,
    )
    phone_number: Mapped[str] = mapped_column(String(20), nullable=False, index=True)

    # Call type
    call_type: Mapped[str] = mapped_column(String(20), default="outbound")
    # outbound, inbound
    source_type: Mapped[str] = mapped_column(String(20), default="mobile")
    # mobile, voip

    # Salesperson
    salesperson_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("salespersons.id", ondelete="SET NULL"),
    )
    salesperson_name: Mapped[str | None] = mapped_column(String(255))
    salesperson_phone: Mapped[str | None] = mapped_column(String(20))

    # Call details
    call_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    call_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_seconds: Mapped[int] = mapped_column(Integer, default=0)

    # Status
    status: Mapped[str] = mapped_column(String(50), default="attempted", index=True)
    # attempted, answered, no_answer, busy, failed
    is_successful: Mapped[bool] = mapped_column(Boolean, default=False)
    # True if answered and duration >= 90 seconds

    # VoIP specific fields
    voip_call_id: Mapped[str | None] = mapped_column(String(100))
    voip_channel: Mapped[str | None] = mapped_column(String(100))
    recording_url: Mapped[str | None] = mapped_column(String(500))

    # Notes
    notes: Mapped[str | None] = mapped_column(Text)
    outcome: Mapped[str | None] = mapped_column(String(100))
    # interested, not_interested, callback_requested, wrong_number, etc.

    metadata_: Mapped[dict] = mapped_column("metadata", JSON, default=dict)

    __table_args__ = (
        Index("ix_call_logs_tenant_phone", "tenant_id", "phone_number"),
        Index("ix_call_logs_tenant_salesperson", "tenant_id", "salesperson_id"),
        Index("ix_call_logs_tenant_status", "tenant_id", "status"),
        Index("ix_call_logs_tenant_call_start", "tenant_id", "call_start"),
    )

