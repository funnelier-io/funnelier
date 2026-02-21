"""
Team API Routes

FastAPI routes for salesperson and team management.
"""

from datetime import datetime, timedelta
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query

from src.api.dependencies import get_current_tenant_id

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



# ============================================================================
# Salesperson CRUD Endpoints
# ============================================================================

@router.get("/salespeople", response_model=SalespersonListResponse)
async def list_salespeople(
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
    is_active: bool | None = Query(default=None),
    region: str | None = Query(default=None),
):
    """
    List all salespeople.
    """
    # Sample salespeople based on the business context
    salespeople = [
        SalespersonResponse(
            id=uuid4(),
            tenant_id=tenant_id,
            name="اسدالهی",
            phone_number="989121234567",
            role="salesperson",
            regions=["تهران"],
            is_active=True,
            assigned_leads=600,
            active_leads=400,
            created_at=datetime.utcnow() - timedelta(days=365),
        ),
        SalespersonResponse(
            id=uuid4(),
            tenant_id=tenant_id,
            name="بردبار",
            phone_number="989121234568",
            role="salesperson",
            regions=["شیراز", "فارس"],
            is_active=True,
            assigned_leads=550,
            active_leads=380,
            created_at=datetime.utcnow() - timedelta(days=300),
        ),
        SalespersonResponse(
            id=uuid4(),
            tenant_id=tenant_id,
            name="رضایی",
            phone_number="989121234569",
            role="salesperson",
            regions=["تهران"],
            is_active=True,
            assigned_leads=580,
            active_leads=350,
            created_at=datetime.utcnow() - timedelta(days=280),
        ),
        SalespersonResponse(
            id=uuid4(),
            tenant_id=tenant_id,
            name="کاشی",
            phone_number="989121234570",
            role="salesperson",
            regions=["اصفهان"],
            is_active=True,
            assigned_leads=520,
            active_leads=320,
            created_at=datetime.utcnow() - timedelta(days=250),
        ),
        SalespersonResponse(
            id=uuid4(),
            tenant_id=tenant_id,
            name="نخست",
            phone_number="989121234571",
            role="salesperson",
            regions=["گیلان", "مازندران"],
            is_active=True,
            assigned_leads=500,
            active_leads=300,
            created_at=datetime.utcnow() - timedelta(days=220),
        ),
        SalespersonResponse(
            id=uuid4(),
            tenant_id=tenant_id,
            name="فدایی",
            phone_number="989121234572",
            role="salesperson",
            regions=["شیراز"],
            is_active=True,
            assigned_leads=480,
            active_leads=280,
            created_at=datetime.utcnow() - timedelta(days=200),
        ),
        SalespersonResponse(
            id=uuid4(),
            tenant_id=tenant_id,
            name="شفیعی",
            phone_number="989121234573",
            role="salesperson",
            regions=["کرمانشاه"],
            is_active=True,
            assigned_leads=450,
            active_leads=260,
            created_at=datetime.utcnow() - timedelta(days=180),
        ),
        SalespersonResponse(
            id=uuid4(),
            tenant_id=tenant_id,
            name="حیدری",
            phone_number="989121234574",
            role="salesperson",
            regions=["بوشهر", "خوزستان"],
            is_active=True,
            assigned_leads=420,
            active_leads=240,
            created_at=datetime.utcnow() - timedelta(days=150),
        ),
        SalespersonResponse(
            id=uuid4(),
            tenant_id=tenant_id,
            name="آتشین",
            phone_number="989121234575",
            role="salesperson",
            regions=["شیراز"],
            is_active=True,
            assigned_leads=400,
            active_leads=220,
            created_at=datetime.utcnow() - timedelta(days=120),
        ),
    ]

    return SalespersonListResponse(
        salespeople=salespeople,
        total_count=len(salespeople),
    )


