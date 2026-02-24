"""
SQLAlchemy Models - ETL / Import Log
Tracks all data import jobs for auditability and status monitoring.
"""

from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, Text, JSON, Index, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from ..session import Base
from ..base_models import UUIDMixin, TimestampMixin


class ImportLogModel(Base, UUIDMixin, TimestampMixin):
    """Tracks individual import job executions."""

    __tablename__ = "import_logs"

    tenant_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Task tracking
    task_id: Mapped[str | None] = mapped_column(String(100), index=True)
    # Celery task ID for async jobs, null for sync

    # Import details
    import_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # "leads_excel", "call_logs_csv", "sms_logs_csv", "voip_json", "leads_batch", "mongodb_sync"
    file_name: Mapped[str | None] = mapped_column(String(500))
    category: Mapped[str | None] = mapped_column(String(255))

    # Status
    status: Mapped[str] = mapped_column(String(20), default="queued", index=True)
    # "queued", "running", "completed", "failed"

    # Results
    total_records: Mapped[int] = mapped_column(Integer, default=0)
    imported: Mapped[int] = mapped_column(Integer, default=0)
    duplicates: Mapped[int] = mapped_column(Integer, default=0)
    errors: Mapped[int] = mapped_column(Integer, default=0)
    error_details: Mapped[list] = mapped_column(JSON, default=list)

    # Timing
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_seconds: Mapped[float | None] = mapped_column(Float)

    # Who initiated
    initiated_by: Mapped[UUID | None] = mapped_column(UUID(as_uuid=True))

    metadata_: Mapped[dict] = mapped_column("metadata", JSON, default=dict)

    __table_args__ = (
        Index("ix_import_logs_tenant_status", "tenant_id", "status"),
        Index("ix_import_logs_tenant_type", "tenant_id", "import_type"),
    )

