"""
API Routes - Segments Module
RFM segmentation endpoints
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Query
from pydantic import BaseModel

router = APIRouter()


# Response schemas
class RFMConfigResponse(BaseModel):
    id: UUID
    recency_thresholds: dict[int, int]
    frequency_thresholds: dict[int, int]
    monetary_thresholds: dict[int, int]
    updated_at: datetime


class RFMConfigUpdate(BaseModel):
    recency_score_5_max: int | None = None
    recency_score_4_max: int | None = None
    recency_score_3_max: int | None = None
    recency_score_2_max: int | None = None
    frequency_score_5_min: int | None = None
    frequency_score_4_min: int | None = None
    frequency_score_3_min: int | None = None
    frequency_score_2_min: int | None = None
    monetary_score_5_min: int | None = None
    monetary_score_4_min: int | None = None
    monetary_score_3_min: int | None = None
    monetary_score_2_min: int | None = None


class SegmentSummary(BaseModel):
    segment: str
    display_name: str
    description: str
    contact_count: int
    percentage: float
    total_revenue: int
    average_order_value: int
    recommended_action: str
    priority: int


class SegmentDistributionResponse(BaseModel):
    total_contacts: int
    segments: list[SegmentSummary]
    calculated_at: datetime


class ContactRFMResponse(BaseModel):
    contact_id: UUID
    phone_number: str
    recency_score: int
    frequency_score: int
    monetary_score: int
    rfm_score: str
    segment: str
    days_since_last_purchase: int | None
    total_purchases: int
    total_spend: int
    calculated_at: datetime


class SegmentMigration(BaseModel):
    from_segment: str
    to_segment: str
    count: int


class SegmentMovementResponse(BaseModel):
    period_start: datetime
    period_end: datetime
    migrations: list[SegmentMigration]
    improved_count: int
    declined_count: int


class ProductRecommendationResponse(BaseModel):
    product_id: UUID
    product_name: str
    product_category: str
    score: float
    reason: str


class TemplateRecommendationResponse(BaseModel):
    template_id: UUID
    template_name: str
    category: str
    score: float
    reason: str


class SegmentRecommendationsResponse(BaseModel):
    segment: str
    recommended_action: str
    urgency: str
    products: list[ProductRecommendationResponse]
    templates: list[TemplateRecommendationResponse]


# Endpoints
@router.get("/distribution", response_model=SegmentDistributionResponse)
async def get_segment_distribution() -> SegmentDistributionResponse:
    """
    Get distribution of contacts across RFM segments.
    """
    # Segment metadata
    segment_info = {
        "champions": ("قهرمانان", "بهترین مشتریان با خرید اخیر و مکرر"),
        "loyal": ("وفادار", "مشتریان با خرید منظم"),
        "potential_loyalist": ("وفادار بالقوه", "مشتریان جدید با پتانسیل بالا"),
        "new_customers": ("مشتریان جدید", "به تازگی اولین خرید را انجام داده‌اند"),
        "promising": ("امیدوارکننده", "مشتریان با علاقه اولیه"),
        "need_attention": ("نیاز به توجه", "مشتریان متوسط در حال کاهش"),
        "about_to_sleep": ("در آستانه خواب", "مشتریان کم‌فعال"),
        "at_risk": ("در معرض خطر", "مشتریان ارزشمند در حال از دست رفتن"),
        "cant_lose": ("نباید از دست بروند", "بهترین‌ها که دیگر خرید نمی‌کنند"),
        "hibernating": ("خواب زمستانی", "مشتریان غیرفعال"),
        "lost": ("از دست رفته", "مشتریان بدون فعالیت"),
    }

    return SegmentDistributionResponse(
        total_contacts=0,
        segments=[],
        calculated_at=datetime.utcnow(),
    )


@router.get("/config", response_model=RFMConfigResponse)
async def get_rfm_config() -> RFMConfigResponse:
    """
    Get current RFM configuration thresholds.
    """
    from uuid import uuid4
    return RFMConfigResponse(
        id=uuid4(),
        recency_thresholds={5: 3, 4: 7, 3: 14, 2: 30},
        frequency_thresholds={5: 10, 4: 5, 3: 3, 2: 2},
        monetary_thresholds={5: 1000000000, 4: 500000000, 3: 100000000, 2: 50000000},
        updated_at=datetime.utcnow(),
    )


@router.patch("/config", response_model=RFMConfigResponse)
async def update_rfm_config(config: RFMConfigUpdate) -> RFMConfigResponse:
    """
    Update RFM configuration thresholds.
    """
    from uuid import uuid4
    return RFMConfigResponse(
        id=uuid4(),
        recency_thresholds={5: 3, 4: 7, 3: 14, 2: 30},
        frequency_thresholds={5: 10, 4: 5, 3: 3, 2: 2},
        monetary_thresholds={5: 1000000000, 4: 500000000, 3: 100000000, 2: 50000000},
        updated_at=datetime.utcnow(),
    )


@router.get("/{segment}/contacts")
async def get_segment_contacts(
    segment: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
) -> dict[str, Any]:
    """
    Get contacts in a specific segment.
    """
    return {
        "segment": segment,
        "items": [],
        "total": 0,
        "page": page,
        "page_size": page_size,
    }


@router.get("/{segment}/recommendations", response_model=SegmentRecommendationsResponse)
async def get_segment_recommendations(segment: str) -> SegmentRecommendationsResponse:
    """
    Get recommendations for a segment (products and templates).
    """
    return SegmentRecommendationsResponse(
        segment=segment,
        recommended_action="",
        urgency="medium",
        products=[],
        templates=[],
    )


@router.get("/contact/{contact_id}/rfm", response_model=ContactRFMResponse)
async def get_contact_rfm(contact_id: UUID) -> ContactRFMResponse:
    """
    Get RFM score for a specific contact.
    """
    return ContactRFMResponse(
        contact_id=contact_id,
        phone_number="",
        recency_score=1,
        frequency_score=1,
        monetary_score=1,
        rfm_score="111",
        segment="lost",
        days_since_last_purchase=None,
        total_purchases=0,
        total_spend=0,
        calculated_at=datetime.utcnow(),
    )


@router.get("/movements", response_model=SegmentMovementResponse)
async def get_segment_movements(
    start_date: datetime | None = None,
    end_date: datetime | None = None,
) -> SegmentMovementResponse:
    """
    Get segment migration/movement report.
    """
    now = datetime.utcnow()
    return SegmentMovementResponse(
        period_start=start_date or now,
        period_end=end_date or now,
        migrations=[],
        improved_count=0,
        declined_count=0,
    )


@router.post("/recalculate")
async def trigger_rfm_recalculation() -> dict[str, Any]:
    """
    Trigger RFM recalculation for all contacts.
    """
    return {
        "status": "started",
        "message": "RFM recalculation job started",
    }

