"""
ERP/CRM Sync API Routes

Endpoints to manage data source connections, trigger syncs,
view sync history, and test ERP connectivity.
"""

import logging
from datetime import datetime, timezone
from typing import Annotated, Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, func, update as sa_update, desc
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_current_tenant_id
from src.infrastructure.database.session import get_session_factory
from src.infrastructure.database.models.tenants import DataSourceConnectionModel
from src.infrastructure.database.models.sync import SyncLogModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/erp", tags=["ERP Sync"])


# ════════════════════════════════════════════════════════════════════
#  Schemas
# ════════════════════════════════════════════════════════════════════

class DataSourceCreate(BaseModel):
    name: str
    source_type: str = "mongodb"  # "mongodb" | "mock" | "odoo" etc.
    connection_config: dict[str, Any] = Field(default_factory=dict)
    # e.g. {"url": "mongodb://...", "database": "mydb"}
    field_mappings: dict[str, str] = Field(default_factory=dict)
    sync_interval_minutes: int = 60
    is_active: bool = True
    description: str | None = None


class DataSourceUpdate(BaseModel):
    name: str | None = None
    connection_config: dict[str, Any] | None = None
    field_mappings: dict[str, str] | None = None
    sync_interval_minutes: int | None = None
    is_active: bool | None = None
    description: str | None = None


class DataSourceOut(BaseModel):
    id: UUID
    tenant_id: UUID
    name: str
    source_type: str
    connection_config: dict[str, Any]
    field_mappings: dict[str, str]
    sync_interval_minutes: int
    sync_enabled: bool
    is_active: bool
    last_sync_at: datetime | None = None
    last_sync_status: str | None = None
    last_sync_records: int = 0
    created_at: datetime
    updated_at: datetime | None = None

    class Config:
        from_attributes = True


class DataSourceListOut(BaseModel):
    sources: list[DataSourceOut]
    total_count: int


class SyncTriggerRequest(BaseModel):
    full_sync: bool = True
    since: datetime | None = None


class ScheduleUpdateRequest(BaseModel):
    sync_interval_minutes: int = Field(ge=5, le=1440, default=60)
    sync_enabled: bool = True


class SyncLogOut(BaseModel):
    id: UUID
    tenant_id: UUID
    data_source_id: UUID | None
    sync_type: str
    direction: str
    status: str
    records_fetched: int
    records_created: int
    records_updated: int
    records_skipped: int
    records_failed: int
    started_at: datetime
    completed_at: datetime | None
    duration_seconds: float | None
    error_message: str | None
    errors: list[str]
    details: dict[str, Any]
    triggered_by: str
    created_at: datetime

    class Config:
        from_attributes = True


class SyncHistoryOut(BaseModel):
    logs: list[SyncLogOut]
    total_count: int


class SyncStatusOut(BaseModel):
    source_id: UUID
    source_name: str
    source_type: str
    is_active: bool
    last_sync_at: datetime | None
    last_sync_status: str | None
    last_sync_records: int
    recent_logs: list[SyncLogOut]
    connector_info: dict[str, Any]


class ConnectorInfoOut(BaseModel):
    name: str
    display_name: str
    supports_invoices: bool
    supports_payments: bool
    supports_customers: bool
    supports_products: bool
    sync_direction: str


# ════════════════════════════════════════════════════════════════════
#  Helpers
# ════════════════════════════════════════════════════════════════════

def _get_connector_for_source(ds: DataSourceConnectionModel):
    """Instantiate the correct IERPConnector for a data source."""
    cfg = ds.connection_config or {}
    source_type = ds.source_type

    if source_type == "mongodb":
        from src.infrastructure.connectors.erp.mongodb_adapter import MongoDBERPAdapter
        url = cfg.get("url", "mongodb://localhost:27017")
        database = cfg.get("database", "funnelier_tenant")
        return MongoDBERPAdapter(url=url, database=database)

    if source_type == "odoo":
        from src.infrastructure.connectors.erp.odoo_adapter import OdooERPAdapter
        return OdooERPAdapter(
            url=cfg.get("url", ""),
            db=cfg.get("database", ""),
            username=cfg.get("username", ""),
            password=cfg.get("password", ""),
        )

    # Fallback to mock
    from src.infrastructure.connectors.erp.mock_adapter import MockERPAdapter
    return MockERPAdapter()


async def _get_session():
    """Get an async DB session."""
    factory = get_session_factory()
    async with factory() as session:
        yield session


# ════════════════════════════════════════════════════════════════════
#  Data Source CRUD
# ════════════════════════════════════════════════════════════════════

