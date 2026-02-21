"""
Analytics API Routes

FastAPI routes for analytics endpoints.
"""

from datetime import datetime, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from .schemas import (
    AlertListResponse,
    AlertResponse,
    AlertRuleSchema,
    CohortAnalysisResponse,
    CohortDataSchema,
    ConversionRateSchema,
    CreateAlertRuleRequest,
    DailyReportResponse,
    DailySnapshotSchema,
    FunnelMetricsResponse,
    FunnelTrendResponse,
    OptimizationOpportunitySchema,
    OptimizationResponse,
    SalespersonListResponse,
    SalespersonMetricsResponse,
    StageCountSchema,
    WeeklyReportResponse,
)

router = APIRouter(prefix="/analytics", tags=["analytics"])


# Dependency for getting current tenant (placeholder)
async def get_current_tenant() -> UUID:
    """Get current tenant from auth context."""
    # This would be replaced with actual auth logic
    return UUID("00000000-0000-0000-0000-000000000001")


# Dependency for getting current user (placeholder)
async def get_current_user() -> UUID:
    """Get current user from auth context."""
    return UUID("00000000-0000-0000-0000-000000000002")


@router.get("/funnel", response_model=FunnelMetricsResponse)
async def get_funnel_metrics(
    tenant_id: Annotated[UUID, Depends(get_current_tenant)],
    start_date: datetime = Query(default=None),
    end_date: datetime = Query(default=None),
    include_comparison: bool = Query(default=True),
):
    """
    Get funnel metrics for a period.

    Returns stage counts, conversion rates, and comparison to previous period.
    """
    if start_date is None:
        start_date = datetime.utcnow() - timedelta(days=30)
    if end_date is None:
        end_date = datetime.utcnow()

    # TODO: Inject service via dependency injection
    # metrics = await funnel_service.get_funnel_metrics(...)

    # Placeholder response
    return FunnelMetricsResponse(
        period_start=start_date,
        period_end=end_date,
        tenant_id=tenant_id,
        stage_counts=[
            StageCountSchema(stage="lead_acquired", count=1000, percentage=100.0),
            StageCountSchema(stage="sms_sent", count=800, percentage=80.0),
            StageCountSchema(stage="sms_delivered", count=750, percentage=75.0),
            StageCountSchema(stage="call_attempted", count=500, percentage=50.0),
            StageCountSchema(stage="call_answered", count=200, percentage=20.0),
            StageCountSchema(stage="invoice_issued", count=100, percentage=10.0),
            StageCountSchema(stage="payment_received", count=50, percentage=5.0),
        ],
        conversion_rates=[
            ConversionRateSchema(from_stage="lead_acquired", to_stage="sms_sent", rate=0.80),
            ConversionRateSchema(from_stage="sms_sent", to_stage="sms_delivered", rate=0.94),
            ConversionRateSchema(from_stage="sms_delivered", to_stage="call_attempted", rate=0.67),
            ConversionRateSchema(from_stage="call_attempted", to_stage="call_answered", rate=0.40),
            ConversionRateSchema(from_stage="call_answered", to_stage="invoice_issued", rate=0.50),
            ConversionRateSchema(from_stage="invoice_issued", to_stage="payment_received", rate=0.50),
        ],
        total_leads=1000,
        total_conversions=50,
        overall_conversion_rate=0.05,
        average_days_to_convert=14.5,
        total_revenue=500_000_000,
        average_order_value=10_000_000,
        leads_change_percent=5.2,
        conversions_change_percent=-2.1,
        revenue_change_percent=3.5,
    )


@router.get("/funnel/trend", response_model=FunnelTrendResponse)
async def get_funnel_trend(
    tenant_id: Annotated[UUID, Depends(get_current_tenant)],
    start_date: datetime = Query(default=None),
    end_date: datetime = Query(default=None),
):
    """
    Get daily funnel snapshots for trend analysis.
    """
    if start_date is None:
        start_date = datetime.utcnow() - timedelta(days=30)
    if end_date is None:
        end_date = datetime.utcnow()

    # Generate sample data
    snapshots = []
    current = start_date
    while current <= end_date:
        snapshots.append(
            DailySnapshotSchema(
                date=current,
                new_leads=30 + (current.day % 10),
                new_conversions=2 + (current.day % 3),
                daily_revenue=20_000_000 + (current.day * 1_000_000),
                conversion_rate=0.05 + (current.day % 5) * 0.01,
            )
        )
        current += timedelta(days=1)

    return FunnelTrendResponse(
        period_start=start_date,
        period_end=end_date,
        snapshots=snapshots,
    )


