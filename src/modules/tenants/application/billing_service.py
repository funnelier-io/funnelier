"""
Multi-tenant Billing & Usage Metering Service.

Tracks usage (contacts, SMS, API calls) per tenant via Redis counters
and PostgreSQL, enforces plan limits, and manages billing plans.
"""

import logging
import time
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ── Plan Definitions ─────────────────────────────────


class PlanLimits(BaseModel):
    """Resource limits for a billing plan."""
    max_contacts: int
    max_sms_per_month: int
    max_users: int
    max_api_calls_per_day: int
    max_import_size_mb: int
    max_data_sources: int
    features: list[str] = Field(default_factory=list)


# Plan catalogue — extensible via DB later
PLANS: dict[str, PlanLimits] = {
    "free": PlanLimits(
        max_contacts=500,
        max_sms_per_month=100,
        max_users=2,
        max_api_calls_per_day=1_000,
        max_import_size_mb=5,
        max_data_sources=1,
        features=["funnel_analytics", "basic_reports"],
    ),
    "basic": PlanLimits(
        max_contacts=5_000,
        max_sms_per_month=2_000,
        max_users=5,
        max_api_calls_per_day=10_000,
        max_import_size_mb=20,
        max_data_sources=3,
        features=[
            "funnel_analytics", "rfm_segmentation", "sms_campaigns",
            "basic_reports", "csv_export",
        ],
    ),
    "professional": PlanLimits(
        max_contacts=50_000,
        max_sms_per_month=10_000,
        max_users=20,
        max_api_calls_per_day=50_000,
        max_import_size_mb=50,
        max_data_sources=10,
        features=[
            "funnel_analytics", "rfm_segmentation", "sms_campaigns",
            "predictive_analytics", "custom_reports", "pdf_export",
            "csv_export", "api_access", "voip_integration",
            "ab_testing", "retention_analysis",
        ],
    ),
    "enterprise": PlanLimits(
        max_contacts=500_000,
        max_sms_per_month=100_000,
        max_users=100,
        max_api_calls_per_day=500_000,
        max_import_size_mb=200,
        max_data_sources=50,
        features=[
            "funnel_analytics", "rfm_segmentation", "sms_campaigns",
            "predictive_analytics", "custom_reports", "pdf_export",
            "csv_export", "api_access", "voip_integration",
            "ab_testing", "retention_analysis", "custom_integrations",
            "sla_support", "multi_region", "audit_log", "sso",
        ],
    ),
}


def get_plan_limits(plan_name: str) -> PlanLimits:
    """Get limits for a plan. Defaults to 'free' if unknown."""
    return PLANS.get(plan_name, PLANS["free"])


# ── Usage Metering ───────────────────────────────────


class UsageMetrics(BaseModel):
    """Current usage snapshot for a tenant."""
    tenant_id: UUID
    period_start: datetime
    period_end: datetime
    # Counts
    contacts_count: int = 0
    contacts_limit: int = 0
    contacts_percent: float = 0
    sms_sent: int = 0
    sms_limit: int = 0
    sms_percent: float = 0
    api_calls_today: int = 0
    api_calls_limit: int = 0
    api_calls_percent: float = 0
    users_count: int = 0
    users_limit: int = 0
    users_percent: float = 0
    data_sources_count: int = 0
    data_sources_limit: int = 0
    # Plan info
    plan: str = "free"
    plan_features: list[str] = Field(default_factory=list)
    # Warnings
    warnings: list[str] = Field(default_factory=list)


