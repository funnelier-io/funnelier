"""
SQLAlchemy Models - Tenants Module
"""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..session import Base
from ..base_models import UUIDMixin, TimestampMixin

if TYPE_CHECKING:
    from .leads import ContactModel
    from .communications import SMSLogModel, CallLogModel


class TenantModel(Base, UUIDMixin, TimestampMixin):
    """Tenant table - represents a customer organization."""

    __tablename__ = "tenants"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)

    # Contact info
    email: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(20))

    # Configuration
    settings: Mapped[dict] = mapped_column(JSON, default=dict)

    # Subscription
    plan: Mapped[str] = mapped_column(String(50), default="free")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    trial_ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Limits
    max_contacts: Mapped[int] = mapped_column(Integer, default=1000)
    max_sms_per_month: Mapped[int] = mapped_column(Integer, default=1000)
    max_users: Mapped[int] = mapped_column(Integer, default=5)

    # Usage tracking
    current_contacts: Mapped[int] = mapped_column(Integer, default=0)
    current_month_sms: Mapped[int] = mapped_column(Integer, default=0)

    metadata_: Mapped[dict] = mapped_column("metadata", JSON, default=dict)

    # Relationships
    users: Mapped[list["TenantUserModel"]] = relationship(back_populates="tenant")
    salespersons: Mapped[list["SalespersonModel"]] = relationship(back_populates="tenant")
    data_sources: Mapped[list["DataSourceConnectionModel"]] = relationship(back_populates="tenant")


class TenantUserModel(Base, UUIDMixin, TimestampMixin):
    """User within a tenant."""

    __tablename__ = "tenant_users"

    tenant_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    # Role
    role: Mapped[str] = mapped_column(String(50), default="member")

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Permissions
    permissions: Mapped[list] = mapped_column(JSON, default=list)

    # Relationships
    tenant: Mapped["TenantModel"] = relationship(back_populates="users")


class SalespersonModel(Base, UUIDMixin, TimestampMixin):
    """Salesperson entity."""

    __tablename__ = "salespersons"

    tenant_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(20))
    email: Mapped[str | None] = mapped_column(String(255))

    # Assignment
    region: Mapped[str | None] = mapped_column(String(100))
    categories: Mapped[list] = mapped_column(JSON, default=list)

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Performance cache
    total_leads_assigned: Mapped[int] = mapped_column(Integer, default=0)
    total_conversions: Mapped[int] = mapped_column(Integer, default=0)
    total_revenue: Mapped[int] = mapped_column(Integer, default=0)

    metadata_: Mapped[dict] = mapped_column("metadata", JSON, default=dict)

    # Relationships
    tenant: Mapped["TenantModel"] = relationship(back_populates="salespersons")


class DataSourceConnectionModel(Base, UUIDMixin, TimestampMixin):
    """Configuration for tenant data source connections."""

    __tablename__ = "data_source_connections"

    tenant_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)

    # Connection details (should be encrypted in production)
    connection_config: Mapped[dict] = mapped_column(JSON, default=dict)

    # Mapping configuration
    field_mappings: Mapped[dict] = mapped_column(JSON, default=dict)

    # Sync settings
    sync_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    sync_interval_minutes: Mapped[int] = mapped_column(Integer, default=60)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_sync_status: Mapped[str | None] = mapped_column(String(50))
    last_sync_records: Mapped[int] = mapped_column(Integer, default=0)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    metadata_: Mapped[dict] = mapped_column("metadata", JSON, default=dict)

    # Relationships
    tenant: Mapped["TenantModel"] = relationship(back_populates="data_sources")

