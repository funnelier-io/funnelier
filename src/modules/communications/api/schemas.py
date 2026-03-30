"""
Communications API Schemas

Pydantic schemas for communications module API endpoints.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


# ============================================================================
# SMS Log Schemas
# ============================================================================

class SMSLogBase(BaseModel):
    """Base schema for SMS log."""
    phone_number: str
    content: str
    template_id: UUID | None = None
    campaign_id: UUID | None = None


class SendSMSRequest(SMSLogBase):
    """Schema for sending a single SMS."""
    contact_id: UUID | None = None


class SMSLogResponse(BaseModel):
    """Schema for SMS log response."""
    id: UUID
    tenant_id: UUID
    contact_id: UUID | None = None
    phone_number: str
    direction: str  # inbound, outbound
    content: str
    template_id: UUID | None = None
    status: str  # pending, sent, delivered, failed
    provider_message_id: str | None = None
    sent_at: datetime | None = None
    delivered_at: datetime | None = None
    failed_at: datetime | None = None
    failure_reason: str | None = None
    campaign_id: UUID | None = None
    provider_name: str | None = None
    cost: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime | None = None

    class Config:
        from_attributes = True


class SMSLogListResponse(BaseModel):
    """Schema for paginated SMS log list."""
    logs: list[SMSLogResponse]
    total_count: int
    page: int
    page_size: int
    has_next: bool
    has_prev: bool


class BulkSendSMSRequest(BaseModel):
    """Schema for bulk SMS sending."""
    contact_ids: list[UUID] | None = None
    phone_numbers: list[str] | None = None
    segment: str | None = None
    category_id: UUID | None = None
    template_id: UUID | None = None
    content: str | None = None
    campaign_id: UUID | None = None
    schedule_at: datetime | None = None


class BulkSendSMSResponse(BaseModel):
    """Schema for bulk SMS response."""
    total_queued: int
    estimated_cost: int
    job_id: UUID | None = None


class SMSDeliveryStatusRequest(BaseModel):
    """Schema for checking SMS delivery status."""
    message_ids: list[str]


class SMSDeliveryStatusResponse(BaseModel):
    """Schema for SMS delivery status response."""
    statuses: dict[str, str]
    total_delivered: int
    total_failed: int
    total_pending: int


# ============================================================================
# SMS Template Schemas
# ============================================================================

class SMSTemplateBase(BaseModel):
    """Base schema for SMS template."""
    name: str
    content: str
    description: str | None = None
    category: str | None = None
    target_segments: list[str] = Field(default_factory=list)
    target_products: list[str] = Field(default_factory=list)
    variant_group: str | None = None
    variant_name: str | None = None
    is_active: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class CreateSMSTemplateRequest(SMSTemplateBase):
    """Schema for creating an SMS template."""
    pass


class UpdateSMSTemplateRequest(BaseModel):
    """Schema for updating an SMS template."""
    name: str | None = None
    content: str | None = None
    description: str | None = None
    category: str | None = None
    target_segments: list[str] | None = None
    target_products: list[str] | None = None
    variant_group: str | None = None
    variant_name: str | None = None
    is_active: bool | None = None
    metadata: dict[str, Any] | None = None


class SMSTemplateResponse(SMSTemplateBase):
    """Schema for SMS template response."""
    id: UUID
    tenant_id: UUID
    times_used: int = 0
    last_used_at: datetime | None = None
    character_count: int
    sms_parts: int
    created_at: datetime
    updated_at: datetime | None = None

    class Config:
        from_attributes = True


class SMSTemplateListResponse(BaseModel):
    """Schema for SMS template list."""
    templates: list[SMSTemplateResponse]
    total_count: int


class TemplatePerformanceResponse(BaseModel):
    """Schema for template performance metrics."""
    template_id: UUID
    template_name: str
    times_used: int
    delivery_rate: float
    response_rate: float
    conversion_rate: float


# ============================================================================
# Call Log Schemas
# ============================================================================

class CallLogBase(BaseModel):
    """Base schema for call log."""
    phone_number: str
    contact_name: str | None = None
    call_type: str  # inbound, outbound
    source: str  # mobile, voip
    duration_seconds: int = 0
    call_time: datetime


class ImportCallLogItem(CallLogBase):
    """Schema for individual call log import item."""
    salesperson_phone: str | None = None
    salesperson_name: str | None = None
    is_answered: bool = False
    voip_unique_id: str | None = None
    recording_url: str | None = None


class ImportCallLogsRequest(BaseModel):
    """Schema for importing call logs."""
    source_type: str  # csv, json, voip_api
    calls: list[ImportCallLogItem] | None = None
    file_content: str | None = None
    successful_call_threshold: int = 90  # seconds


class ImportCallLogsResponse(BaseModel):
    """Schema for call log import response."""
    total_imported: int
    success_count: int
    error_count: int
    matched_contacts: int
    new_contacts: int
    errors: list[str] = Field(default_factory=list)


class CallLogResponse(BaseModel):
    """Schema for call log response."""
    id: UUID
    tenant_id: UUID
    contact_id: UUID | None = None
    phone_number: str
    contact_name: str | None = None
    call_type: str
    source: str
    duration_seconds: int
    call_time: datetime
    answered_at: datetime | None = None
    ended_at: datetime | None = None
    salesperson_id: UUID | None = None
    salesperson_phone: str | None = None
    salesperson_name: str | None = None
    is_answered: bool = False
    is_successful: bool
    voip_unique_id: str | None = None
    recording_url: str | None = None
    notes: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime

    class Config:
        from_attributes = True


class CallLogListResponse(BaseModel):
    """Schema for paginated call log list."""
    calls: list[CallLogResponse]
    total_count: int
    page: int
    page_size: int
    has_next: bool
    has_prev: bool


# ============================================================================
# VoIP Integration Schemas
# ============================================================================

class VoIPConfigBase(BaseModel):
    """Base schema for VoIP configuration."""
    provider_type: str  # asterisk, self_hosted, other
    host: str
    port: int = 5060
    username: str | None = None
    api_key: str | None = None
    is_active: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class CreateVoIPConfigRequest(VoIPConfigBase):
    """Schema for creating VoIP configuration."""
    password: str | None = None


class VoIPConfigResponse(VoIPConfigBase):
    """Schema for VoIP config response."""
    id: UUID
    tenant_id: UUID
    last_sync_at: datetime | None = None
    created_at: datetime
    updated_at: datetime | None = None

    class Config:
        from_attributes = True


class SyncVoIPLogsRequest(BaseModel):
    """Schema for syncing VoIP logs."""
    from_date: datetime | None = None
    to_date: datetime | None = None


class SyncVoIPLogsResponse(BaseModel):
    """Schema for VoIP sync response."""
    total_fetched: int
    new_records: int
    updated_records: int
    errors: list[str] = Field(default_factory=list)


# ============================================================================
# Communication Statistics Schemas
# ============================================================================

class SMSStatsResponse(BaseModel):
    """Schema for SMS statistics."""
    period_start: datetime
    period_end: datetime
    total_sent: int
    total_delivered: int
    total_failed: int
    delivery_rate: float
    total_cost: int
    by_status: dict[str, int]
    by_template: list[dict[str, Any]]


class CallStatsResponse(BaseModel):
    """Schema for call statistics."""
    period_start: datetime
    period_end: datetime
    total_calls: int
    total_answered: int
    total_successful: int
    total_duration: int
    average_duration: float
    answer_rate: float
    success_rate: float
    by_type: dict[str, int]
    by_salesperson: list[dict[str, Any]]


class CommunicationTimelineResponse(BaseModel):
    """Schema for contact communication timeline."""
    contact_id: UUID
    phone_number: str
    events: list[dict[str, Any]]

