"""
Segmentation API Routes

FastAPI routes for RFM segmentation endpoints.
"""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from src.core.domain import RFMSegment

from ..domain import SEGMENT_RECOMMENDATIONS

from .schemas import (
    AllRecommendationsResponse,
    CampaignContactsRequest,
    CampaignContactsResponse,
    ContactRecommendationsResponse,
    MigrationReportResponse,
    ProductRecommendationSchema,
    RFMAnalysisResultResponse,
    RFMConfigResponse,
    RFMConfigSchema,
    RFMProfileListResponse,
    RFMProfileResponse,
    RFMScoreSchema,
    RunRFMAnalysisRequest,
    SegmentCountSchema,
    SegmentDistributionResponse,
    SegmentMigrationSchema,
    SegmentRecommendationResponse,
    UpdateRFMConfigRequest,
)

router = APIRouter(prefix="/segmentation", tags=["segmentation"])


# Dependency for getting current tenant (placeholder)
async def get_current_tenant() -> UUID:
    """Get current tenant from auth context."""
    return UUID("00000000-0000-0000-0000-000000000001")


@router.get("/config", response_model=RFMConfigResponse)
async def get_rfm_config(
    tenant_id: Annotated[UUID, Depends(get_current_tenant)],
):
    """
    Get RFM configuration for tenant.
    """
    return RFMConfigResponse(
        tenant_id=tenant_id,
        config=RFMConfigSchema(),
    )


@router.put("/config", response_model=RFMConfigResponse)
async def update_rfm_config(
    tenant_id: Annotated[UUID, Depends(get_current_tenant)],
    request: UpdateRFMConfigRequest,
):
    """
    Update RFM configuration for tenant.
    """
    config = RFMConfigSchema()

    if request.recency_thresholds:
        config.recency_thresholds = request.recency_thresholds
    if request.frequency_thresholds:
        config.frequency_thresholds = request.frequency_thresholds
    if request.monetary_thresholds:
        config.monetary_thresholds = request.monetary_thresholds
    if request.analysis_period_months:
        config.analysis_period_months = request.analysis_period_months
    if request.high_value_threshold:
        config.high_value_threshold = request.high_value_threshold
    if request.recent_days:
        config.recent_days = request.recent_days

    return RFMConfigResponse(
        tenant_id=tenant_id,
        config=config,
    )


@router.post("/analyze", response_model=RFMAnalysisResultResponse)
async def run_rfm_analysis(
    tenant_id: Annotated[UUID, Depends(get_current_tenant)],
    request: RunRFMAnalysisRequest = None,
):
    """
    Run RFM analysis for all contacts.
    """
    # Placeholder response
    return RFMAnalysisResultResponse(
        tenant_id=tenant_id,
        analysis_date=datetime.utcnow(),
        total_contacts_analyzed=1500,
        contacts_with_purchases=800,
        total_revenue=5_000_000_000,
        average_clv=6_250_000,
        segment_distribution=[
            SegmentCountSchema(
                segment="champions", segment_name_fa="قهرمانان", count=50, percentage=6.25
            ),
            SegmentCountSchema(
                segment="loyal", segment_name_fa="وفادار", count=100, percentage=12.5
            ),
            SegmentCountSchema(
                segment="potential_loyalist",
                segment_name_fa="وفادار بالقوه",
                count=150,
                percentage=18.75,
            ),
            SegmentCountSchema(
                segment="new_customers", segment_name_fa="مشتریان جدید", count=80, percentage=10.0
            ),
            SegmentCountSchema(
                segment="at_risk", segment_name_fa="در خطر", count=120, percentage=15.0
            ),
            SegmentCountSchema(
                segment="hibernating", segment_name_fa="خواب", count=200, percentage=25.0
            ),
            SegmentCountSchema(
                segment="lost", segment_name_fa="از دست رفته", count=100, percentage=12.5
            ),
        ],
    )


@router.get("/distribution", response_model=SegmentDistributionResponse)
async def get_segment_distribution(
    tenant_id: Annotated[UUID, Depends(get_current_tenant)],
):
    """
    Get current segment distribution.
    """
    segments = []
    for segment in RFMSegment:
        rec = SEGMENT_RECOMMENDATIONS.get(segment)
        if rec:
            segments.append(
                SegmentCountSchema(
                    segment=segment.value,
                    segment_name_fa=rec.segment_name_fa,
                    count=100,  # Placeholder
                    percentage=9.09,  # Placeholder
                )
            )

    return SegmentDistributionResponse(
        tenant_id=tenant_id,
        analysis_date=datetime.utcnow(),
        total_contacts=1100,
        segments=segments,
    )


