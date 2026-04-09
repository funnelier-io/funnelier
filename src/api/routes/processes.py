"""
Camunda BPMS API Routes

REST endpoints for managing Camunda processes from the dashboard.
Provides process instance listing, message correlation, and status queries.
"""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from src.api.dependencies import get_current_tenant_id
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


@router.get("/instances/{instance_id}/variables")
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


@router.post("/messages")
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


@router.get("/instances/{instance_id}/history")
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


@router.get("/deployments")
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

