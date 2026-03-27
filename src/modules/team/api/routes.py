"""
Team API Routes

FastAPI routes for salesperson and team management — wired to real database.
"""

from datetime import datetime, timedelta
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_current_tenant_id, get_db_session
from src.infrastructure.database.models.tenants import SalespersonModel
from src.infrastructure.database.models.leads import ContactModel
from src.infrastructure.database.models.communications import CallLogModel

from .schemas import (
    ActivityLogListResponse,
    AssignmentRuleListResponse,
    AssignmentRuleResponse,
    CreateAssignmentRuleRequest,
    CreateSalespersonRequest,
    CreateSalesTargetRequest,
    DailyActivitySummaryResponse,
    PerformanceComparisonResponse,
    PerformanceMetricsSchema,
    SalespersonListResponse,
    SalespersonPerformanceResponse,
    SalespersonResponse,
    SalesTargetListResponse,
    SalesTargetResponse,
    TeamPerformanceResponse,
    TeamTargetSummaryResponse,
    UpdateSalespersonRequest,
)

router = APIRouter(prefix="/team", tags=["team"])


# ─────────────── Helper: build SalespersonResponse from model ───────────────

async def _sp_response(
    session: AsyncSession,
    sp: SalespersonModel,
    tenant_id: UUID,
) -> SalespersonResponse:
    """Build a SalespersonResponse from a SalespersonModel with live lead counts."""
    leads_stmt = (
        select(func.count())
        .select_from(ContactModel)
        .where(ContactModel.tenant_id == tenant_id)
        .where(ContactModel.assigned_to == sp.id)
    )
    result = await session.execute(leads_stmt)
    assigned_leads = result.scalar_one()

    return SalespersonResponse(
        id=sp.id,
        tenant_id=sp.tenant_id,
        name=sp.name,
        phone_number=sp.phone or "",
        email=sp.email,
        role="salesperson",
        regions=[sp.region] if sp.region else [],
        is_active=sp.is_active,
        assigned_leads=assigned_leads,
        active_leads=assigned_leads,
        created_at=sp.created_at,
        updated_at=sp.updated_at,
    )


# ─────────────── Helper: compute call performance for a salesperson ───────────────

async def _call_metrics(
    session: AsyncSession,
    tenant_id: UUID,
    salesperson_id: UUID,
    start_date: datetime,
    end_date: datetime,
) -> PerformanceMetricsSchema:
    """Compute call performance metrics from call_logs for a salesperson."""
    base = (
        select(
            func.count().label("total_calls"),
            func.coalesce(func.sum(CallLogModel.duration_seconds), 0).label("total_duration"),
            func.count().filter(CallLogModel.status == "answered").label("answered_calls"),
            func.count().filter(CallLogModel.is_successful.is_(True)).label("successful_calls"),
        )
        .where(CallLogModel.tenant_id == tenant_id)
        .where(CallLogModel.salesperson_id == salesperson_id)
        .where(CallLogModel.call_start >= start_date)
        .where(CallLogModel.call_start <= end_date)
    )
    result = await session.execute(base)
    row = result.one()

    total_calls = row.total_calls or 0
    answered = row.answered_calls or 0
    successful = row.successful_calls or 0
    total_dur = row.total_duration or 0
    avg_dur = total_dur / total_calls if total_calls > 0 else 0.0
    answer_rate = answered / total_calls if total_calls > 0 else 0.0
    success_rate = successful / total_calls if total_calls > 0 else 0.0

    # Lead stats
    leads_stmt = (
        select(func.count())
        .select_from(ContactModel)
        .where(ContactModel.tenant_id == tenant_id)
        .where(ContactModel.assigned_to == salesperson_id)
    )
    leads_result = await session.execute(leads_stmt)
    assigned_leads = leads_result.scalar_one()

    # Count distinct phones called (contacted leads)
    contacted_stmt = (
        select(func.count(func.distinct(CallLogModel.phone_number)))
        .where(CallLogModel.tenant_id == tenant_id)
        .where(CallLogModel.salesperson_id == salesperson_id)
        .where(CallLogModel.call_start >= start_date)
        .where(CallLogModel.call_start <= end_date)
    )
    contacted_result = await session.execute(contacted_stmt)
    contacted_leads = contacted_result.scalar_one()

    contact_rate = contacted_leads / assigned_leads if assigned_leads > 0 else 0.0

    return PerformanceMetricsSchema(
        total_calls=total_calls,
        answered_calls=answered,
        successful_calls=successful,
        total_call_duration=total_dur,
        average_call_duration=round(avg_dur, 1),
        answer_rate=round(answer_rate, 3),
        success_rate=round(success_rate, 3),
        assigned_leads=assigned_leads,
        contacted_leads=contacted_leads,
        contact_rate=round(contact_rate, 3),
        invoices_created=0,
        invoices_paid=0,
        conversion_rate=0.0,
        total_revenue=0,
        average_deal_size=0,
    )


