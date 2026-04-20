"""
Multi-tenant Onboarding Service.

Orchestrates new tenant provisioning:
1. Create tenant record in DB
2. Create admin user for the tenant
3. Seed default settings (funnel stages, RFM config)
4. Set plan limits based on selected plan
"""

import logging
import re
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.tenants.domain.entities import Tenant
from src.modules.tenants.infrastructure.repositories import TenantRepository
from src.modules.tenants.application.billing_service import PLAN_CATALOGUE

logger = logging.getLogger(__name__)


# ── Onboarding Request/Response Schemas ──────────────────


class OnboardingStep1(BaseModel):
    """Company information."""
    company_name: str = Field(..., min_length=2, max_length=255)
    slug: str = Field(..., min_length=2, max_length=100, pattern=r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?$")
    industry: str = "building_materials"
    company_size: str = "small"  # small, medium, large, enterprise
    phone: str | None = None
    email: str | None = None
    description: str | None = None

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, v: str) -> str:
        if not re.match(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?$", v):
            raise ValueError("Slug must be lowercase alphanumeric with hyphens only")
        return v


class OnboardingStep2(BaseModel):
    """Plan selection."""
    plan: str = "basic"  # free, basic, professional, enterprise

    @field_validator("plan")
    @classmethod
    def validate_plan(cls, v: str) -> str:
        valid_plans = {p.name for p in PLAN_CATALOGUE}
        if v not in valid_plans:
            raise ValueError(f"Invalid plan. Choose from: {', '.join(sorted(valid_plans))}")
        return v


class OnboardingStep3(BaseModel):
    """Admin user details."""
    admin_username: str = Field(..., min_length=3, max_length=100)
    admin_email: str = Field(..., pattern=r"^[^@]+@[^@]+\.[^@]+$")
    admin_password: str = Field(..., min_length=8)
    admin_full_name: str = Field(..., min_length=2, max_length=255)


class OnboardingStep4(BaseModel):
    """Optional data source configuration."""
    data_sources: list[dict[str, Any]] = Field(default_factory=list)
    sms_provider: str | None = None
    sms_api_key: str | None = None
    voip_provider: str | None = None


class OnboardingRequest(BaseModel):
    """Complete onboarding request (all steps combined)."""
    # Step 1: Company
    company_name: str = Field(..., min_length=2, max_length=255)
    slug: str = Field(..., min_length=2, max_length=100)
    industry: str = "building_materials"
    company_size: str = "small"
    phone: str | None = None
    email: str | None = None
    description: str | None = None

    # Step 2: Plan
    plan: str = "basic"

    # Step 3: Admin
    admin_username: str = Field(..., min_length=3, max_length=100)
    admin_email: str
    admin_password: str = Field(..., min_length=8)
    admin_full_name: str = Field(..., min_length=2, max_length=255)

    # Step 4: Optional data sources
    sms_provider: str | None = None
    sms_api_key: str | None = None

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, v: str) -> str:
        if not re.match(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?$", v):
            raise ValueError("Slug must be lowercase alphanumeric with hyphens only")
        return v


class OnboardingResponse(BaseModel):
    """Onboarding result."""
    tenant_id: UUID
    tenant_name: str
    slug: str
    plan: str
    admin_user_id: UUID
    admin_username: str
    access_token: str
    refresh_token: str
    message: str = "Tenant created successfully"


# ── Default Settings ─────────────────────────────────


DEFAULT_FUNNEL_STAGES = [
    {"id": "lead_acquired", "name": "Lead Acquired", "name_fa": "سرنخ جدید", "order": 1, "color": "#3B82F6"},
    {"id": "sms_sent", "name": "SMS Sent", "name_fa": "پیامک ارسال شده", "order": 2, "color": "#8B5CF6"},
    {"id": "sms_delivered", "name": "SMS Delivered", "name_fa": "پیامک تحویل شده", "order": 3, "color": "#A855F7"},
    {"id": "call_attempted", "name": "Call Attempted", "name_fa": "تماس گرفته شده", "order": 4, "color": "#F59E0B"},
    {"id": "call_answered", "name": "Call Answered", "name_fa": "تماس پاسخ داده شده", "order": 5, "color": "#10B981"},
    {"id": "invoice_issued", "name": "Invoice Issued", "name_fa": "پیش‌فاکتور صادر شده", "order": 6, "color": "#06B6D4"},
    {"id": "payment_received", "name": "Payment Received", "name_fa": "پرداخت دریافت شده", "order": 7, "color": "#22C55E", "is_conversion": True},
]

DEFAULT_RFM_SETTINGS = {
    "recency_thresholds": [7, 14, 30, 60, 90],
    "frequency_thresholds": [1, 2, 4, 8, 16],
    "monetary_thresholds": [100_000_000, 500_000_000, 1_000_000_000, 2_000_000_000, 5_000_000_000],
    "analysis_period_months": 12,
    "high_value_threshold": 1_000_000_000,
    "recent_days": 14,
}


def _get_plan_limits(plan_name: str) -> dict[str, Any]:
    """Get plan limits from the billing catalogue."""
    for plan in PLAN_CATALOGUE:
        if plan.name == plan_name:
            return {
                "max_contacts": plan.limits.max_contacts,
                "max_sms_per_month": plan.limits.max_sms_per_month,
                "max_users": plan.limits.max_users,
            }
    # Fallback to basic
    return {"max_contacts": 5000, "max_sms_per_month": 5000, "max_users": 10}


# ── Onboarding Service ───────────────────────────────


class OnboardingService:
    """
    Orchestrates complete tenant onboarding in a single transaction.
    """

    def __init__(self, session: AsyncSession):
        self._session = session
        self._tenant_repo = TenantRepository(session)

    async def check_slug_available(self, slug: str) -> bool:
        """Check if a slug is available."""
        return not await self._tenant_repo.slug_exists(slug)

    async def onboard(self, request: OnboardingRequest) -> OnboardingResponse:
        """
        Execute full onboarding flow:
        1. Validate slug uniqueness
        2. Create tenant with plan limits
        3. Create admin user
        4. Generate auth tokens
        5. Seed default settings
        """
        # 1. Check slug uniqueness
        if await self._tenant_repo.slug_exists(request.slug):
            from fastapi import HTTPException
            raise HTTPException(status_code=409, detail="Slug already taken")

        # 2. Determine plan limits
        limits = _get_plan_limits(request.plan)

        # 3. Build default settings
        settings = {
            "funnel_stages": DEFAULT_FUNNEL_STAGES,
            "rfm_settings": DEFAULT_RFM_SETTINGS,
            "industry": request.industry,
            "company_size": request.company_size,
            "sms_settings": {},
        }
        if request.sms_provider:
            settings["sms_settings"] = {
                "provider": request.sms_provider,
                "api_key": request.sms_api_key,
            }

        # 4. Create tenant
        tenant_id = uuid4()
        tenant = Tenant(
            id=tenant_id,
            name=request.company_name,
            slug=request.slug,
            email=request.email,
            phone=request.phone,
            settings=settings,
            plan=request.plan,
            is_active=True,
            trial_ends_at=datetime.utcnow() + timedelta(days=14) if request.plan == "free" else None,
            max_contacts=limits["max_contacts"],
            max_sms_per_month=limits["max_sms_per_month"],
            max_users=limits["max_users"],
        )
        tenant = await self._tenant_repo.create(tenant)

        # 5. Create admin user for this tenant
        from src.modules.auth.domain.entities import User, UserRole
        from src.modules.auth.infrastructure.repositories import UserRepository
        from src.modules.auth.domain.auth_service import hash_password, create_token_pair

        user_repo = UserRepository(self._session, tenant_id)

        admin_user = User(
            id=uuid4(),
            tenant_id=tenant_id,
            email=request.admin_email,
            username=request.admin_username,
            hashed_password=hash_password(request.admin_password),
            full_name=request.admin_full_name,
            role=UserRole.ADMIN,
            is_active=True,
            is_approved=True,
        )
        admin_user = await user_repo.add(admin_user)

        # 6. Generate tokens
        tokens = create_token_pair(
            user_id=admin_user.id,
            tenant_id=tenant_id,
            role=admin_user.role.value,
        )

        logger.info(
            "Tenant onboarded",
            extra={
                "tenant_id": str(tenant_id),
                "slug": request.slug,
                "plan": request.plan,
                "admin_username": request.admin_username,
            },
        )

        return OnboardingResponse(
            tenant_id=tenant_id,
            tenant_name=request.company_name,
            slug=request.slug,
            plan=request.plan,
            admin_user_id=admin_user.id,
            admin_username=admin_user.username,
            access_token=tokens.access_token,
            refresh_token=tokens.refresh_token,
        )