class UsageMeteringService:
    """
    Tracks and enforces usage limits per tenant.

    Uses Redis for fast counters (API calls, SMS) and PostgreSQL for
    durable counts (contacts, users, data sources).
    """

    # ── Redis counter helpers ────────────────────

    @staticmethod
    async def increment_api_calls(tenant_id: UUID) -> int:
        """Increment daily API call counter. Returns new count."""
        try:
            from src.infrastructure.redis_pool import get_redis_pool
            redis = get_redis_pool()
            today = datetime.utcnow().strftime("%Y-%m-%d")
            key = f"usage:api_calls:{tenant_id}:{today}"
            count = await redis.incr(key)
            if count == 1:
                await redis.expire(key, 86400 + 3600)  # TTL 25h
            return count
        except Exception as e:
            logger.warning("Failed to increment API calls: %s", e)
            return 0

    @staticmethod
    async def get_api_calls_today(tenant_id: UUID) -> int:
        """Get today's API call count."""
        try:
            from src.infrastructure.redis_pool import get_redis_pool
            redis = get_redis_pool()
            today = datetime.utcnow().strftime("%Y-%m-%d")
            key = f"usage:api_calls:{tenant_id}:{today}"
            val = await redis.get(key)
            return int(val) if val else 0
        except Exception:
            return 0

    @staticmethod
    async def increment_sms_count(tenant_id: UUID, count: int = 1) -> int:
        """Increment monthly SMS counter."""
        try:
            from src.infrastructure.redis_pool import get_redis_pool
            redis = get_redis_pool()
            month = datetime.utcnow().strftime("%Y-%m")
            key = f"usage:sms:{tenant_id}:{month}"
            new_count = await redis.incrby(key, count)
            if new_count == count:
                await redis.expire(key, 86400 * 35)  # TTL ~35 days
            return new_count
        except Exception as e:
            logger.warning("Failed to increment SMS count: %s", e)
            return 0

    @staticmethod
    async def get_sms_count_month(tenant_id: UUID) -> int:
        """Get current month SMS count."""
        try:
            from src.infrastructure.redis_pool import get_redis_pool
            redis = get_redis_pool()
            month = datetime.utcnow().strftime("%Y-%m")
            key = f"usage:sms:{tenant_id}:{month}"
            val = await redis.get(key)
            return int(val) if val else 0
        except Exception:
            return 0

    # ── Limit Checks ─────────────────────────────

    @staticmethod
    async def check_contacts_limit(tenant_id: UUID, plan: str, current_contacts: int) -> bool:
        """Return True if under limit."""
        limits = get_plan_limits(plan)
        return current_contacts < limits.max_contacts

    @staticmethod
    async def check_sms_limit(tenant_id: UUID, plan: str) -> bool:
        """Return True if under monthly SMS limit."""
        limits = get_plan_limits(plan)
        current = await UsageMeteringService.get_sms_count_month(tenant_id)
        return current < limits.max_sms_per_month

    @staticmethod
    async def check_api_limit(tenant_id: UUID, plan: str) -> bool:
        """Return True if under daily API call limit."""
        limits = get_plan_limits(plan)
        current = await UsageMeteringService.get_api_calls_today(tenant_id)
        return current < limits.max_api_calls_per_day

    @staticmethod
    def check_feature_access(plan: str, feature: str) -> bool:
        """Return True if the feature is available in the plan."""
        limits = get_plan_limits(plan)
        return feature in limits.features

    # ── Full Usage Report ────────────────────────

    @staticmethod
    async def get_usage_metrics(
        tenant_id: UUID,
        plan: str,
        contacts_count: int,
        users_count: int,
        data_sources_count: int,
    ) -> UsageMetrics:
        """Build a full usage metrics report."""
        limits = get_plan_limits(plan)
        now = datetime.utcnow()
        period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        sms_sent = await UsageMeteringService.get_sms_count_month(tenant_id)
        api_calls = await UsageMeteringService.get_api_calls_today(tenant_id)

        def pct(current: int, maximum: int) -> float:
            return round(current / maximum * 100, 1) if maximum > 0 else 0

        warnings: list[str] = []
        if pct(contacts_count, limits.max_contacts) >= 90:
            warnings.append("contacts_near_limit")
        if pct(sms_sent, limits.max_sms_per_month) >= 90:
            warnings.append("sms_near_limit")
        if pct(api_calls, limits.max_api_calls_per_day) >= 90:
            warnings.append("api_calls_near_limit")
        if pct(users_count, limits.max_users) >= 90:
            warnings.append("users_near_limit")

        return UsageMetrics(
            tenant_id=tenant_id,
            period_start=period_start,
            period_end=now,
            contacts_count=contacts_count,
            contacts_limit=limits.max_contacts,
            contacts_percent=pct(contacts_count, limits.max_contacts),
            sms_sent=sms_sent,
            sms_limit=limits.max_sms_per_month,
            sms_percent=pct(sms_sent, limits.max_sms_per_month),
            api_calls_today=api_calls,
            api_calls_limit=limits.max_api_calls_per_day,
            api_calls_percent=pct(api_calls, limits.max_api_calls_per_day),
            users_count=users_count,
            users_limit=limits.max_users,
            users_percent=pct(users_count, limits.max_users),
            data_sources_count=data_sources_count,
            data_sources_limit=limits.max_data_sources,
            plan=plan,
            plan_features=limits.features,
            warnings=warnings,
        )


# ── Billing History ──────────────────────────────────


class BillingEvent(BaseModel):
    """A billing event (charge, upgrade, etc.)."""
    event_type: str  # charge, upgrade, downgrade, refund, trial_start, trial_end
    plan: str
    amount: int = 0  # in Rial
    currency: str = "IRR"
    description: str = ""
    event_date: datetime = Field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = Field(default_factory=dict)


class PlanInfo(BaseModel):
    """Full plan description for display."""
    name: str
    display_name: str
    display_name_fa: str
    price_monthly: int  # Rial
    price_yearly: int  # Rial
    limits: PlanLimits
    is_popular: bool = False


# Plan display catalogue
PLAN_CATALOGUE: list[PlanInfo] = [
    PlanInfo(
        name="free",
        display_name="Free",
        display_name_fa="رایگان",
        price_monthly=0,
        price_yearly=0,
        limits=PLANS["free"],
    ),
    PlanInfo(
        name="basic",
        display_name="Basic",
        display_name_fa="پایه",
        price_monthly=2_000_000,
        price_yearly=20_000_000,
        limits=PLANS["basic"],
    ),
    PlanInfo(
        name="professional",
        display_name="Professional",
        display_name_fa="حرفه‌ای",
        price_monthly=5_000_000,
        price_yearly=50_000_000,
        limits=PLANS["professional"],
        is_popular=True,
    ),
    PlanInfo(
        name="enterprise",
        display_name="Enterprise",
        display_name_fa="سازمانی",
        price_monthly=15_000_000,
        price_yearly=150_000_000,
        limits=PLANS["enterprise"],
    ),
]

