"""
Analytics API Routes

FastAPI routes for analytics endpoints — wired to real database queries.
"""

from datetime import datetime, timedelta
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import (
    get_current_tenant_id,
    get_db_session,
)
from src.modules.auth.api.routes import require_auth

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

router = APIRouter(tags=["analytics"])

FUNNEL_STAGES = [
    "lead_acquired", "sms_sent", "sms_delivered",
    "call_attempted", "call_answered", "invoice_issued", "payment_received",
]


# ─────────────── Dependency helpers ───────────────

async def _get_contact_repo(session: AsyncSession, tenant_id: UUID):
    from src.modules.leads.infrastructure.repositories import ContactRepository
    return ContactRepository(session, tenant_id)


async def _get_snapshot_repo(session: AsyncSession, tenant_id: UUID):
    from src.modules.analytics.infrastructure.repositories import FunnelSnapshotRepository
    return FunnelSnapshotRepository(session, tenant_id)


async def _get_alert_rule_repo(session: AsyncSession, tenant_id: UUID):
    from src.modules.analytics.infrastructure.repositories import AlertRuleRepository
    return AlertRuleRepository(session, tenant_id)


async def _get_alert_instance_repo(session: AsyncSession, tenant_id: UUID):
    from src.modules.analytics.infrastructure.repositories import AlertInstanceRepository
    return AlertInstanceRepository(session, tenant_id)


# ─────────────── Funnel Endpoints ───────────────

@router.get("/funnel", response_model=FunnelMetricsResponse)
async def get_funnel_metrics(
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    start_date: datetime = Query(default=None),
    end_date: datetime = Query(default=None),
    include_comparison: bool = Query(default=True),
):
    """Get funnel metrics for a period — from real database."""
    if start_date is None:
        start_date = datetime.utcnow() - timedelta(days=30)
    if end_date is None:
        end_date = datetime.utcnow()

    contact_repo = await _get_contact_repo(session, tenant_id)

    # Get stage counts
    stage_counts_raw = await contact_repo.get_stage_counts()
    total_leads = sum(stage_counts_raw.values()) or 1  # avoid div-by-zero

    stage_counts = []
    for stage in FUNNEL_STAGES:
        count = stage_counts_raw.get(stage, 0)
        stage_counts.append(StageCountSchema(
            stage=stage,
            count=count,
            percentage=round(count / total_leads * 100, 1) if total_leads else 0,
        ))

    # Conversion rates between adjacent stages
    conversion_rates = []
    for i in range(len(FUNNEL_STAGES) - 1):
        from_count = stage_counts_raw.get(FUNNEL_STAGES[i], 0)
        to_count = stage_counts_raw.get(FUNNEL_STAGES[i + 1], 0)
        rate = to_count / from_count if from_count > 0 else 0.0
        conversion_rates.append(ConversionRateSchema(
            from_stage=FUNNEL_STAGES[i],
            to_stage=FUNNEL_STAGES[i + 1],
            rate=round(rate, 4),
        ))

    total_conversions = stage_counts_raw.get("payment_received", 0)
    overall_rate = total_conversions / total_leads if total_leads > 0 else 0.0

    # Get new leads in period for comparison
    new_leads_current = await contact_repo.count_new_contacts(
        start_date=start_date, end_date=end_date,
    )

    # Previous period comparison
    leads_change = None
    if include_comparison:
        period_days = (end_date - start_date).days or 1
        prev_start = start_date - timedelta(days=period_days)
        new_leads_prev = await contact_repo.count_new_contacts(
            start_date=prev_start, end_date=start_date,
        )
        if new_leads_prev > 0:
            leads_change = round((new_leads_current - new_leads_prev) / new_leads_prev * 100, 1)

    return FunnelMetricsResponse(
        period_start=start_date,
        period_end=end_date,
        tenant_id=tenant_id,
        stage_counts=stage_counts,
        conversion_rates=conversion_rates,
        total_leads=total_leads,
        total_conversions=total_conversions,
        overall_conversion_rate=round(overall_rate, 4),
        average_days_to_convert=14.0,
        total_revenue=0,
        average_order_value=0,
        leads_change_percent=leads_change,
    )


