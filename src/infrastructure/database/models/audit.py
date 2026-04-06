"""
Audit Log Database Model
"""

from uuid import UUID

from sqlalchemy import DateTime, JSON, String, Text, Index
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.database import Base
from src.infrastructure.database.base_models import UUIDMixin, TimestampMixin, TenantMixin


class AuditLogModel(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """Immutable audit log entry for tracking all user actions."""

    __tablename__ = "audit_logs"

    # Who
    user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    user_name: Mapped[str] = mapped_column(String(255), nullable=False)
    user_role: Mapped[str] = mapped_column(String(50), nullable=False)

    # What
    action: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    # e.g. create, update, delete, login, logout, import, export, approve, deactivate, sync, etc.

    resource_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    # e.g. user, contact, campaign, invoice, sms, call_log, import, report, setting, etc.

    resource_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # UUID or identifier of the affected resource

    # Details
    description: Mapped[str] = mapped_column(Text, nullable=False)
    # Human-readable description, e.g. "Created user john.doe"

    # Change tracking (before/after snapshots for updates)
    changes: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # { "field_name": { "old": "...", "new": "..." }, ... }

    # Context
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Composite indexes for common queries
    __table_args__ = (
        Index("ix_audit_tenant_created", "tenant_id", "created_at"),
        Index("ix_audit_user_created", "user_id", "created_at"),
        Index("ix_audit_action_resource", "action", "resource_type"),
    )

