"""
Segmentation API Routes

FastAPI routes for RFM segmentation endpoints — wired to real database.
"""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_current_tenant_id, get_db_session

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

router = APIRouter(tags=["segmentation"])


# ─────────────── Dependency helpers ───────────────

async def _get_contact_repo(session: AsyncSession, tenant_id: UUID):
    from src.modules.leads.infrastructure.repositories import ContactRepository
    return ContactRepository(session, tenant_id)


SEGMENT_NAMES_FA = {
    "champions": "قهرمانان",
    "loyal": "وفادار",
    "potential_loyalist": "وفادار بالقوه",
    "new_customers": "مشتریان جدید",
    "promising": "امیدوارکننده",
    "need_attention": "نیاز به توجه",
    "about_to_sleep": "در آستانه خواب",
    "at_risk": "در خطر",
    "cant_lose": "نباید از دست داد",
    "hibernating": "خواب",
    "lost": "از دست رفته",
}


@router.get("/config", response_model=RFMConfigResponse)
async def get_rfm_config(
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
):
    """Get RFM configuration for tenant."""
    return RFMConfigResponse(
        tenant_id=tenant_id,
        config=RFMConfigSchema(),
    )


@router.put("/config", response_model=RFMConfigResponse)
async def update_rfm_config(
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
    request: UpdateRFMConfigRequest,
):
    """Update RFM configuration for tenant."""
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
    return RFMConfigResponse(tenant_id=tenant_id, config=config)


@router.post("/analyze", response_model=RFMAnalysisResultResponse)
async def run_rfm_analysis(
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    request: RunRFMAnalysisRequest = None,
):
    """Run RFM analysis for all contacts — from real database."""
    contact_repo = await _get_contact_repo(session, tenant_id)

    # Get RFM segment distribution from DB
    rfm_dist = await contact_repo.get_rfm_distribution()
    total_contacts = await contact_repo.count()
    total_with_segment = sum(rfm_dist.values())

    segment_distribution = []
    for seg_name, count in rfm_dist.items():
        pct = round(count / total_with_segment * 100, 2) if total_with_segment > 0 else 0
        segment_distribution.append(SegmentCountSchema(
            segment=seg_name,
            segment_name_fa=SEGMENT_NAMES_FA.get(seg_name, seg_name),
            count=count,
            percentage=pct,
        ))

    return RFMAnalysisResultResponse(
        tenant_id=tenant_id,
        analysis_date=datetime.utcnow(),
        total_contacts_analyzed=total_contacts,
        contacts_with_purchases=total_with_segment,
        total_revenue=0,
        average_clv=0,
        segment_distribution=segment_distribution,
    )


@router.get("/distribution", response_model=SegmentDistributionResponse)
async def get_segment_distribution(
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
):
    """Get current segment distribution — from real database."""
    contact_repo = await _get_contact_repo(session, tenant_id)
    rfm_dist = await contact_repo.get_rfm_distribution()
    total = sum(rfm_dist.values()) or 1

    segments = []
    for segment in RFMSegment:
        count = rfm_dist.get(segment.value, 0)
        rec = SEGMENT_RECOMMENDATIONS.get(segment)
        fa_name = rec.segment_name_fa if rec else SEGMENT_NAMES_FA.get(segment.value, segment.value)
        segments.append(SegmentCountSchema(
            segment=segment.value,
            segment_name_fa=fa_name,
            count=count,
            percentage=round(count / total * 100, 2),
        ))

    return SegmentDistributionResponse(
        tenant_id=tenant_id,
        analysis_date=datetime.utcnow(),
        total_contacts=total,
        segments=segments,
    )