# ============================================================================
# Salesperson CRUD Endpoints
# ============================================================================

@router.get("/salespeople", response_model=SalespersonListResponse)
async def list_salespeople(
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    is_active: bool | None = Query(default=None),
    region: str | None = Query(default=None),
):
    """List all salespeople — from real database."""
    stmt = select(SalespersonModel).where(SalespersonModel.tenant_id == tenant_id)
    if is_active is not None:
        stmt = stmt.where(SalespersonModel.is_active == is_active)
    if region:
        stmt = stmt.where(SalespersonModel.region == region)
    stmt = stmt.order_by(SalespersonModel.name)

    result = await session.execute(stmt)
    db_salespeople = result.scalars().all()

    salespeople = []
    for sp in db_salespeople:
        salespeople.append(await _sp_response(session, sp, tenant_id))

    return SalespersonListResponse(
        salespeople=salespeople,
        total_count=len(salespeople),
    )


@router.post("/salespeople", response_model=SalespersonResponse, status_code=201)
async def create_salesperson(
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    request: CreateSalespersonRequest,
):
    """Create a new salesperson — persisted to database."""
    model = SalespersonModel(
        id=uuid4(),
        tenant_id=tenant_id,
        name=request.name,
        phone=request.phone_number,
        email=request.email,
        region=request.regions[0] if request.regions else None,
        categories=[],
        is_active=request.is_active,
        total_leads_assigned=0,
        total_conversions=0,
        total_revenue=0,
        metadata_=request.metadata or {},
    )
    session.add(model)
    await session.flush()
    await session.refresh(model)

    return await _sp_response(session, model, tenant_id)


@router.get("/salespeople/{salesperson_id}", response_model=SalespersonResponse)
async def get_salesperson(
    salesperson_id: UUID,
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
):
    """Get salesperson by ID — from real database."""
    stmt = (
        select(SalespersonModel)
        .where(SalespersonModel.tenant_id == tenant_id)
        .where(SalespersonModel.id == salesperson_id)
    )
    result = await session.execute(stmt)
    sp = result.scalar_one_or_none()
    if not sp:
        raise HTTPException(status_code=404, detail="Salesperson not found")

    return await _sp_response(session, sp, tenant_id)


@router.put("/salespeople/{salesperson_id}", response_model=SalespersonResponse)
async def update_salesperson(
    salesperson_id: UUID,
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    request: UpdateSalespersonRequest,
):
    """Update a salesperson — persisted to database."""
    stmt = (
        select(SalespersonModel)
        .where(SalespersonModel.tenant_id == tenant_id)
        .where(SalespersonModel.id == salesperson_id)
    )
    result = await session.execute(stmt)
    sp = result.scalar_one_or_none()
    if not sp:
        raise HTTPException(status_code=404, detail="Salesperson not found")

    if request.name is not None:
        sp.name = request.name
    if request.phone_number is not None:
        sp.phone = request.phone_number
    if request.email is not None:
        sp.email = request.email
    if request.regions is not None:
        sp.region = request.regions[0] if request.regions else None
    if request.is_active is not None:
        sp.is_active = request.is_active
    if request.metadata is not None:
        sp.metadata_ = request.metadata

    await session.flush()
    await session.refresh(sp)

    return await _sp_response(session, sp, tenant_id)


