"""
Tests for Phase 28 — Multi-tenant Billing & Usage Metering.
"""

from uuid import uuid4

import pytest

from src.modules.tenants.application.billing_service import (
    PLANS,
    PLAN_CATALOGUE,
    PlanLimits,
    UsageMeteringService,
    UsageMetrics,
    get_plan_limits,
)


# ── Plan Definition Tests ───────────────────────────


class TestPlanDefinitions:
    def test_four_plans_exist(self):
        assert len(PLANS) == 4
        assert "free" in PLANS
        assert "basic" in PLANS
        assert "professional" in PLANS
        assert "enterprise" in PLANS

    def test_free_plan_has_lowest_limits(self):
        free = PLANS["free"]
        for name, plan in PLANS.items():
            if name != "free":
                assert plan.max_contacts >= free.max_contacts
                assert plan.max_sms_per_month >= free.max_sms_per_month
                assert plan.max_users >= free.max_users

    def test_enterprise_has_highest_limits(self):
        enterprise = PLANS["enterprise"]
        for name, plan in PLANS.items():
            if name != "enterprise":
                assert enterprise.max_contacts >= plan.max_contacts
                assert enterprise.max_users >= plan.max_users

    def test_professional_features_include_predictive(self):
        pro = PLANS["professional"]
        assert "predictive_analytics" in pro.features
        assert "ab_testing" in pro.features
        assert "retention_analysis" in pro.features

    def test_free_plan_has_basic_features_only(self):
        free = PLANS["free"]
        assert "funnel_analytics" in free.features
        assert "predictive_analytics" not in free.features
        assert "custom_reports" not in free.features

    def test_get_plan_limits_returns_free_for_unknown(self):
        result = get_plan_limits("unknown_plan")
        assert result.max_contacts == PLANS["free"].max_contacts

    def test_get_plan_limits_returns_correct_plan(self):
        result = get_plan_limits("professional")
        assert result.max_contacts == 50_000
        assert result.max_sms_per_month == 10_000


# ── Plan Catalogue Tests ────────────────────────────


class TestPlanCatalogue:
    def test_catalogue_has_four_plans(self):
        assert len(PLAN_CATALOGUE) == 4

    def test_professional_is_popular(self):
        pro = [p for p in PLAN_CATALOGUE if p.name == "professional"][0]
        assert pro.is_popular is True

    def test_free_plan_has_zero_price(self):
        free = [p for p in PLAN_CATALOGUE if p.name == "free"][0]
        assert free.price_monthly == 0
        assert free.price_yearly == 0

    def test_yearly_cheaper_than_monthly(self):
        for plan in PLAN_CATALOGUE:
            if plan.price_monthly > 0:
                assert plan.price_yearly < plan.price_monthly * 12

    def test_has_persian_names(self):
        for plan in PLAN_CATALOGUE:
            assert plan.display_name_fa
            assert len(plan.display_name_fa) > 0


# ── Feature Gating Tests ────────────────────────────


class TestFeatureGating:
    def test_free_cannot_access_predictive(self):
        assert UsageMeteringService.check_feature_access("free", "predictive_analytics") is False

    def test_pro_can_access_predictive(self):
        assert UsageMeteringService.check_feature_access("professional", "predictive_analytics") is True

    def test_enterprise_can_access_sso(self):
        assert UsageMeteringService.check_feature_access("enterprise", "sso") is True

    def test_basic_cannot_access_sso(self):
        assert UsageMeteringService.check_feature_access("basic", "sso") is False

    def test_all_plans_have_funnel_analytics(self):
        for plan_name in PLANS:
            assert UsageMeteringService.check_feature_access(plan_name, "funnel_analytics") is True


# ── Usage Metrics Tests ─────────────────────────────


class TestUsageMetrics:
    @pytest.mark.asyncio
    async def test_get_usage_metrics_structure(self):
        """Test usage metrics with zero Redis data."""
        metrics = await UsageMeteringService.get_usage_metrics(
            tenant_id=uuid4(),
            plan="professional",
            contacts_count=5000,
            users_count=10,
            data_sources_count=3,
        )
        assert isinstance(metrics, UsageMetrics)
        assert metrics.contacts_count == 5000
        assert metrics.contacts_limit == 50_000
        assert metrics.contacts_percent == 10.0
        assert metrics.users_count == 10
        assert metrics.plan == "professional"
        assert len(metrics.plan_features) > 0

    @pytest.mark.asyncio
    async def test_warnings_when_near_limit(self):
        """Test that warnings are generated when usage is near limits."""
        metrics = await UsageMeteringService.get_usage_metrics(
            tenant_id=uuid4(),
            plan="free",
            contacts_count=460,  # 92% of 500 limit
            users_count=2,  # 100% of 2 limit
            data_sources_count=1,
        )
        assert "contacts_near_limit" in metrics.warnings
        assert "users_near_limit" in metrics.warnings

    @pytest.mark.asyncio
    async def test_no_warnings_when_low_usage(self):
        """Test no warnings for low usage."""
        metrics = await UsageMeteringService.get_usage_metrics(
            tenant_id=uuid4(),
            plan="enterprise",
            contacts_count=100,
            users_count=5,
            data_sources_count=2,
        )
        assert len(metrics.warnings) == 0

    @pytest.mark.asyncio
    async def test_api_calls_returns_zero_without_redis(self):
        """API call counters return 0 when Redis is unavailable."""
        count = await UsageMeteringService.get_api_calls_today(uuid4())
        assert count == 0

    @pytest.mark.asyncio
    async def test_sms_count_returns_zero_without_redis(self):
        """SMS counters return 0 when Redis is unavailable."""
        count = await UsageMeteringService.get_sms_count_month(uuid4())
        assert count == 0


# ── Usage Enforcement Middleware Tests ───────────────


class TestUsageEnforcement:
    def test_skip_prefixes(self):
        from src.api.middleware.usage_enforcement import _SKIP_PREFIXES
        assert "/health" in _SKIP_PREFIXES
        assert "/api/v1/auth" in _SKIP_PREFIXES
        assert "/api/v1/webhooks" in _SKIP_PREFIXES

