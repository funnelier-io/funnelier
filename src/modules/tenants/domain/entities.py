"""
Tenants Module - Domain Layer
Multi-tenant management
"""

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import Field

from src.core.domain import Entity, DataSourceType


class Tenant(Entity[UUID]):
    """
    Tenant entity - represents a customer organization.
    """

    id: UUID = Field(default_factory=uuid4)
    name: str
    slug: str  # URL-friendly identifier

    # Contact info
    email: str | None = None
    phone: str | None = None

    # Configuration
    settings: dict[str, Any] = Field(default_factory=dict)

    # Subscription
    plan: str = "free"  # free, basic, pro, enterprise
    is_active: bool = True
    trial_ends_at: datetime | None = None

    # Limits
    max_contacts: int = 1000
    max_sms_per_month: int = 1000
    max_users: int = 5

    # Usage tracking
    current_contacts: int = 0
    current_month_sms: int = 0

    metadata: dict[str, Any] = Field(default_factory=dict)


class TenantUser(Entity[UUID]):
    """
    User within a tenant.
    """

    id: UUID = Field(default_factory=uuid4)
    tenant_id: UUID

    email: str
    name: str
    password_hash: str

    # Role
    role: str = "member"  # admin, manager, member, viewer

    # Status
    is_active: bool = True
    last_login_at: datetime | None = None

    # Permissions
    permissions: list[str] = Field(default_factory=list)


class Salesperson(Entity[UUID]):
    """
    Salesperson entity.
    """

    id: UUID = Field(default_factory=uuid4)
    tenant_id: UUID

    name: str
    phone: str | None = None
    email: str | None = None

    # Assignment
    region: str | None = None
    categories: list[str] = Field(default_factory=list)

    # Status
    is_active: bool = True

    # Performance cache
    total_leads_assigned: int = 0
    total_conversions: int = 0
    total_revenue: int = 0

    metadata: dict[str, Any] = Field(default_factory=dict)


class DataSourceConnection(Entity[UUID]):
    """
    Configuration for tenant data source connections.
    """

    id: UUID = Field(default_factory=uuid4)
    tenant_id: UUID

    name: str
    source_type: DataSourceType

    # Connection details (encrypted in production)
    connection_config: dict[str, Any] = Field(default_factory=dict)

    # Mapping configuration
    field_mappings: dict[str, str] = Field(default_factory=dict)

    # Sync settings
    sync_enabled: bool = False
    sync_interval_minutes: int = 60
    last_sync_at: datetime | None = None
    last_sync_status: str | None = None
    last_sync_records: int = 0

    is_active: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)