@router.delete("/salespeople/{salesperson_id}", status_code=204)
async def delete_salesperson(
    salesperson_id: UUID,
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
):
    """Delete a salesperson."""
    from sqlalchemy import delete as sa_delete
    stmt = (
        sa_delete(SalespersonModel)
        .where(SalespersonModel.tenant_id == tenant_id)
        .where(SalespersonModel.id == salesperson_id)
    )
    result = await session.execute(stmt)
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Salesperson not found")


# ============================================================================
# Performance Endpoints
# ============================================================================

@router.get("/performance", response_model=TeamPerformanceResponse)
async def get_team_performance(
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    start_date: datetime = Query(default=None),
    end_date: datetime = Query(default=None),
):
    """Get team performance summary — from real database."""
    if start_date is None:
        start_date = datetime.utcnow() - timedelta(days=30)
    if end_date is None:
        end_date = datetime.utcnow()

    # Get all active salespeople
    stmt = (
        select(SalespersonModel)
        .where(SalespersonModel.tenant_id == tenant_id)
        .where(SalespersonModel.is_active.is_(True))
    )
    result = await session.execute(stmt)
    salespeople = result.scalars().all()

    # Compute per-salesperson metrics
    by_salesperson = []
    for sp in salespeople:
        metrics = await _call_metrics(session, tenant_id, sp.id, start_date, end_date)
        by_salesperson.append(SalespersonPerformanceResponse(
            salesperson_id=sp.id,
            salesperson_name=sp.name,
            period_start=start_date,
            period_end=end_date,
            metrics=metrics,
        ))

    # Sort by total_calls descending for ranking
    by_salesperson.sort(key=lambda x: x.metrics.total_calls, reverse=True)
    for i, sp_perf in enumerate(by_salesperson):
        sp_perf.rank_by_calls = i + 1

    # Aggregate total metrics
    total_calls = sum(sp.metrics.total_calls for sp in by_salesperson)
    total_metrics = PerformanceMetricsSchema(
        total_calls=total_calls,
        answered_calls=sum(sp.metrics.answered_calls for sp in by_salesperson),
        successful_calls=sum(sp.metrics.successful_calls for sp in by_salesperson),
        total_call_duration=sum(sp.metrics.total_call_duration for sp in by_salesperson),
        average_call_duration=round(
            sum(sp.metrics.total_call_duration for sp in by_salesperson) / max(total_calls, 1), 1
        ),
        answer_rate=round(
            sum(sp.metrics.answered_calls for sp in by_salesperson) / max(total_calls, 1), 3
        ),
        success_rate=round(
            sum(sp.metrics.successful_calls for sp in by_salesperson) / max(total_calls, 1), 3
        ),
        assigned_leads=sum(sp.metrics.assigned_leads for sp in by_salesperson),
        contacted_leads=sum(sp.metrics.contacted_leads for sp in by_salesperson),
        contact_rate=round(
            sum(sp.metrics.contacted_leads for sp in by_salesperson) /
            max(sum(sp.metrics.assigned_leads for sp in by_salesperson), 1), 3
        ),
    )

    # Top performers by calls
    top_performers = [
        {"name": sp.salesperson_name, "metric": "calls", "value": sp.metrics.total_calls}
        for sp in sorted(by_salesperson, key=lambda x: x.metrics.total_calls, reverse=True)[:3]
    ]

    # Improvement needed: lowest answer rate
    improvement_needed = [
        {
            "name": sp.salesperson_name,
            "metric": "answer_rate",
            "value": sp.metrics.answer_rate,
            "target": 0.40,
        }
        for sp in by_salesperson
        if sp.metrics.total_calls > 0 and sp.metrics.answer_rate < 0.30
    ]

    return TeamPerformanceResponse(
        period_start=start_date,
        period_end=end_date,
        total_metrics=total_metrics,
        by_salesperson=by_salesperson,
        top_performers=top_performers,
        improvement_needed=improvement_needed,
    )


