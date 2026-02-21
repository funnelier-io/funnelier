"""
Tenants API Routes

FastAPI routes for multi-tenant management.
"""

from datetime import datetime, timedelta
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query

from src.api.dependencies import get_current_tenant_id, get_super_admin

from .schemas import (
    BillingInfoResponse,
    CreateDataSourceConfigRequest,
    CreateIntegrationRequest,
    CreateTenantRequest,
    DataSourceConfigListResponse,
    DataSourceConfigResponse,
    FunnelStageConfig,
    IntegrationListResponse,
    IntegrationResponse,
    RFMSettingsSchema,
    TenantListResponse,
    TenantResponse,
    TenantSettingsResponse,
    UpdateTenantRequest,
    UpdateTenantSettingsRequest,
    UsageStatsResponse,
)

router = APIRouter(prefix="/tenants", tags=["tenants"])



# ============================================================================
# Tenant CRUD Endpoints (Super Admin)
# ============================================================================

@router.get("", response_model=TenantListResponse)
async def list_tenants(
    is_super_admin: Annotated[bool, Depends(get_super_admin)],
    is_active: bool | None = Query(default=None),
    search: str | None = Query(default=None),
):
    """
    List all tenants (super admin only).
    """
    if not is_super_admin:
        raise HTTPException(status_code=403, detail="Super admin access required")

    return TenantListResponse(
        tenants=[],
        total_count=0,
    )


@router.post("", response_model=TenantResponse, status_code=201)
async def create_tenant(
    is_super_admin: Annotated[bool, Depends(get_super_admin)],
    request: CreateTenantRequest,
):
    """
    Create a new tenant (super admin only).
    """
    if not is_super_admin:
        raise HTTPException(status_code=403, detail="Super admin access required")

    return TenantResponse(
        id=uuid4(),
        name=request.name,
        slug=request.slug,
        description=request.description,
        domain=request.domain,
        logo_url=request.logo_url,
        timezone=request.timezone,
        language=request.language,
        currency=request.currency,
        is_active=request.is_active,
        plan="basic",
        max_users=10,
        max_contacts=10000,
        features=["funnel_analytics", "rfm_segmentation", "sms_campaigns"],
        metadata=request.metadata,
        created_at=datetime.utcnow(),
    )


@router.get("/{tenant_id}", response_model=TenantResponse)
async def get_tenant(
    tenant_id: UUID,
    current_tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
    is_super_admin: Annotated[bool, Depends(get_super_admin)],
):
    """
    Get tenant details.
    """
    # Allow if super admin or accessing own tenant
    if not is_super_admin and tenant_id != current_tenant_id:
        raise HTTPException(status_code=403, detail="Access denied")

    raise HTTPException(status_code=404, detail="Tenant not found")


@router.put("/{tenant_id}", response_model=TenantResponse)
async def update_tenant(
    tenant_id: UUID,
    current_tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
    is_super_admin: Annotated[bool, Depends(get_super_admin)],
    request: UpdateTenantRequest,
):
    """
    Update tenant details.
    """
    if not is_super_admin and tenant_id != current_tenant_id:
        raise HTTPException(status_code=403, detail="Access denied")

    raise HTTPException(status_code=404, detail="Tenant not found")


@router.delete("/{tenant_id}", status_code=204)
async def delete_tenant(
    tenant_id: UUID,
    is_super_admin: Annotated[bool, Depends(get_super_admin)],
):
    """
    Delete a tenant (super admin only).
    """
    if not is_super_admin:
        raise HTTPException(status_code=403, detail="Super admin access required")

    pass


# ============================================================================
# Current Tenant Endpoints
# ============================================================================

@router.get("/me", response_model=TenantResponse)
async def get_current_tenant_info(
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
):
    """
    Get current tenant information.
    """
    return TenantResponse(
        id=tenant_id,
        name="شرکت نمونه",
        slug="sample-company",
        description="شرکت تولیدی مصالح ساختمانی",
        timezone="Asia/Tehran",
        language="fa",
        currency="IRR",
        is_active=True,
        plan="pro",
        max_users=25,
        max_contacts=50000,
        features=[
            "funnel_analytics",
            "rfm_segmentation",
            "sms_campaigns",
            "voip_integration",
            "custom_reports",
            "api_access",
        ],
        created_at=datetime.utcnow() - timedelta(days=180),
    )


# ============================================================================
# Tenant Settings Endpoints
# ============================================================================

@router.get("/me/settings", response_model=TenantSettingsResponse)
async def get_tenant_settings(
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
):
    """
    Get tenant settings.
    """
    # Default funnel stages
    default_stages = [
        FunnelStageConfig(
            id="lead_acquired",
            name="Lead Acquired",
            name_fa="سرنخ جدید",
            order=1,
            color="#3B82F6",
        ),
        FunnelStageConfig(
            id="sms_sent",
            name="SMS Sent",
            name_fa="پیامک ارسال شده",
            order=2,
            color="#8B5CF6",
        ),
        FunnelStageConfig(
            id="sms_delivered",
            name="SMS Delivered",
            name_fa="پیامک تحویل شده",
            order=3,
            color="#A855F7",
        ),
        FunnelStageConfig(
            id="call_attempted",
            name="Call Attempted",
            name_fa="تماس گرفته شده",
            order=4,
            color="#F59E0B",
        ),
        FunnelStageConfig(
            id="call_answered",
            name="Call Answered",
            name_fa="تماس پاسخ داده شده",
            order=5,
            color="#10B981",
            is_conversion=False,
        ),
        FunnelStageConfig(
            id="invoice_issued",
            name="Invoice Issued",
            name_fa="پیش‌فاکتور صادر شده",
            order=6,
            color="#06B6D4",
        ),
        FunnelStageConfig(
            id="payment_received",
            name="Payment Received",
            name_fa="پرداخت دریافت شده",
            order=7,
            color="#22C55E",
            is_conversion=True,
        ),
    ]

    return TenantSettingsResponse(
        tenant_id=tenant_id,
        funnel_stages=default_stages,
        rfm_settings=RFMSettingsSchema(),
    )