@router.get("/funnel/by-source")
async def get_funnel_by_source(
    tenant_id: Annotated[UUID, Depends(get_current_tenant)],
    start_date: datetime = Query(default=None),
    end_date: datetime = Query(default=None),
):
    """
    Get funnel metrics broken down by lead source.
    """
    if start_date is None:
        start_date = datetime.utcnow() - timedelta(days=30)
    if end_date is None:
        end_date = datetime.utcnow()

    # Placeholder response
    return {
        "period_start": start_date.isoformat(),
        "period_end": end_date.isoformat(),
        "sources": {
            "نمایشگاه": {"leads": 200, "conversions": 15, "rate": 0.075},
            "سیمان": {"leads": 300, "conversions": 20, "rate": 0.067},
            "پیمانکاران": {"leads": 150, "conversions": 8, "rate": 0.053},
        },
    }


@router.get("/reports/daily", response_model=DailyReportResponse)
async def get_daily_report(
    tenant_id: Annotated[UUID, Depends(get_current_tenant)],
    report_date: datetime = Query(default=None),
):
    """
    Get daily summary report.
    """
    if report_date is None:
        report_date = datetime.utcnow()

    return DailyReportResponse(
        report_date=report_date,
        tenant_id=tenant_id,
        leads={
            "today": 35,
            "yesterday": 32,
            "change": 3,
            "change_percent": 9.4,
        },
        sms={
            "sent_today": 120,
            "delivered_today": 110,
            "delivery_rate": 0.917,
        },
        calls={
            "total_today": 85,
            "answered_today": 30,
            "successful_today": 15,
            "answer_rate": 0.35,
            "success_rate": 0.18,
        },
        revenue={
            "today": 25_000_000,
            "yesterday": 20_000_000,
            "change": 5_000_000,
            "change_percent": 25.0,
            "conversions": 3,
        },
    )


@router.get("/reports/weekly", response_model=WeeklyReportResponse)
async def get_weekly_report(
    tenant_id: Annotated[UUID, Depends(get_current_tenant)],
    week_end: datetime = Query(default=None),
):
    """
    Get weekly summary report.
    """
    if week_end is None:
        week_end = datetime.utcnow()

    week_start = week_end - timedelta(days=7)

    return WeeklyReportResponse(
        period_start=week_start,
        period_end=week_end,
        tenant_id=tenant_id,
        summary={
            "leads": {"this_week": 245, "prev_week": 220, "change_percent": 11.4},
            "sms": {"sent": 840, "delivered": 780, "delivery_rate": 0.93},
            "calls": {"total": 595, "answered": 210, "successful": 105},
            "revenue": {"this_week": 175_000_000, "prev_week": 150_000_000},
        },
        overall_conversion_rate=0.043,
    )


@router.get("/salespeople", response_model=SalespersonListResponse)
async def get_salespeople_metrics(
    tenant_id: Annotated[UUID, Depends(get_current_tenant)],
    start_date: datetime = Query(default=None),
    end_date: datetime = Query(default=None),
):
    """
    Get performance metrics for all salespeople.
    """
    if start_date is None:
        start_date = datetime.utcnow() - timedelta(days=30)
    if end_date is None:
        end_date = datetime.utcnow()

    # Sample data for 9 salespeople
    salespeople = [
        SalespersonMetricsResponse(
            salesperson_id=UUID(f"00000000-0000-0000-0000-00000000000{i}"),
            salesperson_name=name,
            total_calls=100 + i * 10,
            answered_calls=35 + i * 3,
            successful_calls=15 + i * 2,
            total_call_duration=3600 * (i + 1),
            average_call_duration=120 + i * 10,
            assigned_leads=150 + i * 20,
            contacted_leads=80 + i * 5,
            contact_rate=0.5 + i * 0.02,
            conversion_rate=0.1 + i * 0.01,
            invoices_created=20 + i * 2,
            invoices_paid=10 + i,
            total_revenue=100_000_000 + i * 20_000_000,
            rank_by_revenue=9 - i,
            rank_by_conversions=9 - i,
        )
        for i, name in enumerate(
            ["اسدالهی", "بردبار", "رضایی", "کاشی", "نخست", "فدایی", "شفیعی", "حیدری", "آتشین"]
        )
    ]

    return SalespersonListResponse(
        period_start=start_date,
        period_end=end_date,
        salespeople=salespeople,
    )


