"""
SQLAlchemy Model — Segment Rules
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.database.session import Base
from src.infrastructure.database.base_models import UUIDMixin, TimestampMixin


class SegmentRuleModel(Base, UUIDMixin, TimestampMixin):
    """Persisted tenant-defined RFM segment rule."""

    __tablename__ = "segment_rules"

    tenant_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    color: Mapped[str] = mapped_column(String(20), default="#6366f1")
    priority: Mapped[int] = mapped_column(Integer, default=0)

    r_min: Mapped[int] = mapped_column(Integer, default=1)
    r_max: Mapped[int] = mapped_column(Integer, default=5)
    f_min: Mapped[int] = mapped_column(Integer, default=1)
    f_max: Mapped[int] = mapped_column(Integer, default=5)
    m_min: Mapped[int] = mapped_column(Integer, default=1)
    m_max: Mapped[int] = mapped_column(Integer, default=5)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    __table_args__ = (
        Index("ix_segment_rules_tenant_priority", "tenant_id", "priority"),
    )

