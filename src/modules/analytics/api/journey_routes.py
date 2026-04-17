"""
Funnel Journey API Routes

REST endpoints for managing contact funnel journeys.
Start journeys, correlate events, query journey status,
deploy per-tenant funnel processes, and get journey analytics.
"""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_current_tenant_id, get_db_session
from src.infrastructure.camunda.client import get_camunda_client
from src.modules.analytics.application.funnel_journey_service import (
    FUNNEL_STAGES,
    FunnelJourneyService,
)

router = APIRouter(prefix="/funnel/journeys", tags=["Funnel Journeys"])


# ─── Schemas ─────────────────────────────────────────────────────────────────


class StartJourneyRequest(BaseModel):
    """Request to start a funnel journey for a contact."""

    contact_id: UUID
    phone_number: str
    contact_name: str | None = None


class StartJourneyResponse(BaseModel):
    """Response after starting a funnel journey."""

    contact_id: UUID
    phone_number: str
    process_instance_id: str | None = None
    current_stage: str = "lead_acquired"
    camunda_enabled: bool = False


class BatchStartRequest(BaseModel):
    """Request to start journeys for multiple contacts."""

    contacts: list[dict[str, Any]] = Field(
        ..., description="List of dicts with 'id', 'phone_number', 'name' keys"
    )


class BatchStartResponse(BaseModel):
    """Response for batch journey start."""

    total: int
    started: int
    camunda_enabled: bool = False


class CorrelateEventRequest(BaseModel):
    """Request to correlate a funnel event."""

    event_name: str = Field(
        ..., description="Funnel event: sms_sent, sms_delivered, call_attempted, call_answered, invoice_issued, payment_received"
    )
    phone_number: str
    variables: dict[str, Any] = Field(default_factory=dict)


class CorrelateEventResponse(BaseModel):
    """Response after correlating a funnel event."""

    event_name: str
    phone_number: str
    correlated: bool
    new_stage: str


class JourneyStatusResponse(BaseModel):
    """Response for journey status query."""

    phone_number: str
    process_instance_id: str | None = None
    current_stage: str = "unknown"
    started_at: str | None = None
    contact_id: str | None = None
    timestamps: dict[str, str] = Field(default_factory=dict)
    source: str = "camunda"  # "camunda" or "database"


class FunnelStagesResponse(BaseModel):
    """Response listing available funnel stages."""

    stages: list[str]
    count: int


class DeployTenantFunnelRequest(BaseModel):
    """Request to deploy a custom funnel BPMN for a tenant."""

    stages: list[dict[str, Any]] = Field(
        ..., description="Stages with 'name', 'display_name', 'order' keys"
    )
    stale_timeouts: dict[str, str] = Field(
        default_factory=dict,
        description="Stage name → ISO 8601 duration (e.g. {'sms_sent': 'P14D'})",
    )


class DeployTenantFunnelResponse(BaseModel):
    """Response after deploying a tenant funnel."""

    deployment_id: str | None = None
    process_key: str
    stages_count: int
    camunda_enabled: bool = False


class JourneyAnalyticsResponse(BaseModel):
    """Journey analytics for the tenant."""

    total_active: int = 0
    by_stage: dict[str, int] = Field(default_factory=dict)
    stale_count: int = 0
    conversion_rate: float = 0.0
    camunda_enabled: bool = False
    source: str = "database"


# ─── Helper ──────────────────────────────────────────────────────────────────


def _get_journey_service() -> FunnelJourneyService:
    """Create a FunnelJourneyService with the current Camunda client."""
    client = get_camunda_client()
    return FunnelJourneyService(client)


# ─── Endpoints ───────────────────────────────────────────────────────────────


@router.get("/stages", response_model=FunnelStagesResponse)
async def list_funnel_stages(
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
):
    """List all available funnel stages in order."""
    return FunnelStagesResponse(stages=FUNNEL_STAGES, count=len(FUNNEL_STAGES))


@router.post("/start", response_model=StartJourneyResponse, status_code=201)
async def start_journey(
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
    request: StartJourneyRequest,
):
    """
    Start a funnel journey process for a contact.

    Creates a Camunda process instance (if enabled) that tracks the contact
    through funnel stages via message correlation.
    """
    service = _get_journey_service()
    process_id = await service.start_journey(
        contact_id=request.contact_id,
        tenant_id=tenant_id,
        phone_number=request.phone_number,
        contact_name=request.contact_name,
    )
    return StartJourneyResponse(
        contact_id=request.contact_id,
        phone_number=request.phone_number,
        process_instance_id=process_id,
        current_stage="lead_acquired",
        camunda_enabled=get_camunda_client().enabled,
    )


@router.post("/start/batch", response_model=BatchStartResponse)
async def start_batch_journeys(
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
    request: BatchStartRequest,
):
    """Start funnel journeys for multiple contacts (batch import)."""
    service = _get_journey_service()
    started = await service.start_batch_journeys(
        contacts=request.contacts,
        tenant_id=tenant_id,
    )
    return BatchStartResponse(
        total=len(request.contacts),
        started=started,
        camunda_enabled=get_camunda_client().enabled,
    )


