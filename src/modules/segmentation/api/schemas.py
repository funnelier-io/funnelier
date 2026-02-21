"""
Segmentation API Schemas
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class RFMScoreSchema(BaseModel):
    """RFM Score."""

    recency: int
    frequency: int
    monetary: int
    rfm_string: str
    total_score: int


class RFMProfileResponse(BaseModel):
    """Response for RFM profile."""

    id: UUID
    contact_id: UUID
    phone_number: str

    # Metrics
    last_purchase_date: datetime | None = None
    days_since_last_purchase: int | None = None
    purchase_count: int
    total_spend: float
    average_order_value: float

    # RFM
    rfm_score: RFMScoreSchema | None = None
    segment: str | None = None
    segment_name_fa: str | None = None

    # Engagement
    engagement_score: int = 0
    customer_lifetime_value: float = 0.0


class RFMProfileListResponse(BaseModel):
    """Response for list of RFM profiles."""

    profiles: list[RFMProfileResponse]
    total_count: int
    page: int
    page_size: int


class SegmentCountSchema(BaseModel):
    """Segment count."""

    segment: str
    segment_name_fa: str
    count: int
    percentage: float


class SegmentDistributionResponse(BaseModel):
    """Response for segment distribution."""

    tenant_id: UUID
    analysis_date: datetime
    total_contacts: int
    segments: list[SegmentCountSchema]


class SegmentRecommendationResponse(BaseModel):
    """Response for segment recommendation."""

    segment: str
    segment_name_fa: str
    description_fa: str

    recommended_message_types: list[str]
    recommended_products: list[str]
    contact_frequency: str
    channel_priority: list[str]

    discount_allowed: bool
    max_discount_percent: int


class AllRecommendationsResponse(BaseModel):
    """Response for all segment recommendations."""

    recommendations: list[SegmentRecommendationResponse]


class ProductRecommendationSchema(BaseModel):
    """Product recommendation."""

    product_id: str
    name: str
    category: str
    price: float
    recommendation_reason: str
    discount_percent: int = 0


class ContactRecommendationsResponse(BaseModel):
    """Response for contact product recommendations."""

    contact_id: UUID
    segment: str | None = None
    recommendations: list[ProductRecommendationSchema]


class SegmentMigrationSchema(BaseModel):
    """Segment migration data."""

    from_segment: str
    to_segment: str
    count: int


class MigrationReportResponse(BaseModel):
    """Response for segment migration report."""

    period_months: int
    total_contacts: int
    improved: int
    declined: int
    unchanged: int
    migrations: list[SegmentMigrationSchema]


class RFMConfigSchema(BaseModel):
    """RFM configuration."""

    recency_thresholds: list[int] = Field(default=[14, 30, 60, 90])
    frequency_thresholds: list[int] = Field(default=[1, 2, 4, 8])
    monetary_thresholds: list[float] = Field(
        default=[100_000_000, 500_000_000, 1_000_000_000, 2_000_000_000]
    )
    analysis_period_months: int = 12
    high_value_threshold: float = 1_000_000_000
    recent_days: int = 14


class RFMConfigResponse(BaseModel):
    """Response for RFM config."""

    tenant_id: UUID
    config: RFMConfigSchema


class UpdateRFMConfigRequest(BaseModel):
    """Request to update RFM config."""

    recency_thresholds: list[int] | None = None
    frequency_thresholds: list[int] | None = None
    monetary_thresholds: list[float] | None = None
    analysis_period_months: int | None = None
    high_value_threshold: float | None = None
    recent_days: int | None = None


class RunRFMAnalysisRequest(BaseModel):
    """Request to run RFM analysis."""

    limit: int | None = None


class RFMAnalysisResultResponse(BaseModel):
    """Response for RFM analysis result."""

    tenant_id: UUID
    analysis_date: datetime
    total_contacts_analyzed: int
    contacts_with_purchases: int
    total_revenue: float
    average_clv: float
    segment_distribution: list[SegmentCountSchema]


class CampaignContactsRequest(BaseModel):
    """Request to get contacts for campaign."""

    campaign_type: str  # promotional, retention, win_back, vip, upsell, new_product
    limit: int = 1000


class CampaignContactsResponse(BaseModel):
    """Response for campaign contacts."""

    campaign_type: str
    total_contacts: int
    contacts: list[RFMProfileResponse]