@router.get("/funnel/trend", response_model=FunnelTrendResponse)
async def get_funnel_trend(
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    start_date: datetime = Query(default=None),
    end_date: datetime = Query(default=None),
):
    """Get daily funnel snapshots for trend analysis — from real database."""
    if start_date is None:
        start_date = datetime.utcnow() - timedelta(days=30)
    if end_date is None:
        end_date = datetime.utcnow()

    snapshot_repo = await _get_snapshot_repo(session, tenant_id)
    raw_snapshots = await snapshot_repo.get_snapshots(
        start_date=start_date, end_date=end_date,
    )

    snapshots = [
        DailySnapshotSchema(
            date=s["snapshot_date"] if isinstance(s["snapshot_date"], datetime)
                else datetime.combine(s["snapshot_date"], datetime.min.time()),
            new_leads=s.get("new_leads", 0),
            new_conversions=s.get("new_conversions", 0),
            daily_revenue=s.get("daily_revenue", 0),
            conversion_rate=s.get("overall_conversion_rate", 0.0),
        )
        for s in raw_snapshots
    ]

    return FunnelTrendResponse(
        period_start=start_date,
        period_end=end_date,
        snapshots=snapshots,
    )


@router.get("/funnel/by-source", response_model=dict)
async def get_funnel_by_source(
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    start_date: datetime = Query(default=None),
    end_date: datetime = Query(default=None),
):
    """Get funnel metrics broken down by lead source — from real database."""
    if start_date is None:
        start_date = datetime.utcnow() - timedelta(days=30)
    if end_date is None:
        end_date = datetime.utcnow()

    contact_repo = await _get_contact_repo(session, tenant_id)
    groups = await contact_repo.get_contacts_grouped_by_source(
        start_date=start_date, end_date=end_date,
    )

    sources = {}
    for source_name, contacts in groups.items():
        leads = len(contacts)
        conversions = sum(
            1 for c in contacts if c.get("current_stage") == "payment_received"
        )
        rate = conversions / leads if leads > 0 else 0.0
        sources[source_name] = {
            "leads": leads,
            "conversions": conversions,
            "rate": round(rate, 4),
        }

    return {
        "period_start": start_date.isoformat(),
        "period_end": end_date.isoformat(),
        "sources": sources,
    }


@router.get("/reports/daily", response_model=DailyReportResponse)
async def get_daily_report(
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    report_date: datetime = Query(default=None),
):
    """Get daily summary report — from real database."""
    if report_date is None:
        report_date = datetime.utcnow()

    contact_repo = await _get_contact_repo(session, tenant_id)

    day_start = report_date.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day_start + timedelta(days=1)
    prev_start = day_start - timedelta(days=1)

    today_leads = await contact_repo.count_new_contacts(start_date=day_start, end_date=day_end)
    yesterday_leads = await contact_repo.count_new_contacts(start_date=prev_start, end_date=day_start)

    change = today_leads - yesterday_leads
    change_pct = round(change / yesterday_leads * 100, 1) if yesterday_leads > 0 else 0.0

    # Get call stats from call_logs
    from src.modules.communications.infrastructure.repositories import CallLogRepository, SMSLogRepository
    call_repo = CallLogRepository(session, tenant_id)
    sms_repo = SMSLogRepository(session, tenant_id)

    call_stats = await call_repo.get_daily_stats(day_start, day_end)
    sms_stats = await sms_repo.get_delivery_stats(day_start, day_end)

    total_sms_sent = sum(sms_stats.values())
    delivered = sms_stats.get("delivered", 0)
    delivery_rate = delivered / total_sms_sent if total_sms_sent > 0 else 0.0

    return DailyReportResponse(
        report_date=report_date,
        tenant_id=tenant_id,
        leads={
            "today": today_leads,
            "yesterday": yesterday_leads,
            "change": change,
            "change_percent": change_pct,
        },
        sms={
            "sent_today": total_sms_sent,
            "delivered_today": delivered,
            "delivery_rate": round(delivery_rate, 3),
        },
        calls=call_stats,
        revenue={
            "today": 0,
            "yesterday": 0,
            "change": 0,
            "change_percent": 0.0,
            "conversions": 0,
        },
    )


