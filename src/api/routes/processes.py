"""
Camunda BPMS API Routes

REST endpoints for managing Camunda processes from the dashboard.
Provides process instance listing, message correlation, and status queries.
"""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_current_tenant_id, get_db_session
from src.infrastructure.camunda.client import (
    CamundaClient,
    CamundaConnectionError,
    CamundaError,
    CamundaProcessNotFoundError,
    get_camunda_client,
)

router = APIRouter(prefix="/processes", tags=["Camunda BPMS"])


# ─── Schemas ─────────────────────────────────────────────────────────────────


class ProcessInstanceResponse(BaseModel):
    id: str
    definition_id: str
    business_key: str | None = None
    tenant_id: str | None = None
    ended: bool = False
    suspended: bool = False


class ProcessDefinitionResponse(BaseModel):
    id: str
    key: str
    name: str | None = None
    version: int = 0
    deployment_id: str | None = None
    suspended: bool = False


class StartProcessRequest(BaseModel):
    process_key: str
    business_key: str | None = None
    variables: dict[str, Any] = Field(default_factory=dict)


class CorrelateMessageRequest(BaseModel):
    message_name: str
    business_key: str | None = None
    process_instance_id: str | None = None
    variables: dict[str, Any] = Field(default_factory=dict)


class CamundaHealthResponse(BaseModel):
    enabled: bool
    healthy: bool = False
    engine_url: str = ""
    engine_version: str | None = None
    process_definitions: int = 0
    active_instances: int = 0


class ProcessOverviewResponse(BaseModel):
    """Dashboard widget: aggregated process overview."""
    camunda_enabled: bool = False
    healthy: bool = False
    process_types: list[dict[str, Any]] = Field(default_factory=list)
    total_active: int = 0
    total_completed: int = 0
    total_failed: int = 0
    escalations_pending: int = 0
    source: str = "database"  # "camunda" or "database"


class StartEscalationRequest(BaseModel):
    """Request to trigger an ERP sync failure escalation."""
    source_name: str = Field(..., description="ERP data source name")
    error_message: str = Field(..., description="Error description")
    max_retries: int = Field(default=3, ge=1, le=10)


class StartEscalationResponse(BaseModel):
    """Response after starting an ERP sync escalation."""
    process_instance_id: str | None = None
    source_name: str
    camunda_enabled: bool = False
    fallback_used: bool = False


# ─── Helper ──────────────────────────────────────────────────────────────────


def _get_client() -> CamundaClient:
    client = get_camunda_client()
    if not client.enabled:
        raise HTTPException(
            status_code=503,
            detail="Camunda BPMS is not enabled (set CAMUNDA_ENABLED=true)",
        )
    return client


# ─── Endpoints ───────────────────────────────────────────────────────────────


@router.get("/health", response_model=CamundaHealthResponse)
async def camunda_health(
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
):
    """Get Camunda BPMS health and status."""
    client = get_camunda_client()

    result = CamundaHealthResponse(
        enabled=client.enabled,
        engine_url=client.settings.base_url,
    )

    if not client.enabled:
        return result

    try:
        result.healthy = await client.check_health()

        if result.healthy:
            # Get engine version
            try:
                info = await client.get_engine_info()
                result.engine_version = info.get("version")
            except Exception:
                pass

            # Count process definitions
            try:
                defs = await client.list_process_definitions()
                result.process_definitions = len(defs)
            except Exception:
                pass

            # Count active instances for this tenant
            try:
                instances = await client.list_process_instances(
                    tenant_variable=str(tenant_id), active=True
                )
                result.active_instances = len(instances)
            except Exception:
                pass

    except CamundaConnectionError:
        result.healthy = False

    return result


@router.get("/definitions", response_model=list[ProcessDefinitionResponse])
async def list_process_definitions(
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
):
    """List all deployed BPMN process definitions."""
    client = _get_client()
    try:
        defs = await client.list_process_definitions()
        return [
            ProcessDefinitionResponse(
                id=d.id, key=d.key, name=d.name,
                version=d.version, deployment_id=d.deployment_id,
                suspended=d.suspended,
            )
            for d in defs
        ]
    except CamundaConnectionError as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.get("/instances", response_model=list[ProcessInstanceResponse])
async def list_process_instances(
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
    process_key: str | None = Query(default=None),
    business_key: str | None = Query(default=None),
    active_only: bool = Query(default=True),
):
    """List process instances for the current tenant."""
    client = _get_client()
    try:
        instances = await client.list_process_instances(
            process_key=process_key,
            business_key=business_key,
            tenant_variable=str(tenant_id),
            active=True if active_only else None,
        )
        return [
            ProcessInstanceResponse(
                id=i.id, definition_id=i.definition_id,
                business_key=i.business_key, tenant_id=i.tenant_id,
                ended=i.ended, suspended=i.suspended,
            )
            for i in instances
        ]
    except CamundaConnectionError as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.post("/instances", response_model=ProcessInstanceResponse, status_code=201)
