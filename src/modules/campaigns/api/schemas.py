"""
Campaigns API Schemas

Pydantic schemas for campaign management.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


# ============================================================================
# Campaign Schemas
# ============================================================================

class CampaignTargetingSchema(BaseModel):
    """Schema for campaign targeting criteria."""
    segments: list[str] = Field(default_factory=list)
    categories: list[UUID] = Field(default_factory=list)
    sources: list[UUID] = Field(default_factory=list)
    stages: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    exclude_contacted_within_days: int | None = None
    max_contacts: int | None = None


class CampaignScheduleSchema(BaseModel):
    """Schema for campaign schedule."""
    start_at: datetime
    end_at: datetime | None = None
    send_times: list[str] = Field(default_factory=list)  # ["09:00", "14:00"]
    days_of_week: list[int] = Field(default_factory=list)  # 0=Monday, 6=Sunday
    timezone: str = "Asia/Tehran"


class CampaignBase(BaseModel):
    """Base schema for campaign."""
    name: str
    description: str | None = None
    campaign_type: str  # sms, call, mixed
    template_id: UUID | None = None
    content: str | None = None
    targeting: CampaignTargetingSchema = Field(default_factory=CampaignTargetingSchema)
    schedule: CampaignScheduleSchema | None = None
    is_active: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class CreateCampaignRequest(CampaignBase):
    """Schema for creating a campaign."""
    pass


class UpdateCampaignRequest(BaseModel):
    """Schema for updating a campaign."""
    name: str | None = None
    description: str | None = None
    template_id: UUID | None = None
    content: str | None = None
    targeting: CampaignTargetingSchema | None = None
    schedule: CampaignScheduleSchema | None = None
    is_active: bool | None = None
    metadata: dict[str, Any] | None = None


class CampaignResponse(CampaignBase):
    """Schema for campaign response."""
    id: UUID
    tenant_id: UUID
    status: str  # draft, scheduled, running, paused, completed, cancelled
    process_instance_id: str | None = None
    total_recipients: int = 0
    sent_count: int = 0
    delivered_count: int = 0
    failed_count: int = 0
    response_count: int = 0
    conversion_count: int = 0
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime | None = None

    class Config:
        from_attributes = True


class CampaignListResponse(BaseModel):
    """Schema for campaign list."""
    campaigns: list[CampaignResponse]
    total_count: int
    page: int
    page_size: int


class CampaignStatsResponse(BaseModel):
    """Schema for campaign statistics."""
    campaign_id: UUID
    campaign_name: str
    status: str
    total_recipients: int
    sent_count: int
    delivered_count: int
    delivery_rate: float
    failed_count: int
    response_count: int
    response_rate: float
    conversion_count: int
    conversion_rate: float
    cost: int
    revenue: int
    roi: float
    by_segment: list[dict[str, Any]]
    by_day: list[dict[str, Any]]


class CampaignRecipientResponse(BaseModel):
    """Schema for campaign recipient."""
    contact_id: UUID
    phone_number: str
    name: str | None = None
    segment: str | None = None
    status: str  # pending, sent, delivered, failed, responded, converted
    sent_at: datetime | None = None
    delivered_at: datetime | None = None
    responded_at: datetime | None = None
    converted_at: datetime | None = None


class CampaignRecipientsListResponse(BaseModel):
    """Schema for campaign recipients list."""
    recipients: list[CampaignRecipientResponse]
    total_count: int
    page: int
    page_size: int


class ABTestConfigSchema(BaseModel):
    """Schema for A/B test configuration."""
    variants: list[dict[str, Any]]  # [{name, template_id, content, percentage}]
    test_size_percent: float = 20.0
    winner_metric: str = "conversion_rate"  # delivery_rate, response_rate, conversion_rate
    auto_select_winner: bool = True
    test_duration_hours: int = 24


class CreateABTestCampaignRequest(CreateCampaignRequest):
    """Schema for creating an A/B test campaign."""
    ab_test_config: ABTestConfigSchema


class ABTestResultsResponse(BaseModel):
    """Schema for A/B test results."""
    campaign_id: UUID
    variants: list[dict[str, Any]]
    winner: str | None = None
    confidence_level: float | None = None
    test_completed: bool