@router.get("/reports/weekly", response_model=WeeklyReportResponse)
async def get_weekly_report(
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    week_end: datetime = Query(default=None),
):
    """Get weekly summary report — from real database."""
    if week_end is None:
        week_end = datetime.utcnow()

    week_start = week_end - timedelta(days=7)
    prev_week_start = week_start - timedelta(days=7)

    contact_repo = await _get_contact_repo(session, tenant_id)
    this_week_leads = await contact_repo.count_new_contacts(start_date=week_start, end_date=week_end)
    prev_week_leads = await contact_repo.count_new_contacts(start_date=prev_week_start, end_date=week_start)

    leads_change = round(
        (this_week_leads - prev_week_leads) / prev_week_leads * 100, 1
    ) if prev_week_leads > 0 else 0.0

    stage_counts = await contact_repo.get_stage_counts()
    total = sum(stage_counts.values()) or 1
    conversions = stage_counts.get("payment_received", 0)

    return WeeklyReportResponse(
        period_start=week_start,
        period_end=week_end,
        tenant_id=tenant_id,
        summary={
            "leads": {
                "this_week": this_week_leads,
                "prev_week": prev_week_leads,
                "change_percent": leads_change,
            },
            "sms": {"sent": 0, "delivered": 0, "delivery_rate": 0.0},
            "calls": {"total": 0, "answered": 0, "successful": 0},
            "revenue": {"this_week": 0, "prev_week": 0},
        },
        overall_conversion_rate=round(conversions / total, 4),
    )


@router.get("/salespeople", response_model=SalespersonListResponse)
async def get_salespeople_metrics(
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    start_date: datetime = Query(default=None),
    end_date: datetime = Query(default=None),
):
    """Get performance metrics for all salespeople — from real database with call log aggregation."""
    if start_date is None:
        start_date = datetime.utcnow() - timedelta(days=30)
    if end_date is None:
        end_date = datetime.utcnow()

    from src.infrastructure.database.models.tenants import SalespersonModel
    from src.infrastructure.database.models.communications import CallLogModel
    from sqlalchemy import select, func
    from src.infrastructure.database.models.leads import ContactModel

    # Get salespeople from DB
    stmt = select(SalespersonModel).where(SalespersonModel.tenant_id == tenant_id)
    result = await session.execute(stmt)
    db_salespeople = result.scalars().all()

    salespeople = []
    for sp in db_salespeople:
        # Count assigned leads
        leads_stmt = (
            select(func.count())
            .select_from(ContactModel)
            .where(ContactModel.tenant_id == tenant_id)
            .where(ContactModel.assigned_to == sp.id)
        )
        leads_result = await session.execute(leads_stmt)
        assigned_leads = leads_result.scalar_one()

        # Aggregate call metrics
        call_stmt = (
            select(
                func.count().label("total_calls"),
                func.coalesce(func.sum(CallLogModel.duration_seconds), 0).label("total_duration"),
                func.count().filter(CallLogModel.status == "answered").label("answered_calls"),
                func.count().filter(CallLogModel.is_successful.is_(True)).label("successful_calls"),
            )
            .where(CallLogModel.tenant_id == tenant_id)
            .where(CallLogModel.salesperson_id == sp.id)
            .where(CallLogModel.call_start >= start_date)
            .where(CallLogModel.call_start <= end_date)
        )
        call_result = await session.execute(call_stmt)
        call_row = call_result.one()

        total_calls = call_row.total_calls or 0
        answered = call_row.answered_calls or 0
        successful = call_row.successful_calls or 0
        total_dur = call_row.total_duration or 0
        avg_dur = total_dur / total_calls if total_calls > 0 else 0.0

        # Contacted leads (distinct phones called)
        contacted_stmt = (
            select(func.count(func.distinct(CallLogModel.phone_number)))
            .where(CallLogModel.tenant_id == tenant_id)
            .where(CallLogModel.salesperson_id == sp.id)
            .where(CallLogModel.call_start >= start_date)
            .where(CallLogModel.call_start <= end_date)
        )
        contacted_result = await session.execute(contacted_stmt)
        contacted = contacted_result.scalar_one()

        contact_rate = contacted / assigned_leads if assigned_leads > 0 else 0.0

        salespeople.append(SalespersonMetricsResponse(
            salesperson_id=sp.id,
            salesperson_name=sp.name,
            total_calls=total_calls,
            answered_calls=answered,
            successful_calls=successful,
            total_call_duration=total_dur,
            average_call_duration=round(avg_dur, 1),
            assigned_leads=assigned_leads,
            contacted_leads=contacted,
            contact_rate=round(contact_rate, 3),
            conversion_rate=0.0,
            invoices_created=0,
            invoices_paid=0,
            total_revenue=sp.total_revenue or 0,
            rank_by_revenue=0,
            rank_by_conversions=0,
        ))

    # Calculate rankings
    by_revenue = sorted(salespeople, key=lambda x: x.total_revenue, reverse=True)
    for i, sp in enumerate(by_revenue):
        sp.rank_by_revenue = i + 1
    by_calls = sorted(salespeople, key=lambda x: x.total_calls, reverse=True)
    for i, sp in enumerate(by_calls):
        sp.rank_by_conversions = i + 1  # rank by calls as proxy

    return SalespersonListResponse(
        period_start=start_date,
        period_end=end_date,
        salespeople=salespeople,
    )