async def start_process(
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
    request: StartProcessRequest,
):
    """Start a new BPMN process instance."""
    client = _get_client()
    try:
        instance = await client.start_process(
            process_key=request.process_key,
            business_key=request.business_key,
            variables=request.variables,
            tenant_id=str(tenant_id),
        )
        return ProcessInstanceResponse(
            id=instance.id,
            definition_id=instance.definition_id,
            business_key=instance.business_key,
            tenant_id=instance.tenant_id,
            ended=instance.ended,
            suspended=instance.suspended,
        )
    except CamundaProcessNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=f"Process definition not found: {request.process_key}",
        )
    except CamundaConnectionError as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.get("/instances/{instance_id}", response_model=ProcessInstanceResponse)
async def get_process_instance(
    instance_id: str,
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
):
    """Get a specific process instance."""
    client = _get_client()
    try:
        instance = await client.get_process_instance(instance_id)
        return ProcessInstanceResponse(
            id=instance.id,
            definition_id=instance.definition_id,
            business_key=instance.business_key,
            tenant_id=instance.tenant_id,
            ended=instance.ended,
            suspended=instance.suspended,
        )
    except CamundaProcessNotFoundError:
        raise HTTPException(status_code=404, detail="Process instance not found")
    except CamundaConnectionError as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.get("/instances/{instance_id}/variables", response_model=dict)
async def get_process_variables(
    instance_id: str,
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
):
    """Get all variables of a process instance."""
    client = _get_client()
    try:
        return await client.get_process_variables(instance_id)
    except CamundaProcessNotFoundError:
        raise HTTPException(status_code=404, detail="Process instance not found")
    except CamundaConnectionError as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.delete("/instances/{instance_id}", status_code=204)
async def cancel_process_instance(
    instance_id: str,
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
    reason: str = Query(default="Cancelled by user"),
):
    """Cancel (delete) a process instance."""
    client = _get_client()
    try:
        await client.delete_process_instance(instance_id, reason=reason)
    except CamundaProcessNotFoundError:
        raise HTTPException(status_code=404, detail="Process instance not found")
    except CamundaConnectionError as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.post("/messages", response_model=dict)
async def correlate_message(
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
    request: CorrelateMessageRequest,
):
    """
    Correlate a BPMN message to advance a process instance.

    Used when external events happen (SMS delivered, call answered, etc.)
    to push a process instance to the next step.
    """
    client = _get_client()
    try:
        result = await client.correlate_message(
            message_name=request.message_name,
            business_key=request.business_key,
            process_instance_id=request.process_instance_id,
            variables=request.variables,
            tenant_id=str(tenant_id),
        )
        return {"status": "correlated", "message": request.message_name, "result": result}
    except CamundaError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except CamundaConnectionError as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.get("/instances/{instance_id}/history", response_model=list)
async def get_process_history(
    instance_id: str,
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
):
    """Get the activity history of a process instance (audit trail)."""
    client = _get_client()
    try:
        activities = await client.get_activity_instance_history(instance_id)
        return {
            "process_instance_id": instance_id,
            "activities": activities,
        }
    except CamundaConnectionError as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.get("/deployments", response_model=list)
async def list_deployments(
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
):
    """List all BPMN deployments."""
    client = _get_client()
    try:
        deployments = await client.list_deployments()
        return {
            "deployments": [
                {
                    "id": d.id,
                    "name": d.name,
                    "deployment_time": d.deployment_time,
                    "source": d.source,
                }
                for d in deployments
            ]
        }
    except CamundaConnectionError as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.get("/overview", response_model=ProcessOverviewResponse)