@router.post("/salespeople", response_model=SalespersonResponse, status_code=201)
async def create_salesperson(
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
    request: CreateSalespersonRequest,
):
    """
    Create a new salesperson.
    """
    return SalespersonResponse(
        id=uuid4(),
        tenant_id=tenant_id,
        name=request.name,
        phone_number=request.phone_number,
        email=request.email,
        role=request.role,
        regions=request.regions,
        is_active=request.is_active,
        max_leads=request.max_leads,
        user_id=request.user_id,
        metadata=request.metadata,
        created_at=datetime.utcnow(),
    )


@router.get("/salespeople/{salesperson_id}", response_model=SalespersonResponse)
async def get_salesperson(
    salesperson_id: UUID,
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
):
    """
    Get salesperson by ID.
    """
    raise HTTPException(status_code=404, detail="Salesperson not found")


@router.put("/salespeople/{salesperson_id}", response_model=SalespersonResponse)
async def update_salesperson(
    salesperson_id: UUID,
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
    request: UpdateSalespersonRequest,
):
    """
    Update a salesperson.
    """
    raise HTTPException(status_code=404, detail="Salesperson not found")


@router.delete("/salespeople/{salesperson_id}", status_code=204)
async def delete_salesperson(
    salesperson_id: UUID,
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
):
    """
    Delete a salesperson.
    """
    pass


# ============================================================================
# Performance Endpoints
# ============================================================================

@router.get("/performance", response_model=TeamPerformanceResponse)
async def get_team_performance(
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
    start_date: datetime = Query(default=None),
    end_date: datetime = Query(default=None),
):
    """
    Get team performance summary.
    """
    if start_date is None:
        start_date = datetime.utcnow() - timedelta(days=30)
    if end_date is None:
        end_date = datetime.utcnow()

    return TeamPerformanceResponse(
        period_start=start_date,
        period_end=end_date,
        total_metrics=PerformanceMetricsSchema(
            total_calls=3000,
            answered_calls=1200,
            successful_calls=600,
            total_call_duration=360000,
            average_call_duration=120.0,
            answer_rate=0.40,
            success_rate=0.20,
            assigned_leads=4500,
            contacted_leads=2700,
            contact_rate=0.60,
            invoices_created=250,
            invoices_paid=150,
            conversion_rate=0.033,
            total_revenue=2_000_000_000,
            average_deal_size=13_333_333,
        ),
        by_salesperson=[],
        top_performers=[
            {"name": "اسدالهی", "metric": "revenue", "value": 300_000_000},
            {"name": "بردبار", "metric": "conversions", "value": 28},
        ],
        improvement_needed=[
            {"name": "آتشین", "metric": "contact_rate", "value": 0.45, "target": 0.60},
        ],
    )


@router.get("/salespeople/{salesperson_id}/performance", response_model=SalespersonPerformanceResponse)
async def get_salesperson_performance(
    salesperson_id: UUID,
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
    start_date: datetime = Query(default=None),
    end_date: datetime = Query(default=None),
):
    """
    Get performance metrics for a specific salesperson.
    """
    if start_date is None:
        start_date = datetime.utcnow() - timedelta(days=30)
    if end_date is None:
        end_date = datetime.utcnow()

    return SalespersonPerformanceResponse(
        salesperson_id=salesperson_id,
        salesperson_name="Sample Salesperson",
        period_start=start_date,
        period_end=end_date,
        metrics=PerformanceMetricsSchema(
            total_calls=400,
            answered_calls=150,
            successful_calls=75,
            total_call_duration=45000,
            average_call_duration=112.5,
            answer_rate=0.375,
            success_rate=0.188,
            assigned_leads=600,
            contacted_leads=400,
            contact_rate=0.667,
            invoices_created=30,
            invoices_paid=18,
            conversion_rate=0.03,
            total_revenue=300_000_000,
            average_deal_size=16_666_667,
        ),
        rank_by_revenue=1,
        rank_by_conversions=2,
        rank_by_calls=3,
        trend={
            "revenue_change": 15.5,
            "conversion_change": -2.3,
            "calls_change": 8.0,
        },
    )