@router.get("/connectors", response_model=list[ConnectorInfoOut])
async def list_available_connectors():
    """List available ERP/CRM connector types."""
    from src.infrastructure.connectors.erp.registry import ERPConnectorRegistry
    connectors = []
    for name in ERPConnectorRegistry.available():
        try:
            from src.infrastructure.connectors.erp.registry import _CONNECTORS
            cls = _CONNECTORS.get(name)
            if cls:
                inst = cls() if name == "mock" else None
                if inst:
                    info = inst.get_info()
                    connectors.append(ConnectorInfoOut(
                        name=info.name,
                        display_name=info.display_name,
                        supports_invoices=info.supports_invoices,
                        supports_payments=info.supports_payments,
                        supports_customers=info.supports_customers,
                        supports_products=info.supports_products,
                        sync_direction=info.sync_direction.value,
                    ))
                else:
                    connectors.append(ConnectorInfoOut(
                        name=name,
                        display_name=name.title(),
                        supports_invoices=True,
                        supports_payments=True,
                        supports_customers=True,
                        supports_products=False,
                        sync_direction="pull",
                    ))
        except Exception:
            connectors.append(ConnectorInfoOut(
                name=name,
                display_name=name.title(),
                supports_invoices=True,
                supports_payments=True,
                supports_customers=True,
                supports_products=False,
                sync_direction="pull",
            ))
    return connectors


@router.get("/sources", response_model=DataSourceListOut)
async def list_data_sources(
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
    session: AsyncSession = Depends(_get_session),
):
    """List all configured ERP/CRM data sources."""
    stmt = (
        select(DataSourceConnectionModel)
        .where(DataSourceConnectionModel.tenant_id == tenant_id)
        .order_by(DataSourceConnectionModel.created_at.desc())
    )
    result = await session.execute(stmt)
    models = result.scalars().all()

    sources = []
    for m in models:
        # Mask sensitive fields in connection_config
        safe_config = {**m.connection_config}
        if "password" in safe_config:
            safe_config["password"] = "***"
        sources.append(DataSourceOut(
            id=m.id,
            tenant_id=m.tenant_id,
            name=m.name,
            source_type=m.source_type,
            connection_config=safe_config,
            field_mappings=m.field_mappings or {},
            sync_interval_minutes=m.sync_interval_minutes,
            sync_enabled=m.sync_enabled,
            is_active=m.is_active,
            last_sync_at=m.last_sync_at,
            last_sync_status=m.last_sync_status,
            last_sync_records=m.last_sync_records,
            created_at=m.created_at,
            updated_at=m.updated_at,
        ))

    count_stmt = (
        select(func.count())
        .select_from(DataSourceConnectionModel)
        .where(DataSourceConnectionModel.tenant_id == tenant_id)
    )
    count_result = await session.execute(count_stmt)
    total = count_result.scalar_one()

    return DataSourceListOut(sources=sources, total_count=total)