@router.get("/profiles", response_model=RFMProfileListResponse)
async def get_rfm_profiles(
    tenant_id: Annotated[UUID, Depends(get_current_tenant)],
    segment: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    """
    Get RFM profiles with optional filtering.
    """
    # Placeholder response
    return RFMProfileListResponse(
        profiles=[],
        total_count=0,
        page=page,
        page_size=page_size,
    )


@router.get("/profiles/{contact_id}", response_model=RFMProfileResponse)
async def get_contact_rfm_profile(
    contact_id: UUID,
    tenant_id: Annotated[UUID, Depends(get_current_tenant)],
):
    """
    Get RFM profile for a specific contact.
    """
    # Placeholder response
    return RFMProfileResponse(
        id=UUID("00000000-0000-0000-0000-000000000001"),
        contact_id=contact_id,
        phone_number="989123456789",
        last_purchase_date=datetime.utcnow(),
        days_since_last_purchase=7,
        purchase_count=5,
        total_spend=500_000_000,
        average_order_value=100_000_000,
        rfm_score=RFMScoreSchema(
            recency=5,
            frequency=3,
            monetary=4,
            rfm_string="534",
            total_score=12,
        ),
        segment="loyal",
        segment_name_fa="وفادار",
        engagement_score=4,
        customer_lifetime_value=600_000_000,
    )


@router.get("/recommendations", response_model=AllRecommendationsResponse)
async def get_all_recommendations():
    """
    Get marketing recommendations for all segments.
    """
    recommendations = []
    for segment in RFMSegment:
        rec = SEGMENT_RECOMMENDATIONS.get(segment)
        if rec:
            recommendations.append(
                SegmentRecommendationResponse(
                    segment=segment.value,
                    segment_name_fa=rec.segment_name_fa,
                    description_fa=rec.description_fa,
                    recommended_message_types=rec.recommended_message_types,
                    recommended_products=rec.recommended_products,
                    contact_frequency=rec.contact_frequency,
                    channel_priority=rec.channel_priority,
                    discount_allowed=rec.discount_allowed,
                    max_discount_percent=rec.max_discount_percent,
                )
            )

    return AllRecommendationsResponse(recommendations=recommendations)


@router.get("/recommendations/{segment}", response_model=SegmentRecommendationResponse)
async def get_segment_recommendation(segment: str):
    """
    Get marketing recommendation for a specific segment.
    """
    try:
        segment_enum = RFMSegment(segment)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid segment: {segment}")

    rec = SEGMENT_RECOMMENDATIONS.get(segment_enum)
    if not rec:
        raise HTTPException(status_code=404, detail=f"Recommendation not found for: {segment}")

    return SegmentRecommendationResponse(
        segment=segment_enum.value,
        segment_name_fa=rec.segment_name_fa,
        description_fa=rec.description_fa,
        recommended_message_types=rec.recommended_message_types,
        recommended_products=rec.recommended_products,
        contact_frequency=rec.contact_frequency,
        channel_priority=rec.channel_priority,
        discount_allowed=rec.discount_allowed,
        max_discount_percent=rec.max_discount_percent,
    )


@router.get("/products/{contact_id}", response_model=ContactRecommendationsResponse)
async def get_contact_product_recommendations(
    contact_id: UUID,
    tenant_id: Annotated[UUID, Depends(get_current_tenant)],
    limit: int = Query(default=5, ge=1, le=20),
):
    """
    Get personalized product recommendations for a contact.
    """
    # Placeholder response
    return ContactRecommendationsResponse(
        contact_id=contact_id,
        segment="loyal",
        recommendations=[
            ProductRecommendationSchema(
                product_id="prod-001",
                name="سیمان تیپ 2",
                category="cement",
                price=500_000,
                recommendation_reason="محصول مکمل",
                discount_percent=5,
            ),
            ProductRecommendationSchema(
                product_id="prod-002",
                name="کاشی 60x60",
                category="tile",
                price=150_000,
                recommendation_reason="پیشنهاد ویژه",
                discount_percent=10,
            ),
        ],
    )


@router.get("/migration-report", response_model=MigrationReportResponse)
async def get_segment_migration_report(
    tenant_id: Annotated[UUID, Depends(get_current_tenant)],
    months: int = Query(default=1, ge=1, le=12),
):
    """
    Get report on segment migrations over time.
    """
    return MigrationReportResponse(
        period_months=months,
        total_contacts=800,
        improved=120,
        declined=80,
        unchanged=600,
        migrations=[
            SegmentMigrationSchema(
                from_segment="promising", to_segment="loyal", count=30
            ),
            SegmentMigrationSchema(
                from_segment="at_risk", to_segment="hibernating", count=25
            ),
            SegmentMigrationSchema(
                from_segment="loyal", to_segment="champions", count=20
            ),
        ],
    )


@router.post("/campaign-contacts", response_model=CampaignContactsResponse)
async def get_contacts_for_campaign(
    tenant_id: Annotated[UUID, Depends(get_current_tenant)],
    request: CampaignContactsRequest,
):
    """
    Get contacts suitable for a specific campaign type.
    """
    return CampaignContactsResponse(
        campaign_type=request.campaign_type,
        total_contacts=0,
        contacts=[],
    )


@router.get("/high-priority", response_model=RFMProfileListResponse)
async def get_high_priority_contacts(
    tenant_id: Annotated[UUID, Depends(get_current_tenant)],
    limit: int = Query(default=50, ge=1, le=100),
):
    """
    Get contacts prioritized for immediate marketing action.
    """
    return RFMProfileListResponse(
        profiles=[],
        total_count=0,
        page=1,
        page_size=limit,
    )

