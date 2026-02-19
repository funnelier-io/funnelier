"""
API Routes - Analytics Module
Funnel metrics and analytics endpoints
"""

from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Query
from pydantic import BaseModel

router = APIRouter()


# Response schemas
class FunnelStageCount(BaseModel):
    stage: str
    count: int
    percentage: float


class ConversionRate(BaseModel):
    from_stage: str
    to_stage: str
    rate: float


class FunnelMetricsResponse(BaseModel):
    period_start: datetime
    period_end: datetime
    total_leads: int
    total_conversions: int
    overall_conversion_rate: float
    total_revenue: int
    average_order_value: int
    average_days_to_convert: float | None
    stage_counts: list[FunnelStageCount]
    conversion_rates: list[ConversionRate]
    leads_change_percent: float | None
    conversions_change_percent: float | None
    revenue_change_percent: float | None


class DailyMetrics(BaseModel):
    date: datetime
    new_leads: int
    new_conversions: int
    revenue: int
    conversion_rate: float


class TrendResponse(BaseModel):
    period_start: datetime
    period_end: datetime
    daily_metrics: list[DailyMetrics]
    trend_direction: str  # up, down, stable
    trend_percentage: float


class BottleneckResponse(BaseModel):
    stage: str
    drop_off_rate: float
    severity: str
    recommendation: str


class CohortRow(BaseModel):
    cohort_date: datetime
    cohort_size: int
    conversions_by_day: dict[int, int]
    conversion_rates_by_day: dict[int, float]


class CohortAnalysisResponse(BaseModel):
    cohorts: list[CohortRow]
    periods: list[int]


class SalespersonPerformance(BaseModel):
    salesperson_id: UUID
    salesperson_name: str
    total_calls: int
    answered_calls: int
    average_call_duration: int
    assigned_leads: int
    contacted_leads: int
    invoices_paid: int
    total_revenue: int
    contact_rate: float
    conversion_rate: float
    rank_by_revenue: int | None
    rank_by_conversions: int | None


class TeamPerformanceResponse(BaseModel):
    period_start: datetime
    period_end: datetime
    salespersons: list[SalespersonPerformance]
    total_team_revenue: int
    total_team_conversions: int


# Endpoints
@router.get("/funnel", response_model=FunnelMetricsResponse)
async def get_funnel_metrics(
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    compare_previous: bool = True,
) -> FunnelMetricsResponse:
    """
    Get funnel metrics for a period.
    """
    now = datetime.utcnow()
    if not end_date:
        end_date = now
    if not start_date:
        start_date = end_date - timedelta(days=30)

    # Sample response
    return FunnelMetricsResponse(
        period_start=start_date,
        period_end=end_date,
        total_leads=0,
        total_conversions=0,
        overall_conversion_rate=0.0,
        total_revenue=0,
        average_order_value=0,
        average_days_to_convert=None,
        stage_counts=[],
        conversion_rates=[],
        leads_change_percent=None,
        conversions_change_percent=None,
        revenue_change_percent=None,
    )


@router.get("/funnel/trend", response_model=TrendResponse)
async def get_funnel_trend(
    days: int = Query(30, ge=7, le=90),
    metric: str = Query("conversions", enum=["leads", "conversions", "revenue"]),
) -> TrendResponse:
    """
    Get funnel trend over time.
    """
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)

    return TrendResponse(
        period_start=start_date,
        period_end=end_date,
        daily_metrics=[],
        trend_direction="stable",
        trend_percentage=0.0,
    )


@router.get("/funnel/bottlenecks", response_model=list[BottleneckResponse])
async def get_bottlenecks(
    threshold: float = Query(0.5, ge=0.0, le=1.0),
) -> list[BottleneckResponse]:
    """
    Identify funnel bottlenecks.
    """
    return []


@router.get("/cohorts", response_model=CohortAnalysisResponse)
async def get_cohort_analysis(
    weeks: int = Query(8, ge=4, le=12),
) -> CohortAnalysisResponse:
    """
    Get cohort analysis for recent weeks.
    """
    return CohortAnalysisResponse(
        cohorts=[],
        periods=[0, 7, 14, 21, 28],
    )


@router.get("/team", response_model=TeamPerformanceResponse)
async def get_team_performance(
    start_date: datetime | None = None,
    end_date: datetime | None = None,
) -> TeamPerformanceResponse:
    """
    Get sales team performance metrics.
    """
    now = datetime.utcnow()
    if not end_date:
        end_date = now
    if not start_date:
        start_date = end_date - timedelta(days=30)

    return TeamPerformanceResponse(
        period_start=start_date,
        period_end=end_date,
        salespersons=[],
        total_team_revenue=0,
        total_team_conversions=0,
    )


@router.get("/team/{salesperson_id}", response_model=SalespersonPerformance)
async def get_salesperson_performance(
    salesperson_id: UUID,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
) -> SalespersonPerformance:
    """
    Get individual salesperson performance.
    """
    return SalespersonPerformance(
        salesperson_id=salesperson_id,
        salesperson_name="",
        total_calls=0,
        answered_calls=0,
        average_call_duration=0,
        assigned_leads=0,
        contacted_leads=0,
        invoices_paid=0,
        total_revenue=0,
        contact_rate=0.0,
        conversion_rate=0.0,
        rank_by_revenue=None,
        rank_by_conversions=None,
    )


@router.get("/conversion-rates")
async def get_conversion_rates(
    group_by: str = Query("day", enum=["day", "week", "month"]),
    start_date: datetime | None = None,
    end_date: datetime | None = None,
) -> list[dict[str, Any]]:
    """
    Get historical conversion rates.
    """
    return []


@router.get("/attribution")
async def get_attribution_report(
    start_date: datetime | None = None,
    end_date: datetime | None = None,
) -> dict[str, Any]:
    """
    Get attribution report by source/category.
    """
    return {
        "by_source": [],
        "by_category": [],
        "by_campaign": [],
    }