async def get_process_overview(
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
):
    """
    Get an aggregated process overview for the dashboard widget.

    Works from both Camunda (if enabled) and the database fallback.
    Returns counts by process type (campaigns, funnel journeys, ERP syncs),
    plus pending escalations from the notification table.
    """
    client = get_camunda_client()
    result = ProcessOverviewResponse(camunda_enabled=client.enabled)

    # Always query database for process-related stats
    from sqlalchemy import select, func
    from src.infrastructure.database.models.etl import ImportLogModel
    from src.infrastructure.database.models.notifications import NotificationModel

    # Import logs as proxy for process activity
    import_stats_stmt = (
        select(
            ImportLogModel.status,
            func.count(ImportLogModel.id),
        )
        .where(ImportLogModel.tenant_id == tenant_id)
        .group_by(ImportLogModel.status)
    )
    import_result = await session.execute(import_stats_stmt)
    import_by_status = dict(import_result.all())

    completed_imports = import_by_status.get("completed", 0)
    failed_imports = import_by_status.get("failed", 0)
    running_imports = import_by_status.get("running", 0)

    # Pending escalations (critical unread notifications from ERP/SMS)
    escalation_stmt = (
        select(func.count(NotificationModel.id))
        .where(NotificationModel.tenant_id == tenant_id)
        .where(NotificationModel.is_read == False)
        .where(NotificationModel.severity == "critical")
        .where(NotificationModel.source_type.in_([
            "erp_sync_escalation", "sms_compensation", "stale_stage",
        ]))
    )
    escalation_result = await session.execute(escalation_stmt)
    escalations_pending = escalation_result.scalar() or 0

    # Contact funnel stage counts (as proxy for funnel journey activity)
    from src.infrastructure.database.models.leads import ContactModel
    funnel_stmt = (
        select(func.count(ContactModel.id))
        .where(ContactModel.tenant_id == tenant_id)
        .where(ContactModel.is_active == True)
        .where(ContactModel.current_stage != "lead_acquired")
    )
    funnel_result = await session.execute(funnel_stmt)
    active_journeys = funnel_result.scalar() or 0

    # Campaign counts
    from src.infrastructure.database.models.communications import CampaignModel
    campaign_stats_stmt = (
        select(CampaignModel.status, func.count(CampaignModel.id))
        .where(CampaignModel.tenant_id == tenant_id)
        .group_by(CampaignModel.status)
    )
    campaign_result = await session.execute(campaign_stats_stmt)
    campaign_by_status = dict(campaign_result.all())

    active_campaigns = campaign_by_status.get("sending", 0) + campaign_by_status.get("tracking", 0)
    completed_campaigns = campaign_by_status.get("completed", 0)
    failed_campaigns = campaign_by_status.get("failed", 0) + campaign_by_status.get("partially_sent", 0)

    # Build process_types summary
    process_types = [
        {
            "type": "campaign_lifecycle",
            "display_name": "کمپین پیامکی",
            "active": active_campaigns,
            "completed": completed_campaigns,
            "failed": failed_campaigns,
        },
        {
            "type": "funnel_journey",
            "display_name": "سفر قیف فروش",
            "active": active_journeys,
            "completed": 0,  # Would need payment_received count
            "failed": 0,
        },
        {
            "type": "erp_sync",
            "display_name": "همگام‌سازی ERP",
            "active": running_imports,
            "completed": completed_imports,
            "failed": failed_imports,
        },
    ]

    result.process_types = process_types
    result.total_active = active_campaigns + active_journeys + running_imports
    result.total_completed = completed_campaigns + completed_imports
    result.total_failed = failed_campaigns + failed_imports
    result.escalations_pending = escalations_pending
    result.source = "database"

    # If Camunda is available, try to enrich with live data
    if client.enabled:
        try:
            health = await client.check_health()
            result.healthy = health
            if health:
                result.source = "camunda+database"
        except Exception:
            pass

    return result


@router.post("/escalations/erp-sync", response_model=StartEscalationResponse, status_code=201)
async def start_erp_sync_escalation(
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
    request: StartEscalationRequest,
):
    """
    Trigger an ERP sync failure escalation workflow.

    Starts a Camunda process (if enabled) that will:
    1. Log the failure
    2. Retry up to max_retries times (5-min intervals)
    3. If all retries fail, escalate to tenant admin with critical notification
    4. Send 24h reminders until manually resolved

    Falls back to direct notification if Camunda is disabled.
    """
    client = get_camunda_client()
    tenant_str = str(tenant_id)

    if client.enabled:
        try:
            instance = await client.start_process(
                process_key="erp_sync_escalation",
                business_key=f"erp-sync-{request.source_name}-{tenant_str[:8]}",
                variables={
                    "tenant_id": tenant_str,
                    "source_name": request.source_name,
                    "error_message": request.error_message,
                    "max_retries": request.max_retries,
                    "retry_count": 0,
                },
                tenant_id=tenant_str,
            )
            return StartEscalationResponse(
                process_instance_id=instance.id,
                source_name=request.source_name,
                camunda_enabled=True,
            )
        except (CamundaConnectionError, CamundaError) as e:
            # Fall through to DB-only fallback
            pass

    # Fallback: create notification directly
    from src.infrastructure.database.session import get_session_factory
    from src.infrastructure.database.models.notifications import NotificationModel
    from src.infrastructure.database.models.tenants import TenantUserModel
    from sqlalchemy import select

    session_factory = get_session_factory()
    async with session_factory() as session:
        admin_stmt = (
            select(TenantUserModel.id)
            .where(TenantUserModel.tenant_id == tenant_id)
            .where(TenantUserModel.role.in_(["super_admin", "tenant_admin"]))
            .where(TenantUserModel.is_active.is_(True))
            .limit(1)
        )
        admin_result = await session.execute(admin_stmt)
        admin_id = admin_result.scalar_one_or_none()
        user_id = admin_id if admin_id else tenant_id

        notification = NotificationModel(
            tenant_id=tenant_id,
            user_id=user_id,
            type="alert",
            severity="critical",
            title=f"خطای همگام‌سازی ERP — {request.source_name}",
            body=(
                f"همگام‌سازی داده از منبع «{request.source_name}» ناموفق بود.\n"
                f"خطا: {request.error_message[:200]}\n"
                f"لطفاً بررسی و اقدام کنید."
            ),
            source_type="erp_sync_escalation",
            metadata_json={
                "source_name": request.source_name,
                "error_message": request.error_message,
                "fallback": True,
            },
        )
        session.add(notification)
        await session.commit()

    return StartEscalationResponse(
        source_name=request.source_name,
        camunda_enabled=False,
        fallback_used=True,
    )

