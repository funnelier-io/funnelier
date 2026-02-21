"""
Tenants API Schemas

Pydantic schemas for multi-tenant management.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


# ============================================================================
# Tenant Schemas
# ============================================================================

class TenantBase(BaseModel):
    """Base schema for tenant."""
    name: str
    slug: str
    description: str | None = None
    domain: str | None = None
    logo_url: str | None = None
    timezone: str = "Asia/Tehran"
    language: str = "fa"
    currency: str = "IRR"
    is_active: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class CreateTenantRequest(TenantBase):
    """Schema for creating a tenant."""
    admin_email: str
    admin_name: str


class UpdateTenantRequest(BaseModel):
    """Schema for updating a tenant."""
    name: str | None = None
    description: str | None = None
    domain: str | None = None
    logo_url: str | None = None
    timezone: str | None = None
    language: str | None = None
    currency: str | None = None
    is_active: bool | None = None
    metadata: dict[str, Any] | None = None


class TenantResponse(TenantBase):
    """Schema for tenant response."""
    id: UUID
    plan: str = "basic"  # basic, pro, enterprise
    max_users: int = 10
    max_contacts: int = 10000
    features: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime | None = None

    class Config:
        from_attributes = True


class TenantListResponse(BaseModel):
    """Schema for tenant list."""
    tenants: list[TenantResponse]
    total_count: int


# ============================================================================
# Tenant Settings Schemas
# ============================================================================

class FunnelStageConfig(BaseModel):
    """Schema for funnel stage configuration."""
    id: str
    name: str
    name_fa: str
    order: int
    color: str | None = None
    is_conversion: bool = False
    auto_transition_rules: dict[str, Any] = Field(default_factory=dict)


class RFMSettingsSchema(BaseModel):
    """Schema for RFM settings."""
    recency_thresholds: list[int] = [7, 14, 30, 60, 90]
    frequency_thresholds: list[int] = [1, 2, 4, 8, 16]
    monetary_thresholds: list[int] = [100_000_000, 500_000_000, 1_000_000_000, 2_000_000_000, 5_000_000_000]
    analysis_period_months: int = 12
    high_value_threshold: int = 1_000_000_000
    recent_days: int = 14


class CallSettingsSchema(BaseModel):
    """Schema for call settings."""
    successful_call_threshold_seconds: int = 90
    voip_provider: str | None = None
    auto_match_contacts: bool = True


class SMSSettingsSchema(BaseModel):
    """Schema for SMS settings."""
    provider: str = "kavenegar"
    api_key: str | None = None
    sender_number: str | None = None
    daily_limit: int | None = None
    delivery_report_webhook: str | None = None


class NotificationSettingsSchema(BaseModel):
    """Schema for notification settings."""
    email_enabled: bool = True
    sms_enabled: bool = False
    webhook_url: str | None = None
    alert_recipients: list[str] = Field(default_factory=list)


class TenantSettingsResponse(BaseModel):
    """Schema for tenant settings response."""
    tenant_id: UUID
    funnel_stages: list[FunnelStageConfig] = Field(default_factory=list)
    rfm_settings: RFMSettingsSchema = Field(default_factory=RFMSettingsSchema)
    call_settings: CallSettingsSchema = Field(default_factory=CallSettingsSchema)
    sms_settings: SMSSettingsSchema = Field(default_factory=SMSSettingsSchema)
    notification_settings: NotificationSettingsSchema = Field(default_factory=NotificationSettingsSchema)
    custom_fields: dict[str, Any] = Field(default_factory=dict)
    updated_at: datetime | None = None


class UpdateTenantSettingsRequest(BaseModel):
    """Schema for updating tenant settings."""
    funnel_stages: list[FunnelStageConfig] | None = None
    rfm_settings: RFMSettingsSchema | None = None
    call_settings: CallSettingsSchema | None = None
    sms_settings: SMSSettingsSchema | None = None
    notification_settings: NotificationSettingsSchema | None = None
    custom_fields: dict[str, Any] | None = None


# ============================================================================
# Data Source Configuration Schemas
# ============================================================================

class DataSourceConfigBase(BaseModel):
    """Base schema for data source configuration."""
    name: str
    source_type: str  # mongodb, postgresql, mysql, api, file
    description: str | None = None
    connection_config: dict[str, Any] = Field(default_factory=dict)
    field_mappings: dict[str, str] = Field(default_factory=dict)
    sync_interval_minutes: int = 60
    is_active: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class CreateDataSourceConfigRequest(DataSourceConfigBase):
    """Schema for creating a data source config."""
    pass


class DataSourceConfigResponse(DataSourceConfigBase):
    """Schema for data source config response."""
    id: UUID
    tenant_id: UUID
    last_sync_at: datetime | None = None
    last_sync_status: str | None = None
    records_synced: int = 0
    created_at: datetime
    updated_at: datetime | None = None

    class Config:
        from_attributes = True


class DataSourceConfigListResponse(BaseModel):
    """Schema for data source config list."""
    configs: list[DataSourceConfigResponse]
    total_count: int


# ============================================================================
# Integration Schemas
# ============================================================================

class IntegrationBase(BaseModel):
    """Base schema for integration."""
    name: str
    integration_type: str  # crm, erp, sms_provider, voip, webhook
    description: str | None = None
    config: dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True


class CreateIntegrationRequest(IntegrationBase):
    """Schema for creating an integration."""
    pass


class IntegrationResponse(IntegrationBase):
    """Schema for integration response."""
    id: UUID
    tenant_id: UUID
    status: str = "configured"  # configured, connected, error
    last_activity_at: datetime | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime | None = None

    class Config:
        from_attributes = True


class IntegrationListResponse(BaseModel):
    """Schema for integration list."""
    integrations: list[IntegrationResponse]
    total_count: int


# ============================================================================
# Usage & Billing Schemas
# ============================================================================

class UsageStatsResponse(BaseModel):
    """Schema for usage statistics."""
    tenant_id: UUID
    period_start: datetime
    period_end: datetime
    contacts_count: int
    contacts_limit: int
    sms_sent: int
    sms_limit: int | None = None
    api_calls: int
    storage_used_mb: float
    users_count: int
    users_limit: int


class BillingInfoResponse(BaseModel):
    """Schema for billing information."""
    tenant_id: UUID
    plan: str
    plan_price: int
    billing_cycle: str  # monthly, yearly
    next_billing_date: datetime | None = None
    payment_method: str | None = None
    is_trial: bool = False
    trial_ends_at: datetime | None = None