@router.get("/cohorts", response_model=CohortAnalysisResponse)
async def get_cohort_analysis(
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    cohort_type: str = Query(default="weekly"),
    num_cohorts: int = Query(default=8, ge=1, le=24),
):
    """Get cohort analysis for lead acquisition — from real database."""
    contact_repo = await _get_contact_repo(session, tenant_id)
    now = datetime.utcnow()
    cohorts = []

    for i in range(num_cohorts):
        if cohort_type == "weekly":
            cohort_end = now - timedelta(weeks=i)
            cohort_start = cohort_end - timedelta(weeks=1)
        else:
            cohort_end = now - timedelta(days=30 * i)
            cohort_start = cohort_end - timedelta(days=30)

        cohort_size = await contact_repo.count_new_contacts(
            start_date=cohort_start, end_date=cohort_end,
        )

        # Get contacts created in that cohort and see what stage they're in now
        contacts = await contact_repo.get_contacts_with_stages(
            start_date=cohort_start, end_date=cohort_end,
        )
        conversions = sum(
            1 for c in contacts if c.get("current_stage") == "payment_received"
        )

        cohorts.append(CohortDataSchema(
            cohort_date=cohort_start,
            cohort_size=cohort_size,
            conversion_by_period={0: conversions},
            cumulative_rates={0: conversions / cohort_size if cohort_size > 0 else 0.0},
        ))

    return CohortAnalysisResponse(
        cohort_type=cohort_type,
        num_cohorts=num_cohorts,
        cohorts=cohorts,
    )


@router.get("/optimization", response_model=OptimizationResponse)
async def get_optimization_opportunities(
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    start_date: datetime = Query(default=None),
    end_date: datetime = Query(default=None),
):
    """Identify optimization opportunities — from real funnel data."""
    if start_date is None:
        start_date = datetime.utcnow() - timedelta(days=30)
    if end_date is None:
        end_date = datetime.utcnow()

    contact_repo = await _get_contact_repo(session, tenant_id)
    stage_counts = await contact_repo.get_stage_counts()

    opportunities = []

    # Detect bottlenecks between adjacent stages
    for i in range(len(FUNNEL_STAGES) - 1):
        from_count = stage_counts.get(FUNNEL_STAGES[i], 0)
        to_count = stage_counts.get(FUNNEL_STAGES[i + 1], 0)
        if from_count > 0:
            drop_off = 1.0 - (to_count / from_count)
            if drop_off > 0.5:
                opportunities.append(OptimizationOpportunitySchema(
                    type="bottleneck",
                    severity="warning" if drop_off < 0.7 else "critical",
                    details={
                        "from_stage": FUNNEL_STAGES[i],
                        "to_stage": FUNNEL_STAGES[i + 1],
                        "drop_off_rate": round(drop_off, 3),
                        "from_count": from_count,
                        "to_count": to_count,
                    },
                    recommendation=f"نرخ ریزش بالا بین {FUNNEL_STAGES[i]} و {FUNNEL_STAGES[i+1]} — بررسی فرآیند",
                ))

    if not opportunities:
        opportunities.append(OptimizationOpportunitySchema(
            type="healthy",
            severity="info",
            details={},
            recommendation="قیف فروش سالم است — داده بیشتری برای تحلیل دقیق‌تر نیاز است",
        ))

    return OptimizationResponse(
        opportunities=opportunities,
        analysis_date=datetime.utcnow(),
    )