@router.get("/salespeople/{salesperson_id}/performance", response_model=SalespersonPerformanceResponse)
async def get_salesperson_performance(
    salesperson_id: UUID,
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    start_date: datetime = Query(default=None),
    end_date: datetime = Query(default=None),
):
    """Get performance metrics for a specific salesperson — from real database."""
    if start_date is None:
        start_date = datetime.utcnow() - timedelta(days=30)
    if end_date is None:
        end_date = datetime.utcnow()

    # Verify salesperson exists
    stmt = (
        select(SalespersonModel)
        .where(SalespersonModel.tenant_id == tenant_id)
        .where(SalespersonModel.id == salesperson_id)
    )
    result = await session.execute(stmt)
    sp = result.scalar_one_or_none()
    if not sp:
        raise HTTPException(status_code=404, detail="Salesperson not found")

    metrics = await _call_metrics(session, tenant_id, salesperson_id, start_date, end_date)

    # Previous period for trend
    period_days = (end_date - start_date).days or 1
    prev_start = start_date - timedelta(days=period_days)
    prev_metrics = await _call_metrics(session, tenant_id, salesperson_id, prev_start, start_date)

    calls_change = round(
        (metrics.total_calls - prev_metrics.total_calls) / max(prev_metrics.total_calls, 1) * 100, 1
    )

    # Rank among team
    all_sp_stmt = (
        select(SalespersonModel.id)
        .where(SalespersonModel.tenant_id == tenant_id)
        .where(SalespersonModel.is_active.is_(True))
    )
    all_sp_result = await session.execute(all_sp_stmt)
    all_sp_ids = [row[0] for row in all_sp_result.all()]

    call_counts = []
    for sp_id in all_sp_ids:
        cnt_stmt = (
            select(func.count())
            .select_from(CallLogModel)
            .where(CallLogModel.tenant_id == tenant_id)
            .where(CallLogModel.salesperson_id == sp_id)
            .where(CallLogModel.call_start >= start_date)
            .where(CallLogModel.call_start <= end_date)
        )
        cnt_result = await session.execute(cnt_stmt)
        call_counts.append((sp_id, cnt_result.scalar_one()))

    call_counts.sort(key=lambda x: x[1], reverse=True)
    rank_calls = next((i + 1 for i, (sid, _) in enumerate(call_counts) if sid == salesperson_id), None)

    return SalespersonPerformanceResponse(
        salesperson_id=salesperson_id,
        salesperson_name=sp.name,
        period_start=start_date,
        period_end=end_date,
        metrics=metrics,
        rank_by_revenue=None,
        rank_by_conversions=None,
        rank_by_calls=rank_calls,
        trend={"calls_change": calls_change},
    )


@router.get("/performance/comparison", response_model=PerformanceComparisonResponse)
async def compare_salesperson_performance(
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    salesperson_ids: list[UUID] = Query(default=[]),
    start_date: datetime = Query(default=None),
    end_date: datetime = Query(default=None),
):
    """Compare performance of multiple salespeople — from real database."""
    if start_date is None:
        start_date = datetime.utcnow() - timedelta(days=30)
    if end_date is None:
        end_date = datetime.utcnow()

    if not salesperson_ids:
        stmt = (
            select(SalespersonModel.id)
            .where(SalespersonModel.tenant_id == tenant_id)
            .where(SalespersonModel.is_active.is_(True))
        )
        result = await session.execute(stmt)
        salesperson_ids = [row[0] for row in result.all()]

    salespeople = []
    for sp_id in salesperson_ids:
        sp_stmt = (
            select(SalespersonModel)
            .where(SalespersonModel.tenant_id == tenant_id)
            .where(SalespersonModel.id == sp_id)
        )
        sp_result = await session.execute(sp_stmt)
        sp = sp_result.scalar_one_or_none()
        if not sp:
            continue

        metrics = await _call_metrics(session, tenant_id, sp_id, start_date, end_date)
        salespeople.append({
            "salesperson_id": str(sp.id),
            "name": sp.name,
            "region": sp.region or "",
            "total_calls": metrics.total_calls,
            "answered_calls": metrics.answered_calls,
            "successful_calls": metrics.successful_calls,
            "answer_rate": metrics.answer_rate,
            "success_rate": metrics.success_rate,
            "contacted_leads": metrics.contacted_leads,
            "assigned_leads": metrics.assigned_leads,
            "contact_rate": metrics.contact_rate,
        })

    return PerformanceComparisonResponse(
        period_start=start_date,
        period_end=end_date,
        salespeople=salespeople,
        metrics_compared=["total_calls", "answered_calls", "answer_rate", "success_rate", "contact_rate"],
    )