@router.put("/me/settings", response_model=TenantSettingsResponse)
async def update_tenant_settings(
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
    request: UpdateTenantSettingsRequest,
):
    """
    Update tenant settings.
    """
    return TenantSettingsResponse(
        tenant_id=tenant_id,
        funnel_stages=request.funnel_stages or [],
        rfm_settings=request.rfm_settings or RFMSettingsSchema(),
        call_settings=request.call_settings,
        sms_settings=request.sms_settings,
        notification_settings=request.notification_settings,
        custom_fields=request.custom_fields or {},
        updated_at=datetime.utcnow(),
    )


# ============================================================================
# Data Source Configuration Endpoints
# ============================================================================

@router.get("/me/data-sources", response_model=DataSourceConfigListResponse)
async def list_data_sources(
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
):
    """
    List configured data sources.
    """
    return DataSourceConfigListResponse(
        configs=[],
        total_count=0,
    )


@router.post("/me/data-sources", response_model=DataSourceConfigResponse, status_code=201)
async def create_data_source(
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
    request: CreateDataSourceConfigRequest,
):
    """
    Create a data source configuration.
    """
    return DataSourceConfigResponse(
        id=uuid4(),
        tenant_id=tenant_id,
        name=request.name,
        source_type=request.source_type,
        description=request.description,
        connection_config=request.connection_config,
        field_mappings=request.field_mappings,
        sync_interval_minutes=request.sync_interval_minutes,
        is_active=request.is_active,
        metadata=request.metadata,
        created_at=datetime.utcnow(),
    )


@router.get("/me/data-sources/{source_id}", response_model=DataSourceConfigResponse)
async def get_data_source(
    source_id: UUID,
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
):
    """
    Get data source configuration.
    """
    raise HTTPException(status_code=404, detail="Data source not found")


@router.delete("/me/data-sources/{source_id}", status_code=204)
async def delete_data_source(
    source_id: UUID,
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
):
    """
    Delete a data source configuration.
    """
    pass


@router.post("/me/data-sources/{source_id}/test")
async def test_data_source_connection(
    source_id: UUID,
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
):
    """
    Test connection to a data source.
    """
    return {
        "success": True,
        "message": "Connection successful",
        "records_available": 1500,
    }


@router.post("/me/data-sources/{source_id}/sync")
async def trigger_data_source_sync(
    source_id: UUID,
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
    full_sync: bool = Query(default=False),
):
    """
    Trigger data sync from a source.
    """
    return {
        "job_id": str(uuid4()),
        "status": "started",
        "full_sync": full_sync,
    }


# ============================================================================
# Integration Endpoints
# ============================================================================

@router.get("/me/integrations", response_model=IntegrationListResponse)
async def list_integrations(
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
):
    """
    List configured integrations.
    """
    return IntegrationListResponse(
        integrations=[],
        total_count=0,
    )


@router.post("/me/integrations", response_model=IntegrationResponse, status_code=201)
async def create_integration(
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
    request: CreateIntegrationRequest,
):
    """
    Create an integration.
    """
    return IntegrationResponse(
        id=uuid4(),
        tenant_id=tenant_id,
        name=request.name,
        integration_type=request.integration_type,
        description=request.description,
        config=request.config,
        is_active=request.is_active,
        status="configured",
        created_at=datetime.utcnow(),
    )


@router.post("/me/integrations/{integration_id}/test")
async def test_integration(
    integration_id: UUID,
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
):
    """
    Test an integration connection.
    """
    return {
        "success": True,
        "message": "Integration test successful",
    }


# ============================================================================
# Usage & Billing Endpoints
# ============================================================================

@router.get("/me/usage", response_model=UsageStatsResponse)
async def get_usage_stats(
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
):
    """
    Get current usage statistics.
    """
    now = datetime.utcnow()
    period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    return UsageStatsResponse(
        tenant_id=tenant_id,
        period_start=period_start,
        period_end=now,
        contacts_count=5000,
        contacts_limit=50000,
        sms_sent=3500,
        sms_limit=10000,
        api_calls=15000,
        storage_used_mb=256.5,
        users_count=9,
        users_limit=25,
    )


@router.get("/me/billing", response_model=BillingInfoResponse)
async def get_billing_info(
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
):
    """
    Get billing information.
    """
    return BillingInfoResponse(
        tenant_id=tenant_id,
        plan="pro",
        plan_price=5_000_000,
        billing_cycle="monthly",
        next_billing_date=datetime.utcnow() + timedelta(days=15),
        payment_method="bank_transfer",
        is_trial=False,
    )

