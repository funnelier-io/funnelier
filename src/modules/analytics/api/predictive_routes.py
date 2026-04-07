"""
Predictive Analytics API Routes

Endpoints for churn prediction, lead scoring, campaign ROI, A/B tests, retention.
"""

from datetime import datetime, timedelta
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_current_tenant_id, get_db_session
from src.modules.analytics.application.predictive_service import (
    ABTestResult,
    CampaignROI,
    ChurnSummary,
    LeadScoringResult,
    PredictiveAnalyticsService,
    RetentionAnalysis,
)

router = APIRouter(prefix="/predictive", tags=["predictive-analytics"])

_svc = PredictiveAnalyticsService()


# ── Request schemas ──────────────────────────────────

class ABTestRequest(BaseModel):
    test_name: str = "آزمایش A/B"
    variant_a_name: str = "کنترل (A)"
    variant_b_name: str = "آزمایشی (B)"
    variant_a_conversions: int
    variant_a_total: int
    variant_b_conversions: int
    variant_b_total: int
    confidence_threshold: float = 0.95


class CampaignROIRequest(BaseModel):
    campaign_name: str
    campaign_id: UUID | None = None
    total_cost: float
    leads_generated: int
    conversions: int
    total_revenue: float
    average_product_margin: float = 0.3


# ── Helper: load contact data for churn / scoring ────

async def _load_contacts_for_analysis(
    session: AsyncSession, tenant_id: UUID,
    limit: int = 5000,
) -> list[dict[str, Any]]:
    """Load contacts with engagement data for predictive analysis."""
    from src.infrastructure.database.models.leads import ContactModel

    stmt = (
        select(ContactModel)
        .where(ContactModel.tenant_id == tenant_id)
        .order_by(ContactModel.created_at.desc())
        .limit(limit)
    )
    result = await session.execute(stmt)
    rows = result.scalars().all()

    now = datetime.utcnow()
    contacts = []
    for r in rows:
        # days since last activity (use updated_at or created_at)
        last = r.updated_at or r.created_at or now
        # Strip timezone info for safe subtraction
        last_naive = last.replace(tzinfo=None) if hasattr(last, 'tzinfo') and last.tzinfo else last
        days_since = (now - last_naive).days if last_naive else 999

        contacts.append({
            "id": r.id,
            "phone_number": r.phone_number,
            "name": r.name,
            "category_name": r.category_name,
            "current_stage": r.current_stage or "lead_acquired",
            "rfm_segment": r.rfm_segment,
            "total_calls": r.total_calls or 0,
            "answered_calls": r.total_answered_calls or 0,
            "total_sms_received": r.total_sms_delivered or 0,
            "purchase_count": r.total_paid_invoices or 0,
            "total_spend": r.total_revenue or 0,
            "days_since_last_activity": days_since,
            "days_since_created": (now - (r.created_at.replace(tzinfo=None) if hasattr(r.created_at, 'tzinfo') and r.created_at.tzinfo else r.created_at)).days if r.created_at else 999,
            "last_activity_date": last_naive,
        })

    return contacts


# ── Endpoints ────────────────────────────────────────

@router.get("/churn", response_model=ChurnSummary)
async def predict_churn(
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    limit: int = Query(default=5000, ge=100, le=50000),
):
    """Predict churn risk for all contacts."""
    contacts = await _load_contacts_for_analysis(session, tenant_id, limit)
    return _svc.predict_churn(contacts)


@router.get("/lead-scores", response_model=LeadScoringResult)
async def score_leads(
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    limit: int = Query(default=5000, ge=100, le=50000),
):
    """Score all leads by conversion likelihood."""
    contacts = await _load_contacts_for_analysis(session, tenant_id, limit)
    return _svc.score_leads(contacts)


@router.post("/ab-test", response_model=ABTestResult)
async def ab_test_significance(
    request: ABTestRequest,
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
):
    """Calculate A/B test statistical significance."""
    return _svc.ab_test_significance(
        test_name=request.test_name,
        variant_a_conversions=request.variant_a_conversions,
        variant_a_total=request.variant_a_total,
        variant_b_conversions=request.variant_b_conversions,
        variant_b_total=request.variant_b_total,
        confidence_threshold=request.confidence_threshold,
        variant_a_name=request.variant_a_name,
        variant_b_name=request.variant_b_name,
    )


@router.post("/campaign-roi", response_model=CampaignROI)
async def calculate_campaign_roi(
    request: CampaignROIRequest,
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
):
    """Calculate campaign ROI metrics."""
    return _svc.calculate_campaign_roi(
        campaign_name=request.campaign_name,
        campaign_id=request.campaign_id,
        total_cost=request.total_cost,
        leads_generated=request.leads_generated,
        conversions=request.conversions,
        total_revenue=request.total_revenue,
        average_product_margin=request.average_product_margin,
    )


@router.get("/retention", response_model=RetentionAnalysis)
async def get_retention_curves(
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    period_type: str = Query(default="weekly", pattern="^(weekly|monthly)$"),
    num_cohorts: int = Query(default=8, ge=2, le=24),
    num_periods: int = Query(default=8, ge=2, le=24),
):
    """Get retention curves by cohort."""
    from src.infrastructure.database.models.leads import ContactModel

    now = datetime.utcnow()
    period_days = 7 if period_type == "weekly" else 30
    cohorts_data = []

    for i in range(num_cohorts):
        cohort_end = now - timedelta(days=period_days * i)
        cohort_start = cohort_end - timedelta(days=period_days)

        stmt = (
            select(ContactModel)
            .where(ContactModel.tenant_id == tenant_id)
            .where(ContactModel.created_at >= cohort_start)
            .where(ContactModel.created_at < cohort_end)
        )
        result = await session.execute(stmt)
        rows = result.scalars().all()

        contacts = [
            {
                "created_at": r.created_at,
                "last_activity_date": r.updated_at or r.created_at,
                "is_active": True,
            }
            for r in rows
        ]

        label = cohort_start.strftime("%Y-%m-%d")
        cohorts_data.append({
            "cohort_label": label,
            "cohort_start": cohort_start,
            "contacts": contacts,
        })

    return _svc.calculate_retention(cohorts_data, period_type, num_periods)