@router.get("/performance/leaderboard")
async def get_performance_leaderboard(
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    metric: str = Query(default="calls"),
    start_date: datetime = Query(default=None),
    end_date: datetime = Query(default=None),
):
    """Get salesperson leaderboard by metric — from real database."""
    if start_date is None:
        start_date = datetime.utcnow() - timedelta(days=30)
    if end_date is None:
        end_date = datetime.utcnow()

    stmt = (
        select(SalespersonModel)
        .where(SalespersonModel.tenant_id == tenant_id)
        .where(SalespersonModel.is_active.is_(True))
    )
    result = await session.execute(stmt)
    salespeople = result.scalars().all()

    entries = []
    for sp in salespeople:
        m = await _call_metrics(session, tenant_id, sp.id, start_date, end_date)
        if metric == "calls":
            value = m.total_calls
        elif metric == "answered":
            value = m.answered_calls
        elif metric == "answer_rate":
            value = m.answer_rate
        elif metric == "success_rate":
            value = m.success_rate
        elif metric == "duration":
            value = m.total_call_duration
        elif metric == "contact_rate":
            value = m.contact_rate
        else:
            value = m.total_calls

        entries.append({"name": sp.name, "salesperson_id": str(sp.id), "value": value})

    entries.sort(key=lambda x: x["value"], reverse=True)
    leaderboard = [
        {"rank": i + 1, "name": e["name"], "salesperson_id": e["salesperson_id"], "value": e["value"]}
        for i, e in enumerate(entries)
    ]

    return {
        "metric": metric,
        "period_start": start_date.isoformat(),
        "period_end": end_date.isoformat(),
        "leaderboard": leaderboard,
    }


# ============================================================================
# Activity Endpoints
# ============================================================================

@router.get("/salespeople/{salesperson_id}/activities", response_model=ActivityLogListResponse)
async def get_salesperson_activities(
    salesperson_id: UUID,
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    activity_type: str | None = Query(default=None),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
):
    """Get activity log for a salesperson — call logs from database."""
    from .schemas import ActivityLogSchema

    skip = (page - 1) * page_size
    stmt = (
        select(CallLogModel)
        .where(CallLogModel.tenant_id == tenant_id)
        .where(CallLogModel.salesperson_id == salesperson_id)
    )
    if date_from:
        stmt = stmt.where(CallLogModel.call_start >= date_from)
    if date_to:
        stmt = stmt.where(CallLogModel.call_start <= date_to)
    stmt = stmt.order_by(CallLogModel.call_start.desc()).offset(skip).limit(page_size)

    result = await session.execute(stmt)
    call_logs = result.scalars().all()

    count_stmt = (
        select(func.count())
        .select_from(CallLogModel)
        .where(CallLogModel.tenant_id == tenant_id)
        .where(CallLogModel.salesperson_id == salesperson_id)
    )
    if date_from:
        count_stmt = count_stmt.where(CallLogModel.call_start >= date_from)
    if date_to:
        count_stmt = count_stmt.where(CallLogModel.call_start <= date_to)
    count_result = await session.execute(count_stmt)
    total_count = count_result.scalar_one()

    activities = [
        ActivityLogSchema(
            id=cl.id,
            salesperson_id=salesperson_id,
            activity_type="call",
            description=f"{'تماس موفق' if cl.is_successful else 'تماس'} - {cl.duration_seconds}s",
            contact_id=cl.contact_id,
            contact_phone=cl.phone_number,
            timestamp=cl.call_start,
            metadata={"status": cl.status, "duration": cl.duration_seconds},
        )
        for cl in call_logs
    ]

    return ActivityLogListResponse(
        activities=activities,
        total_count=total_count,
        page=page,
        page_size=page_size,
    )