@router.get("/profiles", response_model=RFMProfileListResponse)
async def get_rfm_profiles(
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    segment: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    """Get RFM profiles — from real database."""
    contact_repo = await _get_contact_repo(session, tenant_id)
    skip = (page - 1) * page_size

    if segment:
        contacts = await contact_repo.get_by_segment(segment, skip=skip, limit=page_size)
    else:
        contacts = await contact_repo.get_all(skip=skip, limit=page_size)

    profiles = []
    for c in contacts:
        phone = c.phone_number.normalized if hasattr(c.phone_number, 'normalized') else str(c.phone_number)
        profiles.append(RFMProfileResponse(
            id=c.id,
            contact_id=c.id,
            phone_number=phone,
            last_purchase_date=c.last_purchase_at,
            days_since_last_purchase=0,
            purchase_count=c.total_paid_invoices or 0,
            total_spend=c.total_revenue or 0,
            average_order_value=c.total_revenue // c.total_paid_invoices if c.total_paid_invoices else 0,
            rfm_score=RFMScoreSchema(
                recency=c.recency_score or 0,
                frequency=c.frequency_score or 0,
                monetary=c.monetary_score or 0,
                rfm_string=c.rfm_score or "000",
                total_score=(c.recency_score or 0) + (c.frequency_score or 0) + (c.monetary_score or 0),
            ),
            segment=c.rfm_segment or "unscored",
            segment_name_fa=SEGMENT_NAMES_FA.get(c.rfm_segment or "", "نامشخص"),
            engagement_score=0,
            customer_lifetime_value=c.total_revenue or 0,
        ))

    total_count = await contact_repo.count()

    return RFMProfileListResponse(
        profiles=profiles,
        total_count=total_count,
        page=page,
        page_size=page_size,
    )


@router.get("/profiles/{contact_id}", response_model=RFMProfileResponse)
async def get_contact_rfm_profile(
    contact_id: UUID,
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
):
    """Get RFM profile for a specific contact — from real database."""
    contact_repo = await _get_contact_repo(session, tenant_id)
    contact = await contact_repo.get(contact_id)
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    phone = contact.phone_number.normalized if hasattr(contact.phone_number, 'normalized') else str(contact.phone_number)
    return RFMProfileResponse(
        id=contact.id,
        contact_id=contact.id,
        phone_number=phone,
        last_purchase_date=contact.last_purchase_at,
        days_since_last_purchase=0,
        purchase_count=contact.total_paid_invoices or 0,
        total_spend=contact.total_revenue or 0,
        average_order_value=contact.total_revenue // contact.total_paid_invoices if contact.total_paid_invoices else 0,
        rfm_score=RFMScoreSchema(
            recency=contact.recency_score or 0,
            frequency=contact.frequency_score or 0,
            monetary=contact.monetary_score or 0,
            rfm_string=contact.rfm_score or "000",
            total_score=(contact.recency_score or 0) + (contact.frequency_score or 0) + (contact.monetary_score or 0),
        ),
        segment=contact.rfm_segment or "unscored",
        segment_name_fa=SEGMENT_NAMES_FA.get(contact.rfm_segment or "", "نامشخص"),
        engagement_score=0,
        customer_lifetime_value=contact.total_revenue or 0,
    )


@router.get("/recommendations", response_model=AllRecommendationsResponse)
async def get_all_recommendations():
    """Get marketing recommendations for all segments."""
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
    """Get marketing recommendation for a specific segment."""
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
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    limit: int = Query(default=5, ge=1, le=20),
):
    """Get personalized product recommendations for a contact — from real database."""
    contact_repo = await _get_contact_repo(session, tenant_id)
    contact = await contact_repo.get(contact_id)
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    segment = contact.rfm_segment or "new_customers"
    rec = None
    try:
        rec = SEGMENT_RECOMMENDATIONS.get(RFMSegment(segment))
    except (ValueError, KeyError):
        pass

    recommendations = []
    if rec and rec.recommended_products:
        for i, prod in enumerate(rec.recommended_products[:limit]):
            recommendations.append(ProductRecommendationSchema(
                product_id=f"prod-{i+1:03d}",
                name=prod,
                category="recommended",
                price=0,
                recommendation_reason=f"پیشنهاد برای بخش {SEGMENT_NAMES_FA.get(segment, segment)}",
                discount_percent=rec.max_discount_percent or 0,
            ))

    return ContactRecommendationsResponse(
        contact_id=contact_id,
        segment=segment,
        recommendations=recommendations,
    )


@router.get("/migration-report", response_model=MigrationReportResponse)
async def get_segment_migration_report(
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    months: int = Query(default=1, ge=1, le=12),
):
    """Get report on segment migrations over time."""
    contact_repo = await _get_contact_repo(session, tenant_id)
    total = await contact_repo.count()

    # For now return placeholder — full migration tracking requires historical snapshots
    return MigrationReportResponse(
        period_months=months,
        total_contacts=total,
        improved=0,
        declined=0,
        unchanged=total,
        migrations=[],
    )


@router.post("/campaign-contacts", response_model=CampaignContactsResponse)
async def get_contacts_for_campaign(
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    request: CampaignContactsRequest,
):
    """Get contacts suitable for a specific campaign type — from real database."""
    contact_repo = await _get_contact_repo(session, tenant_id)

    # Get contacts in the target segments
    all_contacts = []
    for seg in (request.target_segments or []):
        contacts = await contact_repo.get_by_segment(seg, limit=100)
        all_contacts.extend(contacts)

    contact_dicts = [
        {
            "contact_id": str(c.id),
            "phone_number": c.phone_number.normalized if hasattr(c.phone_number, 'normalized') else str(c.phone_number),
            "segment": c.rfm_segment or "unknown",
            "name": c.name or "",
        }
        for c in all_contacts
    ]

    return CampaignContactsResponse(
        campaign_type=request.campaign_type,
        total_contacts=len(contact_dicts),
        contacts=contact_dicts,
    )


@router.get("/high-priority", response_model=RFMProfileListResponse)
async def get_high_priority_contacts(
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    limit: int = Query(default=50, ge=1, le=100),
):
    """Get contacts prioritized for immediate marketing action — from real database."""
    contact_repo = await _get_contact_repo(session, tenant_id)

    # High priority = at_risk + cant_lose segments
    profiles = []
    for seg in ["at_risk", "cant_lose", "about_to_sleep"]:
        contacts = await contact_repo.get_by_segment(seg, limit=limit)
        for c in contacts:
            phone = c.phone_number.normalized if hasattr(c.phone_number, 'normalized') else str(c.phone_number)
            profiles.append(RFMProfileResponse(
                id=c.id,
                contact_id=c.id,
                phone_number=phone,
                last_purchase_date=c.last_purchase_at,
                days_since_last_purchase=0,
                purchase_count=c.total_paid_invoices or 0,
                total_spend=c.total_revenue or 0,
                average_order_value=c.total_revenue // c.total_paid_invoices if c.total_paid_invoices else 0,
                rfm_score=RFMScoreSchema(
                    recency=c.recency_score or 0,
                    frequency=c.frequency_score or 0,
                    monetary=c.monetary_score or 0,
                    rfm_string=c.rfm_score or "000",
                    total_score=(c.recency_score or 0) + (c.frequency_score or 0) + (c.monetary_score or 0),
                ),
                segment=c.rfm_segment or "unscored",
                segment_name_fa=SEGMENT_NAMES_FA.get(c.rfm_segment or "", "نامشخص"),
                engagement_score=0,
                customer_lifetime_value=c.total_revenue or 0,
            ))

    return RFMProfileListResponse(
        profiles=profiles[:limit],
        total_count=len(profiles),
        page=1,
        page_size=limit,
    )
