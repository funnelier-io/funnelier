"""
SQLAlchemy Models - Leads Module
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, JSON, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..session import Base
from ..base_models import UUIDMixin, TimestampMixin


class LeadCategoryModel(Base, UUIDMixin, TimestampMixin):
    """Category for organizing leads."""

    __tablename__ = "lead_categories"

    tenant_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    parent_id: Mapped[UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("lead_categories.id", ondelete="SET NULL"))
    color: Mapped[str | None] = mapped_column(String(20))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    metadata_: Mapped[dict] = mapped_column("metadata", JSON, default=dict)

    contacts: Mapped[list["ContactModel"]] = relationship(back_populates="category")

    __table_args__ = (Index("ix_lead_categories_tenant_name", "tenant_id", "name"),)


class LeadSourceModel(Base, UUIDMixin, TimestampMixin):
    """Lead source configuration."""

    __tablename__ = "lead_sources"

    tenant_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    file_path: Mapped[str | None] = mapped_column(String(500))
    category_id: Mapped[UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("lead_categories.id", ondelete="SET NULL"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_import_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    total_leads: Mapped[int] = mapped_column(Integer, default=0)
    metadata_: Mapped[dict] = mapped_column("metadata", JSON, default=dict)


class ContactModel(Base, UUIDMixin, TimestampMixin):
    """Contact/Lead - the core entity that moves through the funnel."""

    __tablename__ = "contacts"

    tenant_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    phone_number: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    name: Mapped[str | None] = mapped_column(String(255))
    email: Mapped[str | None] = mapped_column(String(255))

    source_id: Mapped[UUID | None] = mapped_column(UUID(as_uuid=True))
    source_name: Mapped[str | None] = mapped_column(String(255))
    category_id: Mapped[UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("lead_categories.id", ondelete="SET NULL"))
    category_name: Mapped[str | None] = mapped_column(String(255))

    assigned_to: Mapped[UUID | None] = mapped_column(UUID(as_uuid=True))
    assigned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    current_stage: Mapped[str] = mapped_column(String(50), default="lead_acquired", index=True)
    stage_entered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    rfm_segment: Mapped[str | None] = mapped_column(String(50), index=True)
    rfm_score: Mapped[str | None] = mapped_column(String(3))
    recency_score: Mapped[int | None] = mapped_column(Integer)
    frequency_score: Mapped[int | None] = mapped_column(Integer)
    monetary_score: Mapped[int | None] = mapped_column(Integer)
    last_rfm_update: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    total_sms_sent: Mapped[int] = mapped_column(Integer, default=0)
    total_sms_delivered: Mapped[int] = mapped_column(Integer, default=0)
    total_calls: Mapped[int] = mapped_column(Integer, default=0)
    total_answered_calls: Mapped[int] = mapped_column(Integer, default=0)
    total_call_duration: Mapped[int] = mapped_column(Integer, default=0)

    total_invoices: Mapped[int] = mapped_column(Integer, default=0)
    total_paid_invoices: Mapped[int] = mapped_column(Integer, default=0)
    total_revenue: Mapped[int] = mapped_column(Integer, default=0)
    last_purchase_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    first_purchase_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False)
    blocked_reason: Mapped[str | None] = mapped_column(String(255))

    tags: Mapped[list] = mapped_column(JSON, default=list)
    custom_fields: Mapped[dict] = mapped_column(JSON, default=dict)
    notes: Mapped[str | None] = mapped_column(Text)

    category: Mapped["LeadCategoryModel | None"] = relationship(back_populates="contacts")

    __table_args__ = (
        Index("ix_contacts_tenant_phone", "tenant_id", "phone_number", unique=True),
        Index("ix_contacts_tenant_stage", "tenant_id", "current_stage"),
        Index("ix_contacts_tenant_segment", "tenant_id", "rfm_segment"),
    )

