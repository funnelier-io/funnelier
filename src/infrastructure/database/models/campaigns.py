"""
SQLAlchemy Models - Campaigns Module
"""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, JSON, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from ..session import Base
from ..base_models import UUIDMixin, TimestampMixin


class CampaignModel(Base, UUIDMixin, TimestampMixin):
    """SMS/call marketing campaign."""

    __tablename__ = "campaigns"

    tenant_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Basic info
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    campaign_type: Mapped[str] = mapped_column(String(50), default="sms")
    # sms, call, mixed

    # Template / content
    template_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sms_templates.id", ondelete="SET NULL"),
    )
    message_content: Mapped[str | None] = mapped_column(Text)

    # Targeting
    target_segment: Mapped[str | None] = mapped_column(String(100))
    target_category_id: Mapped[UUID | None] = mapped_column(UUID(as_uuid=True))
    target_filters: Mapped[dict] = mapped_column(JSON, default=dict)
    targeting: Mapped[dict] = mapped_column(JSON, default=dict)

    # Schedule
    schedule: Mapped[dict | None] = mapped_column(JSON)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Status
    status: Mapped[str] = mapped_column(String(50), default="draft", index=True)
    # draft, scheduled, running, paused, completed, cancelled
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Result counters
    total_recipients: Mapped[int] = mapped_column(Integer, default=0)
    total_sent: Mapped[int] = mapped_column(Integer, default=0)
    total_delivered: Mapped[int] = mapped_column(Integer, default=0)
    total_failed: Mapped[int] = mapped_column(Integer, default=0)
    total_calls_received: Mapped[int] = mapped_column(Integer, default=0)
    total_conversions: Mapped[int] = mapped_column(Integer, default=0)
    total_revenue: Mapped[int] = mapped_column(Integer, default=0)

    # A/B testing
    is_ab_test: Mapped[bool] = mapped_column(Boolean, default=False)
    variant_name: Mapped[str | None] = mapped_column(String(50))
    parent_campaign_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("campaigns.id", ondelete="SET NULL"),
    )

    # Cost tracking
    estimated_cost: Mapped[int] = mapped_column(Integer, default=0)
    actual_cost: Mapped[int] = mapped_column(Integer, default=0)

    # Audit
    created_by: Mapped[UUID | None] = mapped_column(UUID(as_uuid=True))
    metadata_: Mapped[dict] = mapped_column("metadata", JSON, default=dict)

    __table_args__ = (
        Index("ix_campaigns_tenant_status", "tenant_id", "status"),
        Index("ix_campaigns_tenant_name", "tenant_id", "name"),
        Index("ix_campaigns_tenant_created", "tenant_id", "created_at"),
    )


class CampaignRecipientModel(Base, UUIDMixin, TimestampMixin):
    """Tracks each recipient in a campaign."""

    __tablename__ = "campaign_recipients"

    tenant_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    campaign_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("campaigns.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    contact_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("contacts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    phone_number: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str | None] = mapped_column(String(255))
    segment: Mapped[str | None] = mapped_column(String(100))

    # Delivery tracking
    status: Mapped[str] = mapped_column(String(50), default="pending")
    # pending, sent, delivered, failed, responded, converted
    sms_log_id: Mapped[UUID | None] = mapped_column(UUID(as_uuid=True))

    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    converted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    metadata_: Mapped[dict] = mapped_column("metadata", JSON, default=dict)

    __table_args__ = (
        Index("ix_campaign_recipients_campaign_status", "campaign_id", "status"),
        Index("ix_campaign_recipients_tenant_campaign", "tenant_id", "campaign_id"),
    )