@router.get("/cohorts", response_model=CohortAnalysisResponse)
async def get_cohort_analysis(
    tenant_id: Annotated[UUID, Depends(get_current_tenant)],
    cohort_type: str = Query(default="weekly"),  # weekly, monthly
    num_cohorts: int = Query(default=8, ge=1, le=24),
):
    """
    Get cohort analysis for lead acquisition.
    """
    now = datetime.utcnow()
    cohorts = []

    for i in range(num_cohorts):
        if cohort_type == "weekly":
            cohort_date = now - timedelta(weeks=i + 1)
        else:
            cohort_date = now - timedelta(days=30 * (i + 1))

        cohorts.append(
            CohortDataSchema(
                cohort_date=cohort_date,
                cohort_size=100 + i * 10,
                conversion_by_period={0: 5, 7: 8, 14: 10, 21: 12},
                cumulative_rates={0: 0.05, 7: 0.13, 14: 0.23, 21: 0.35},
            )
        )

    return CohortAnalysisResponse(
        cohort_type=cohort_type,
        num_cohorts=num_cohorts,
        cohorts=cohorts,
    )


@router.get("/optimization", response_model=OptimizationResponse)
async def get_optimization_opportunities(
    tenant_id: Annotated[UUID, Depends(get_current_tenant)],
    start_date: datetime = Query(default=None),
    end_date: datetime = Query(default=None),
):
    """
    Identify optimization opportunities in the funnel.
    """
    if start_date is None:
        start_date = datetime.utcnow() - timedelta(days=30)
    if end_date is None:
        end_date = datetime.utcnow()

    opportunities = [
        OptimizationOpportunitySchema(
            type="bottleneck",
            severity="warning",
            details={"stage": "call_answered", "drop_off_rate": 0.60},
            recommendation="نرخ پاسخگویی پایین - بررسی زمان‌بندی تماس‌ها",
        ),
        OptimizationOpportunitySchema(
            type="sms_delivery",
            severity="info",
            details={"delivery_rate": 0.92},
            recommendation="نرخ تحویل خوب است اما می‌توان بهبود داد",
        ),
    ]

    return OptimizationResponse(
        opportunities=opportunities,
        analysis_date=datetime.utcnow(),
    )


@router.get("/alerts", response_model=AlertListResponse)
async def get_alerts(
    tenant_id: Annotated[UUID, Depends(get_current_tenant)],
    severity: str | None = Query(default=None),
    acknowledged: bool | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
):
    """
    Get list of alerts.
    """
    # Placeholder response
    return AlertListResponse(
        alerts=[],
        total_count=0,
        unacknowledged_count=0,
    )


@router.post("/alerts/rules", response_model=AlertRuleSchema)
async def create_alert_rule(
    tenant_id: Annotated[UUID, Depends(get_current_tenant)],
    request: CreateAlertRuleRequest,
):
    """
    Create a new alert rule.
    """
    return AlertRuleSchema(
        id=UUID("00000000-0000-0000-0000-000000000001"),
        name=request.name,
        metric_name=request.metric_name,
        condition=request.condition,
        threshold_value=request.threshold_value,
        severity=request.severity,
        notification_channels=request.notification_channels,
        recipient_emails=request.recipient_emails,
        recipient_phones=request.recipient_phones,
        webhook_url=request.webhook_url,
        is_active=True,
    )


@router.post("/alerts/{alert_id}/acknowledge", response_model=AlertResponse)
async def acknowledge_alert(
    alert_id: UUID,
    tenant_id: Annotated[UUID, Depends(get_current_tenant)],
    user_id: Annotated[UUID, Depends(get_current_user)],
):
    """
    Acknowledge an alert.
    """
    raise HTTPException(status_code=404, detail="Alert not found")