@router.post("/sources", response_model=DataSourceOut, status_code=201)
async def create_data_source(
    request: DataSourceCreate,
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
    session: AsyncSession = Depends(_get_session),
):
    """Create a new ERP/CRM data source configuration."""
    model = DataSourceConnectionModel(
        id=uuid4(),
        tenant_id=tenant_id,
        name=request.name,
        source_type=request.source_type,
        connection_config=request.connection_config,
        field_mappings=request.field_mappings,
        sync_interval_minutes=request.sync_interval_minutes,
        sync_enabled=request.is_active,
        is_active=request.is_active,
        metadata_={"description": request.description} if request.description else {},
    )
    session.add(model)
    await session.commit()
    await session.refresh(model)

    return DataSourceOut(
        id=model.id,
        tenant_id=model.tenant_id,
        name=model.name,
        source_type=model.source_type,
        connection_config=model.connection_config,
        field_mappings=model.field_mappings or {},
        sync_interval_minutes=model.sync_interval_minutes,
        sync_enabled=model.sync_enabled,
        is_active=model.is_active,
        last_sync_at=model.last_sync_at,
        last_sync_status=model.last_sync_status,
        last_sync_records=model.last_sync_records,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


@router.get("/sources/{source_id}", response_model=DataSourceOut)
async def get_data_source(
    source_id: UUID,
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
    session: AsyncSession = Depends(_get_session),
):
    """Get a data source by ID."""
    stmt = select(DataSourceConnectionModel).where(
        DataSourceConnectionModel.id == source_id,
        DataSourceConnectionModel.tenant_id == tenant_id,
    )
    result = await session.execute(stmt)
    model = result.scalar_one_or_none()
    if not model:
        raise HTTPException(status_code=404, detail="Data source not found")

    return DataSourceOut(
        id=model.id,
        tenant_id=model.tenant_id,
        name=model.name,
        source_type=model.source_type,
        connection_config=model.connection_config,
        field_mappings=model.field_mappings or {},
        sync_interval_minutes=model.sync_interval_minutes,
        sync_enabled=model.sync_enabled,
        is_active=model.is_active,
        last_sync_at=model.last_sync_at,
        last_sync_status=model.last_sync_status,
        last_sync_records=model.last_sync_records,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


@router.put("/sources/{source_id}", response_model=DataSourceOut)
async def update_data_source(
    source_id: UUID,
    request: DataSourceUpdate,
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
    session: AsyncSession = Depends(_get_session),
):
    """Update a data source configuration."""
    stmt = select(DataSourceConnectionModel).where(
        DataSourceConnectionModel.id == source_id,
        DataSourceConnectionModel.tenant_id == tenant_id,
    )
    result = await session.execute(stmt)
    model = result.scalar_one_or_none()
    if not model:
        raise HTTPException(status_code=404, detail="Data source not found")

    updates = request.model_dump(exclude_unset=True)
    for key, value in updates.items():
        if key == "is_active":
            model.is_active = value
            model.sync_enabled = value
        elif key == "description":
            model.metadata_ = {**(model.metadata_ or {}), "description": value}
        elif hasattr(model, key):
            setattr(model, key, value)

    await session.commit()
    await session.refresh(model)

    return DataSourceOut(
        id=model.id,
        tenant_id=model.tenant_id,
        name=model.name,
        source_type=model.source_type,
        connection_config=model.connection_config,
        field_mappings=model.field_mappings or {},
        sync_interval_minutes=model.sync_interval_minutes,
        sync_enabled=model.sync_enabled,
        is_active=model.is_active,
        last_sync_at=model.last_sync_at,
        last_sync_status=model.last_sync_status,
        last_sync_records=model.last_sync_records,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


@router.delete("/sources/{source_id}", status_code=204)
async def delete_data_source(
    source_id: UUID,
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
    session: AsyncSession = Depends(_get_session),
):
    """Delete a data source."""
    stmt = select(DataSourceConnectionModel).where(
        DataSourceConnectionModel.id == source_id,
        DataSourceConnectionModel.tenant_id == tenant_id,
    )
    result = await session.execute(stmt)
    model = result.scalar_one_or_none()
    if not model:
        raise HTTPException(status_code=404, detail="Data source not found")

    await session.delete(model)
    await session.commit()


# ════════════════════════════════════════════════════════════════════
#  Connection Test
# ════════════════════════════════════════════════════════════════════

@router.post("/sources/{source_id}/test", response_model=dict)
async def test_connection(
    source_id: UUID,
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
    session: AsyncSession = Depends(_get_session),
):
    """Test connectivity to the configured ERP/CRM."""
    stmt = select(DataSourceConnectionModel).where(
        DataSourceConnectionModel.id == source_id,
        DataSourceConnectionModel.tenant_id == tenant_id,
    )
    result = await session.execute(stmt)
    ds = result.scalar_one_or_none()
    if not ds:
        raise HTTPException(status_code=404, detail="Data source not found")

    connector = _get_connector_for_source(ds)
    try:
        success, message = await connector.test_connection()
        info = connector.get_info()
        return {
            "success": success,
            "message": message,
            "connector": {
                "name": info.name,
                "display_name": info.display_name,
                "supports_invoices": info.supports_invoices,
                "supports_payments": info.supports_payments,
                "supports_customers": info.supports_customers,
            },
        }
    except Exception as exc:
        return {"success": False, "message": str(exc)}
    finally:
        try:
            await connector.disconnect()
        except Exception:
            pass


# ════════════════════════════════════════════════════════════════════
#  Trigger Sync
# ════════════════════════════════════════════════════════════════════

@router.post("/sources/{source_id}/sync", response_model=dict)
async def trigger_sync(
    source_id: UUID,
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
    request: SyncTriggerRequest | None = None,
    session: AsyncSession = Depends(_get_session),
):
    """Trigger a data sync from an ERP/CRM data source."""
    stmt = select(DataSourceConnectionModel).where(
        DataSourceConnectionModel.id == source_id,
        DataSourceConnectionModel.tenant_id == tenant_id,
    )
    result = await session.execute(stmt)
    ds = result.scalar_one_or_none()
    if not ds:
        raise HTTPException(status_code=404, detail="Data source not found")

    connector = _get_connector_for_source(ds)

    from src.modules.sales.infrastructure.erp_sync_service import ERPSyncService

    svc = ERPSyncService(
        connector=connector,
        session=session,
        tenant_id=tenant_id,
        source_system=ds.source_type,
        data_source_id=ds.id,
    )

    since = None
    if request and not request.full_sync and request.since:
        since = request.since
    elif not (request and request.full_sync) and ds.last_sync_at:
        since = ds.last_sync_at

    sync_result = await svc.full_sync(
        since=since,
        triggered_by="manual",
    )

    # Update data source last sync info
    ds.last_sync_at = datetime.now(timezone.utc)
    ds.last_sync_status = "success" if sync_result.success else "failed"
    ds.last_sync_records = sync_result.records_synced

    await session.commit()

    return {
        "success": sync_result.success,
        "records_synced": sync_result.records_synced,
        "records_created": sync_result.records_created,
        "records_updated": sync_result.records_updated,
        "records_failed": sync_result.records_failed,
        "errors": sync_result.errors,
        "duration_seconds": sync_result.duration_seconds,
        "details": sync_result.metadata,
    }


# ════════════════════════════════════════════════════════════════════
#  Sync History
# ════════════════════════════════════════════════════════════════════

@router.get("/sync-history", response_model=SyncHistoryOut)
async def get_sync_history(
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
    source_id: UUID | None = Query(default=None),
    status: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(_get_session),
):
    """Get sync operation history."""
    stmt = (
        select(SyncLogModel)
        .where(SyncLogModel.tenant_id == tenant_id)
        .order_by(SyncLogModel.started_at.desc())
    )
    if source_id:
        stmt = stmt.where(SyncLogModel.data_source_id == source_id)
    if status:
        stmt = stmt.where(SyncLogModel.status == status)

    # Count
    count_stmt = (
        select(func.count())
        .select_from(SyncLogModel)
        .where(SyncLogModel.tenant_id == tenant_id)
    )
    if source_id:
        count_stmt = count_stmt.where(SyncLogModel.data_source_id == source_id)
    if status:
        count_stmt = count_stmt.where(SyncLogModel.status == status)
    count_result = await session.execute(count_stmt)
    total = count_result.scalar_one()

    # Paginate
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    result = await session.execute(stmt)
    logs = result.scalars().all()

    return SyncHistoryOut(
        logs=[
            SyncLogOut(
                id=log.id,
                tenant_id=log.tenant_id,
                data_source_id=log.data_source_id,
                sync_type=log.sync_type,
                direction=log.direction,
                status=log.status,
                records_fetched=log.records_fetched,
                records_created=log.records_created,
                records_updated=log.records_updated,
                records_skipped=log.records_skipped,
                records_failed=log.records_failed,
                started_at=log.started_at,
                completed_at=log.completed_at,
                duration_seconds=log.duration_seconds,
                error_message=log.error_message,
                errors=log.errors or [],
                details=log.details or {},
                triggered_by=log.triggered_by,
                created_at=log.created_at,
            )
            for log in logs
        ],
        total_count=total,
    )


@router.get("/sources/{source_id}/status", response_model=SyncStatusOut)
async def get_source_sync_status(
    source_id: UUID,
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
    session: AsyncSession = Depends(_get_session),
):
    """Get detailed sync status for a data source."""
    stmt = select(DataSourceConnectionModel).where(
        DataSourceConnectionModel.id == source_id,
        DataSourceConnectionModel.tenant_id == tenant_id,
    )
    result = await session.execute(stmt)
    ds = result.scalar_one_or_none()
    if not ds:
        raise HTTPException(status_code=404, detail="Data source not found")

    # Get recent sync logs
    logs_stmt = (
        select(SyncLogModel)
        .where(
            SyncLogModel.data_source_id == source_id,
            SyncLogModel.tenant_id == tenant_id,
        )
        .order_by(SyncLogModel.started_at.desc())
        .limit(5)
    )
    logs_result = await session.execute(logs_stmt)
    recent_logs = logs_result.scalars().all()

    # Get connector info
    connector = _get_connector_for_source(ds)
    info = connector.get_info()

    return SyncStatusOut(
        source_id=ds.id,
        source_name=ds.name,
        source_type=ds.source_type,
        is_active=ds.is_active,
        last_sync_at=ds.last_sync_at,
        last_sync_status=ds.last_sync_status,
        last_sync_records=ds.last_sync_records,
        recent_logs=[
            SyncLogOut(
                id=log.id,
                tenant_id=log.tenant_id,
                data_source_id=log.data_source_id,
                sync_type=log.sync_type,
                direction=log.direction,
                status=log.status,
                records_fetched=log.records_fetched,
                records_created=log.records_created,
                records_updated=log.records_updated,
                records_skipped=log.records_skipped,
                records_failed=log.records_failed,
                started_at=log.started_at,
                completed_at=log.completed_at,
                duration_seconds=log.duration_seconds,
                error_message=log.error_message,
                errors=log.errors or [],
                details=log.details or {},
                triggered_by=log.triggered_by,
                created_at=log.created_at,
            )
            for log in recent_logs
        ],
        connector_info={
            "name": info.name,
            "display_name": info.display_name,
            "supports_invoices": info.supports_invoices,
            "supports_payments": info.supports_payments,
            "supports_customers": info.supports_customers,
            "supports_products": info.supports_products,
            "sync_direction": info.sync_direction.value,
        },
    )


# ════════════════════════════════════════════════════════════════════
#  Quick sync (no data source registration needed)
# ════════════════════════════════════════════════════════════════════

@router.post("/quick-sync", response_model=dict)
async def quick_sync(
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
    provider: str = Query(default="mock"),
    session: AsyncSession = Depends(_get_session),
):
    """
    Quick sync using the globally configured ERP provider.
    Uses ERPConnectorRegistry (no data-source config needed).
    """
    from src.infrastructure.connectors.erp.registry import ERPConnectorRegistry
    from src.modules.sales.infrastructure.erp_sync_service import ERPSyncService

    connector = ERPConnectorRegistry.get()
    svc = ERPSyncService(
        connector=connector,
        session=session,
        tenant_id=tenant_id,
        source_system=provider,
    )

    sync_result = await svc.full_sync(triggered_by="manual")
    await session.commit()

    return {
        "success": sync_result.success,
        "records_synced": sync_result.records_synced,
        "records_created": sync_result.records_created,
        "records_updated": sync_result.records_updated,
        "records_failed": sync_result.records_failed,
        "errors": sync_result.errors,
        "duration_seconds": sync_result.duration_seconds,
        "details": sync_result.metadata,
    }


# ════════════════════════════════════════════════════════════════════
#  Schedule Management
# ════════════════════════════════════════════════════════════════════

@router.put("/sources/{source_id}/schedule", response_model=DataSourceOut)
async def update_sync_schedule(
    source_id: UUID,
    request: ScheduleUpdateRequest,
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
    session: AsyncSession = Depends(_get_session),
):
    """Update the automatic sync schedule for a data source."""
    stmt = select(DataSourceConnectionModel).where(
        DataSourceConnectionModel.id == source_id,
        DataSourceConnectionModel.tenant_id == tenant_id,
    )
    result = await session.execute(stmt)
    model = result.scalar_one_or_none()
    if not model:
        raise HTTPException(status_code=404, detail="Data source not found")

    model.sync_interval_minutes = request.sync_interval_minutes
    model.sync_enabled = request.sync_enabled

    await session.commit()
    await session.refresh(model)

    return DataSourceOut(
        id=model.id,
        tenant_id=model.tenant_id,
        name=model.name,
        source_type=model.source_type,
        connection_config=model.connection_config,
        field_mappings=model.field_mappings or {},
        sync_interval_minutes=model.sync_interval_minutes,
        sync_enabled=model.sync_enabled,
        is_active=model.is_active,
        last_sync_at=model.last_sync_at,
        last_sync_status=model.last_sync_status,
        last_sync_records=model.last_sync_records,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


@router.get("/dedup-strategies", response_model=list)
async def list_dedup_strategies():
    """List available deduplication strategies for data sync."""
    return {
        "strategies": [
            {
                "name": "external_id",
                "display_name": "External ID Match",
                "description": "Match records by their external system ID. Creates new if not found, updates if exists.",
                "is_default": True,
            },
            {
                "name": "phone_number",
                "display_name": "Phone Number Match",
                "description": "Match contacts by phone number. Merges data if existing contact found.",
                "is_default": False,
            },
            {
                "name": "invoice_number",
                "display_name": "Invoice Number Match",
                "description": "Match invoices by invoice number. Useful when external_id changes across systems.",
                "is_default": False,
            },
            {
                "name": "skip_existing",
                "display_name": "Skip Existing",
                "description": "Only create new records. Skip any record that already exists in the database.",
                "is_default": False,
            },
        ],
    }