@router.get("/performance/comparison", response_model=PerformanceComparisonResponse)
async def compare_salesperson_performance(
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
    salesperson_ids: list[UUID] = Query(default=[]),
    start_date: datetime = Query(default=None),
    end_date: datetime = Query(default=None),
):
    """
    Compare performance of multiple salespeople.
    """
    if start_date is None:
        start_date = datetime.utcnow() - timedelta(days=30)
    if end_date is None:
        end_date = datetime.utcnow()

    return PerformanceComparisonResponse(
        period_start=start_date,
        period_end=end_date,
        salespeople=[],
        metrics_compared=["calls", "conversions", "revenue", "contact_rate"],
    )


@router.get("/performance/leaderboard")
async def get_performance_leaderboard(
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
    metric: str = Query(default="revenue"),  # revenue, conversions, calls, contact_rate
    start_date: datetime = Query(default=None),
    end_date: datetime = Query(default=None),
):
    """
    Get salesperson leaderboard by metric.
    """
    if start_date is None:
        start_date = datetime.utcnow() - timedelta(days=30)
    if end_date is None:
        end_date = datetime.utcnow()

    return {
        "metric": metric,
        "period_start": start_date.isoformat(),
        "period_end": end_date.isoformat(),
        "leaderboard": [
            {"rank": 1, "name": "اسدالهی", "value": 300_000_000},
            {"rank": 2, "name": "بردبار", "value": 280_000_000},
            {"rank": 3, "name": "رضایی", "value": 250_000_000},
            {"rank": 4, "name": "کاشی", "value": 220_000_000},
            {"rank": 5, "name": "نخست", "value": 200_000_000},
        ],
    }


# ============================================================================
# Activity Endpoints
# ============================================================================

@router.get("/salespeople/{salesperson_id}/activities", response_model=ActivityLogListResponse)
async def get_salesperson_activities(
    salesperson_id: UUID,
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    activity_type: str | None = Query(default=None),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
):
    """
    Get activity log for a salesperson.
    """
    return ActivityLogListResponse(
        activities=[],
        total_count=0,
        page=page,
        page_size=page_size,
    )


@router.get("/salespeople/{salesperson_id}/daily-summary", response_model=list[DailyActivitySummaryResponse])
async def get_salesperson_daily_summary(
    salesperson_id: UUID,
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
    days: int = Query(default=7, ge=1, le=30),
):
    """
    Get daily activity summary for a salesperson.
    """
    return []


# ============================================================================
# Assignment Rules Endpoints
# ============================================================================

@router.get("/assignment-rules", response_model=AssignmentRuleListResponse)
async def list_assignment_rules(
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
):
    """
    List assignment rules.
    """
    return AssignmentRuleListResponse(
        rules=[],
        total_count=0,
    )


@router.post("/assignment-rules", response_model=AssignmentRuleResponse, status_code=201)
async def create_assignment_rule(
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
    request: CreateAssignmentRuleRequest,
):
    """
    Create an assignment rule.
    """
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
    """
    Delete an assignment rule.
    """
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
    """
    List sales targets.
    """
    return SalesTargetListResponse(
        targets=[],
        total_count=0,
    )


@router.post("/targets", response_model=SalesTargetResponse, status_code=201)
async def create_sales_target(
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
    request: CreateSalesTargetRequest,
):
    """
    Create a sales target.
    """
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
    period_type: str = Query(default="monthly"),
):
    """
    Get team target achievement summary.
    """
    now = datetime.utcnow()
    if period_type == "monthly":
        period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        period_end = now
    else:
        period_start = now - timedelta(days=7)
        period_end = now

    return TeamTargetSummaryResponse(
        period_start=period_start,
        period_end=period_end,
        team_target_revenue=3_000_000_000,
        team_actual_revenue=2_000_000_000,
        team_achievement=0.667,
        by_salesperson=[],
    )