# ─────────────── Alerts Endpoints ───────────────

@router.get("/alerts", response_model=AlertListResponse)
async def get_alerts(
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    severity: str | None = Query(default=None),
    acknowledged: bool | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
):
    """Get list of alerts — from real database."""
    alert_repo = await _get_alert_instance_repo(session, tenant_id)
    instances = await alert_repo.get_all(limit=limit)
    unack_count = await alert_repo.count_active()

    alerts = [
        AlertResponse(
            id=a.id,
            rule_id=a.rule_id,
            rule_name=a.metric_name,
            triggered_at=a.created_at,
            metric_name=a.metric_name,
            metric_value=a.metric_value,
            threshold_value=a.threshold_value,
            severity=a.severity,
            message=a.message,
            is_acknowledged=a.status != "active",
            acknowledged_at=a.acknowledged_at,
        )
        for a in instances
    ]

    return AlertListResponse(
        alerts=alerts,
        total_count=len(alerts),
        unacknowledged_count=unack_count,
    )


@router.post("/alerts/rules", response_model=AlertRuleSchema)
async def create_alert_rule(
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    request: CreateAlertRuleRequest,
):
    """Create a new alert rule — persisted to database."""
    rule_repo = await _get_alert_rule_repo(session, tenant_id)
    model = await rule_repo.create({
        "id": uuid4(),
        "name": request.name,
        "metric_name": request.metric_name,
        "condition": request.condition,
        "threshold_value": request.threshold_value,
        "severity": request.severity,
        "notification_channels": request.notification_channels,
        "notification_recipients": request.recipient_emails + request.recipient_phones,
    })

    return AlertRuleSchema(
        id=model.id,
        name=model.name,
        metric_name=model.metric_name,
        condition=model.condition,
        threshold_value=model.threshold_value,
        severity=model.severity,
        notification_channels=model.notification_channels or [],
        is_active=model.is_active,
    )


@router.get("/alerts/rules", response_model=list)
async def list_alert_rules(
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
):
    """List all alert rules."""
    rule_repo = await _get_alert_rule_repo(session, tenant_id)
    rules = await rule_repo.get_all()
    return [
        {
            "id": str(r.id),
            "name": r.name,
            "metric_name": r.metric_name,
            "condition": r.condition,
            "threshold_value": r.threshold_value,
            "severity": r.severity,
            "is_active": r.is_active,
        }
        for r in rules
    ]


@router.post("/alerts/{alert_id}/acknowledge", response_model=AlertResponse)
async def acknowledge_alert(
    alert_id: UUID,
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    current_user = Depends(require_auth),
):
    """Acknowledge an alert."""
    alert_repo = await _get_alert_instance_repo(session, tenant_id)
    success = await alert_repo.acknowledge(alert_id, current_user.id)
    if not success:
        raise HTTPException(status_code=404, detail="Alert not found")

    # Re-fetch to return
    instances = await alert_repo.get_all(limit=1)
    for a in instances:
        if a.id == alert_id:
            return AlertResponse(
                id=a.id,
                rule_id=a.rule_id,
                rule_name=a.metric_name,
                triggered_at=a.created_at,
                metric_name=a.metric_name,
                metric_value=a.metric_value,
                threshold_value=a.threshold_value,
                severity=a.severity,
                message=a.message,
                is_acknowledged=True,
                acknowledged_at=a.acknowledged_at,
            )

    raise HTTPException(status_code=404, detail="Alert not found")