@router.post("/correlate", response_model=CorrelateEventResponse)
async def correlate_event(
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    request: CorrelateEventRequest,
):
    """
    Correlate a domain event to advance a contact's funnel journey.

    This endpoint is called when external events occur (SMS sent, call answered,
    invoice issued, payment received). It updates both the Camunda process
    instance and the contact's stage in the database.
    """
    if request.event_name not in FUNNEL_STAGES[1:]:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid event name '{request.event_name}'. Must be one of: {', '.join(FUNNEL_STAGES[1:])}",
        )

    service = _get_journey_service()
    correlated = await service.correlate_event(
        event_name=request.event_name,
        phone_number=request.phone_number,
        tenant_id=tenant_id,
        variables=request.variables,
        session=session,
    )
    return CorrelateEventResponse(
        event_name=request.event_name,
        phone_number=request.phone_number,
        correlated=correlated,
        new_stage=request.event_name,
    )


@router.get("/status/{phone_number}", response_model=JourneyStatusResponse)
async def get_journey_status(
    phone_number: str,
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
):
    """
    Get the funnel journey status for a contact by phone number.

    Returns process variables from Camunda if available, otherwise
    falls back to reading the contact's current_stage from the database.
    """
    service = _get_journey_service()
    status = await service.get_journey_status(
        phone_number=phone_number,
        tenant_id=tenant_id,
    )

    if status:
        # Extract timestamp fields
        timestamps = {k: v for k, v in status.items() if k.endswith("_at") and k != "started_at"}
        return JourneyStatusResponse(
            phone_number=phone_number,
            process_instance_id=status.get("process_instance_id"),
            current_stage=status.get("current_stage", "unknown"),
            started_at=status.get("started_at"),
            contact_id=status.get("contact_id"),
            timestamps=timestamps,
            source="camunda",
        )

    # Fallback: query DB for contact's current_stage
    from src.infrastructure.database.models.leads import ContactModel
    from sqlalchemy import select

    stmt = (
        select(ContactModel.current_stage, ContactModel.stage_entered_at)
        .where(ContactModel.phone_number == phone_number)
        .where(ContactModel.tenant_id == tenant_id)
    )
    result = await session.execute(stmt)
    row = result.one_or_none()

    if not row:
        raise HTTPException(status_code=404, detail="Contact not found")

    return JourneyStatusResponse(
        phone_number=phone_number,
        current_stage=row.current_stage,
        started_at=row.stage_entered_at.isoformat() if row.stage_entered_at else None,
        source="database",
    )


@router.post("/deploy", response_model=DeployTenantFunnelResponse)
async def deploy_tenant_funnel(
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
    request: DeployTenantFunnelRequest,
):
    """
    Deploy a custom funnel BPMN process for this tenant.

    Generates a per-tenant BPMN from the provided stage configuration
    and deploys it to Camunda. Includes optional stale-stage boundary
    timer events.
    """
    from src.infrastructure.camunda.deployment import deploy_tenant_funnel as _deploy

    client = get_camunda_client()
    tenant_str = str(tenant_id)
    process_key = f"funnel_journey_{tenant_str.replace('-', '_')}"

    deployment = await _deploy(
        client=client,
        tenant_id=tenant_str,
        stages=request.stages,
        stale_timeouts=request.stale_timeouts,
    )

    return DeployTenantFunnelResponse(
        deployment_id=deployment.id if deployment else None,
        process_key=process_key,
        stages_count=len(request.stages),
        camunda_enabled=client.enabled,
    )


@router.get("/analytics", response_model=JourneyAnalyticsResponse)
async def get_journey_analytics(
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
):
    """
    Get journey analytics: active journeys by stage, stale count, conversion rate.

    Works from the database regardless of Camunda status.
    """
    from src.infrastructure.database.models.leads import ContactModel
    from sqlalchemy import select, func, case

    # Count contacts per stage
    stmt = (
        select(ContactModel.current_stage, func.count(ContactModel.id))
        .where(ContactModel.tenant_id == tenant_id)
        .where(ContactModel.is_active == True)
        .group_by(ContactModel.current_stage)
    )
    result = await session.execute(stmt)
    by_stage: dict[str, int] = {}
    total_active = 0
    for stage, count in result.all():
        by_stage[stage] = count
        total_active += count

    # Count stale contacts (stage_entered_at > 14 days ago for pre-call, > 7 days for post-call)
    from datetime import datetime, timedelta

    cutoff_14d = datetime.utcnow() - timedelta(days=14)
    cutoff_7d = datetime.utcnow() - timedelta(days=7)

    stale_stmt = (
        select(func.count(ContactModel.id))
        .where(ContactModel.tenant_id == tenant_id)
        .where(ContactModel.is_active == True)
        .where(
            case(
                (ContactModel.current_stage.in_(["lead_acquired", "sms_sent", "sms_delivered"]),
                 ContactModel.stage_entered_at < cutoff_14d),
                (ContactModel.current_stage.in_(["call_attempted", "call_answered", "invoice_issued"]),
                 ContactModel.stage_entered_at < cutoff_7d),
                else_=False,
            )
        )
    )
    stale_result = await session.execute(stale_stmt)
    stale_count = stale_result.scalar() or 0

    # Conversion rate
    payment_count = by_stage.get("payment_received", 0)
    conversion_rate = (payment_count / total_active * 100) if total_active > 0 else 0.0

    return JourneyAnalyticsResponse(
        total_active=total_active,
        by_stage=by_stage,
        stale_count=stale_count,
        conversion_rate=round(conversion_rate, 2),
        camunda_enabled=get_camunda_client().enabled,
        source="database",
    )