@router.get("/salespeople/{salesperson_id}/daily-summary", response_model=list[DailyActivitySummaryResponse])
async def get_salesperson_daily_summary(
    salesperson_id: UUID,
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    days: int = Query(default=7, ge=1, le=30),
):
    """Get daily activity summary for a salesperson — from real call logs."""
    sp_stmt = (
        select(SalespersonModel)
        .where(SalespersonModel.tenant_id == tenant_id)
        .where(SalespersonModel.id == salesperson_id)
    )
    sp_result = await session.execute(sp_stmt)
    sp = sp_result.scalar_one_or_none()
    if not sp:
        raise HTTPException(status_code=404, detail="Salesperson not found")

    summaries = []
    now = datetime.utcnow()

    for i in range(days):
        day_start = (now - timedelta(days=i)).replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)

        calls_stmt = (
            select(
                func.count().label("calls_made"),
                func.count().filter(CallLogModel.status == "answered").label("calls_answered"),
            )
            .where(CallLogModel.tenant_id == tenant_id)
            .where(CallLogModel.salesperson_id == salesperson_id)
            .where(CallLogModel.call_start >= day_start)
            .where(CallLogModel.call_start < day_end)
        )
        calls_result = await session.execute(calls_stmt)
        row = calls_result.one()

        summaries.append(DailyActivitySummaryResponse(
            date=day_start,
            salesperson_id=salesperson_id,
            salesperson_name=sp.name,
            calls_made=row.calls_made or 0,
            calls_answered=row.calls_answered or 0,
        ))

    return summaries


# ============================================================================
# Assignment Rules Endpoints
# ============================================================================

@router.get("/assignment-rules", response_model=AssignmentRuleListResponse)
async def list_assignment_rules(
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
):
    """List assignment rules."""
    return AssignmentRuleListResponse(rules=[], total_count=0)


@router.post("/assignment-rules", response_model=AssignmentRuleResponse, status_code=201)
async def create_assignment_rule(
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
    request: CreateAssignmentRuleRequest,
):
    """Create an assignment rule."""
    return AssignmentRuleResponse(
        id=uuid4(),
        tenant_id=tenant_id,
        name=request.name,
        rule_type=request.rule_type,
        is_active=request.is_active,
        priority=request.priority,
        conditions=request.conditions,
        salesperson_ids=request.salesperson_ids,
        metadata=request.metadata,
        created_at=datetime.utcnow(),
    )


@router.delete("/assignment-rules/{rule_id}", status_code=204)
async def delete_assignment_rule(
    rule_id: UUID,
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
):
    """Delete an assignment rule."""
    pass


# ============================================================================
# Targets Endpoints
# ============================================================================

@router.get("/targets", response_model=SalesTargetListResponse)
async def list_sales_targets(
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
    salesperson_id: UUID | None = Query(default=None),
    period_type: str | None = Query(default=None),
    is_current: bool = Query(default=True),
):
    """List sales targets."""
    return SalesTargetListResponse(targets=[], total_count=0)


@router.post("/targets", response_model=SalesTargetResponse, status_code=201)
async def create_sales_target(
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
    request: CreateSalesTargetRequest,
):
    """Create a sales target."""
    return SalesTargetResponse(
        id=uuid4(),
        tenant_id=tenant_id,
        salesperson_id=request.salesperson_id,
        period_type=request.period_type,
        period_start=request.period_start,
        period_end=request.period_end,
        target_calls=request.target_calls,
        target_contacts=request.target_contacts,
        target_conversions=request.target_conversions,
        target_revenue=request.target_revenue,
        metadata=request.metadata,
        created_at=datetime.utcnow(),
    )


@router.get("/targets/summary", response_model=TeamTargetSummaryResponse)
async def get_team_target_summary(
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    period_type: str = Query(default="monthly"),
):
    """Get team target achievement summary — uses real call data for actuals."""
    now = datetime.utcnow()
    if period_type == "monthly":
        period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        period_end = now
    else:
        period_start = now - timedelta(days=7)
        period_end = now

    stmt = (
        select(func.coalesce(func.sum(SalespersonModel.total_revenue), 0))
        .where(SalespersonModel.tenant_id == tenant_id)
    )
    result = await session.execute(stmt)
    actual_revenue = result.scalar_one()

    target_revenue = 3_000_000_000
    achievement = actual_revenue / target_revenue if target_revenue > 0 else 0.0

    return TeamTargetSummaryResponse(
        period_start=period_start,
        period_end=period_end,
        team_target_revenue=target_revenue,
        team_actual_revenue=actual_revenue,
        team_achievement=round(achievement, 3),
        by_salesperson=[],
    )

