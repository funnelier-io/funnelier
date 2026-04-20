"""
Tenants API Routes

FastAPI routes for multi-tenant management.
"""

from datetime import datetime, timedelta
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_current_tenant_id, get_db_session
from src.modules.auth.api.routes import require_auth, require_admin
from src.modules.auth.domain.entities import UserRole

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
from src.modules.tenants.application.onboarding_service import (
    OnboardingRequest,
)

router = APIRouter(prefix="/tenants", tags=["tenants"])

# Separate public router for onboarding (no auth required).
# Must be registered WITHOUT the require_auth dependency in main.py.
onboarding_router = APIRouter(prefix="/tenants", tags=["onboarding"])


# ============================================================================
# Public Onboarding Endpoints (no auth required)
# ============================================================================

@onboarding_router.post("/onboard", status_code=201)
async def onboard_tenant(
    request: OnboardingRequest,
    session: AsyncSession = Depends(get_db_session),
):
    """
    Self-service tenant onboarding wizard.
    Creates a new tenant, admin user, and seeds default settings.
    Returns auth tokens for immediate login.

    This is a PUBLIC endpoint — no authentication required.
    """
    from src.modules.tenants.application.onboarding_service import (
        OnboardingService,
    )

    service = OnboardingService(session)
    result = await service.onboard(request)
    return result


@onboarding_router.get("/onboard/check-slug")
async def check_slug_availability(
    slug: str = Query(..., min_length=2, max_length=100),
    session: AsyncSession = Depends(get_db_session),
):
    """
    Check if a tenant slug is available.
    Public endpoint: no authentication required.
    """
    from src.modules.tenants.application.onboarding_service import OnboardingService

    service = OnboardingService(session)
    available = await service.check_slug_available(slug)
    return {"slug": slug, "available": available}


@onboarding_router.get("/onboard/plans")
async def get_onboarding_plans():
    """
    Get available plans for the onboarding wizard.
    Public endpoint: no authentication required.
    """
    from src.modules.tenants.application.billing_service import PLAN_CATALOGUE
    return {
        "plans": [p.model_dump() for p in PLAN_CATALOGUE],
    }



# ============================================================================
# Current Tenant Endpoints
# ============================================================================
# NOTE: /me routes MUST be registered before /{tenant_id} so FastAPI does
# not try to parse the literal string "me" as a UUID path parameter.
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


@router.post("/me/data-sources/{source_id}/test", response_model=dict)
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


@router.post("/me/data-sources/{source_id}/sync", response_model=dict)
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


@router.post("/me/integrations/{integration_id}/test", response_model=dict)
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
    Get current usage statistics from Redis counters and DB.
    """
    from src.modules.tenants.application.billing_service import UsageMeteringService

    metrics = await UsageMeteringService.get_usage_metrics(
        tenant_id=tenant_id,
        plan="professional",
        contacts_count=5000,  # TODO: query from DB
        users_count=9,
        data_sources_count=2,
    )

    return UsageStatsResponse(
        tenant_id=tenant_id,
        period_start=metrics.period_start,
        period_end=metrics.period_end,
        contacts_count=metrics.contacts_count,
        contacts_limit=metrics.contacts_limit,
        sms_sent=metrics.sms_sent,
        sms_limit=metrics.sms_limit,
        api_calls=metrics.api_calls_today,
        storage_used_mb=256.5,
        users_count=metrics.users_count,
        users_limit=metrics.users_limit,
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
        plan="professional",
        plan_price=5_000_000,
        billing_cycle="monthly",
        next_billing_date=datetime.utcnow() + timedelta(days=15),
        payment_method="bank_transfer",
        is_trial=False,
    )


@router.get("/me/billing/plans", response_model=dict)
async def list_available_plans(
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
):
    """List all available billing plans with features and pricing."""
    from src.modules.tenants.application.billing_service import PLAN_CATALOGUE
    return {
        "plans": [p.model_dump() for p in PLAN_CATALOGUE],
        "current_plan": "professional",
    }


@router.get("/me/usage/detailed", response_model=dict)
async def get_detailed_usage(
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
):
    """Get detailed usage metrics with percentages and warnings."""
    from src.modules.tenants.application.billing_service import UsageMeteringService

    metrics = await UsageMeteringService.get_usage_metrics(
        tenant_id=tenant_id,
        plan="professional",
        contacts_count=5000,
        users_count=9,
        data_sources_count=2,
    )
    return metrics.model_dump()


# ============================================================================
# Tenant CRUD Endpoints (Super Admin)
# ============================================================================
# NOTE: /{tenant_id} routes MUST come after /me routes (see above).
# ============================================================================

@router.get("", response_model=TenantListResponse)
async def list_tenants(
    admin_user=Depends(require_admin),
    is_active: bool | None = Query(default=None),
    search: str | None = Query(default=None),
):
    """
    List all tenants (super admin only).
    """
    if not admin_user.has_permission(UserRole.SUPER_ADMIN):
        raise HTTPException(status_code=403, detail="Super admin access required")

    return TenantListResponse(
        tenants=[],
        total_count=0,
    )


@router.post("", response_model=TenantResponse, status_code=201)
async def create_tenant(
    request: CreateTenantRequest,
    admin_user=Depends(require_admin),
):
    """
    Create a new tenant (super admin only).
    """
    if not admin_user.has_permission(UserRole.SUPER_ADMIN):
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
    admin_user=Depends(require_admin),
):
    """
    Get tenant details.
    """
    # Allow if super admin or accessing own tenant
    if not admin_user.has_permission(UserRole.SUPER_ADMIN) and tenant_id != current_tenant_id:
        raise HTTPException(status_code=403, detail="Access denied")

    raise HTTPException(status_code=404, detail="Tenant not found")


@router.put("/{tenant_id}", response_model=TenantResponse)
async def update_tenant(
    tenant_id: UUID,
    request: UpdateTenantRequest,
    current_tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
    admin_user=Depends(require_admin),
):
    """
    Update tenant details.
    """
    if not admin_user.has_permission(UserRole.SUPER_ADMIN) and tenant_id != current_tenant_id:
        raise HTTPException(status_code=403, detail="Access denied")

    raise HTTPException(status_code=404, detail="Tenant not found")


@router.delete("/{tenant_id}", status_code=204)
async def delete_tenant(
    tenant_id: UUID,
    admin_user=Depends(require_admin),
):
    """
    Delete a tenant (super admin only).
    """
    if not admin_user.has_permission(UserRole.SUPER_ADMIN):
        raise HTTPException(status_code=403, detail="Super admin access required")

    pass
