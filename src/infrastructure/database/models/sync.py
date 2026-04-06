"""
SQLAlchemy Models — ERP/CRM Sync
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, JSON, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..session import Base
from ..base_models import UUIDMixin, TimestampMixin


class SyncLogModel(Base, UUIDMixin, TimestampMixin):
    """Log of every sync operation executed against a data source."""

    __tablename__ = "sync_logs"

    tenant_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    data_source_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("data_source_connections.id", ondelete="SET NULL"),
        index=True,
    )

    # What was synced
    sync_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # "full", "incremental", "invoices", "payments", "customers", "products"

    direction: Mapped[str] = mapped_column(String(20), default="pull")
    # "pull" (ERP → Funnelier), "push", "bidirectional"

    # Status
    status: Mapped[str] = mapped_column(String(30), default="running", index=True)
    # "running", "success", "partial", "failed", "cancelled"

    # Counters
    records_fetched: Mapped[int] = mapped_column(Integer, default=0)
    records_created: Mapped[int] = mapped_column(Integer, default=0)
    records_updated: Mapped[int] = mapped_column(Integer, default=0)
    records_skipped: Mapped[int] = mapped_column(Integer, default=0)
    records_failed: Mapped[int] = mapped_column(Integer, default=0)

    # Timing
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_seconds: Mapped[float | None] = mapped_column(Float)

    # Errors and details
    error_message: Mapped[str | None] = mapped_column(Text)
    errors: Mapped[list] = mapped_column(JSON, default=list)
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    # e.g. {"invoices": {"created": 5, "updated": 10}, "payments": {...}}

    # Who triggered it
    triggered_by: Mapped[str] = mapped_column(String(50), default="manual")
    # "manual", "scheduled", "webhook", "system"
    triggered_by_user_id: Mapped[UUID | None] = mapped_column(UUID(as_uuid=True))

    __table_args__ = (
        Index("ix_sync_logs_tenant_status", "tenant_id", "status"),
        Index("ix_sync_logs_tenant_started", "tenant_id", "started_at"),
        Index("ix_sync_logs_source_started", "data_source_id", "started_at"),
    )

