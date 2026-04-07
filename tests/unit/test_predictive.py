"""
Tests for Predictive Analytics Service
Churn prediction, lead scoring, A/B test, campaign ROI, retention.
"""

import math
from datetime import datetime, timedelta
from uuid import uuid4

import pytest

from src.modules.analytics.application.predictive_service import (
    PredictiveAnalyticsService,
)


@pytest.fixture
def svc():
    return PredictiveAnalyticsService()


# ── Churn Prediction Tests ───────────────────────────


def _make_contact(**overrides):
    base = {
        "id": uuid4(),
        "phone_number": "09121234567",
        "name": "Test",
        "category_name": "general",
        "current_stage": "lead_acquired",
        "rfm_segment": None,
        "total_calls": 0,
        "answered_calls": 0,
        "total_sms_received": 0,
        "purchase_count": 0,
        "total_spend": 0,
        "days_since_last_activity": 100,
        "days_since_created": 100,
        "last_activity_date": None,
    }
    base.update(overrides)
    return base


class TestChurnPrediction:
    def test_inactive_contact_high_churn(self, svc):
        contacts = [_make_contact(days_since_last_activity=200, total_calls=0)]
        result = svc.predict_churn(contacts)
        assert result.total_contacts == 1
        assert result.top_risk_contacts[0].churn_probability > 0.7

    def test_active_contact_low_churn(self, svc):
        contacts = [_make_contact(
            days_since_last_activity=3,
            total_calls=10,
            answered_calls=5,
            purchase_count=5,
            total_spend=500_000_000,
            current_stage="call_answered",
        )]
        result = svc.predict_churn(contacts)
        assert result.top_risk_contacts[0].churn_probability < 0.4

    def test_churn_risk_distribution(self, svc):
        contacts = [
            _make_contact(days_since_last_activity=5, total_calls=10, answered_calls=5, purchase_count=3),
            _make_contact(days_since_last_activity=100, total_calls=0),
            _make_contact(days_since_last_activity=200, total_calls=0),
        ]
        result = svc.predict_churn(contacts)
        assert sum(result.risk_distribution.values()) == 3

    def test_churn_empty_contacts(self, svc):
        result = svc.predict_churn([])
        assert result.total_contacts == 0
        assert result.at_risk_count == 0

    def test_churn_has_recommendations(self, svc):
        contacts = [_make_contact()]
        result = svc.predict_churn(contacts)
        assert len(result.recommendations) > 0

    def test_churn_revenue_at_risk(self, svc):
        contacts = [
            _make_contact(days_since_last_activity=200, total_spend=100_000_000),
        ]
        result = svc.predict_churn(contacts)
        assert result.estimated_revenue_at_risk > 0


# ── Lead Scoring Tests ───────────────────────────────


class TestLeadScoring:
    def test_hot_lead_high_score(self, svc):
        leads = [_make_contact(
            current_stage="call_answered",
            total_calls=5,
            answered_calls=3,
            days_since_created=5,
            purchase_count=2,
            total_spend=200_000_000,
        )]
        result = svc.score_leads(leads)
        assert result.top_leads[0].score >= 60
        assert result.top_leads[0].grade in ("A", "B")

    def test_cold_lead_low_score(self, svc):
        leads = [_make_contact(
            current_stage="lead_acquired",
            total_calls=0,
            answered_calls=0,
            days_since_created=120,
            purchase_count=0,
        )]
        result = svc.score_leads(leads)
        assert result.top_leads[0].score < 30
        assert result.top_leads[0].grade in ("D", "F")

    def test_grade_distribution(self, svc):
        leads = [
            _make_contact(current_stage="payment_received", total_calls=10, answered_calls=5, purchase_count=5, days_since_created=5),
            _make_contact(current_stage="lead_acquired", total_calls=0, days_since_created=120),
        ]
        result = svc.score_leads(leads)
        assert sum(result.grade_distribution.values()) == 2

    def test_scoring_factors_present(self, svc):
        leads = [_make_contact()]
        result = svc.score_leads(leads)
        assert "stage_progression" in result.top_leads[0].scoring_factors
        assert "engagement" in result.top_leads[0].scoring_factors

    def test_empty_leads(self, svc):
        result = svc.score_leads([])
        assert result.total_scored == 0
        assert result.average_score == 0


# ── A/B Test Tests ───────────────────────────────────


class TestABTest:
    def test_significant_difference(self, svc):
        result = svc.ab_test_significance(
            test_name="SMS test",
            variant_a_conversions=50,
            variant_a_total=1000,
            variant_b_conversions=80,
            variant_b_total=1000,
        )
        assert result.variant_a_rate == 0.05
        assert result.variant_b_rate == 0.08
        assert result.is_significant is True
        assert result.winner is not None
        assert result.p_value < 0.05

    def test_no_significant_difference(self, svc):
        result = svc.ab_test_significance(
            test_name="Small test",
            variant_a_conversions=5,
            variant_a_total=100,
            variant_b_conversions=6,
            variant_b_total=100,
        )
        assert result.is_significant is False
        assert result.winner is None

    def test_equal_variants(self, svc):
        result = svc.ab_test_significance(
            test_name="Equal",
            variant_a_conversions=50,
            variant_a_total=1000,
            variant_b_conversions=50,
            variant_b_total=1000,
        )
        assert abs(result.absolute_difference) < 0.001
        assert result.is_significant is False

    def test_required_sample_size_returned(self, svc):
        result = svc.ab_test_significance(
            test_name="test",
            variant_a_conversions=5,
            variant_a_total=50,
            variant_b_conversions=10,
            variant_b_total=50,
        )
        assert result.required_sample_size > 0

    def test_confidence_threshold_custom(self, svc):
        result = svc.ab_test_significance(
            test_name="strict",
            variant_a_conversions=50,
            variant_a_total=1000,
            variant_b_conversions=65,
            variant_b_total=1000,
            confidence_threshold=0.99,
        )
        # With 99% threshold, marginal differences may not be significant
        assert isinstance(result.is_significant, bool)


# ── Campaign ROI Tests ───────────────────────────────


class TestCampaignROI:
    def test_positive_roi(self, svc):
        result = svc.calculate_campaign_roi(
            campaign_name="SMS Campaign",
            campaign_id=uuid4(),
            total_cost=1_000_000,
            leads_generated=500,
            conversions=50,
            total_revenue=10_000_000,
        )
        assert result.roi_percent > 0
        assert result.cost_per_lead == 2000
        assert result.cost_per_conversion == 20000
        assert result.conversion_rate == 0.1

    def test_negative_roi(self, svc):
        result = svc.calculate_campaign_roi(
            campaign_name="Bad Campaign",
            campaign_id=None,
            total_cost=10_000_000,
            leads_generated=100,
            conversions=2,
            total_revenue=5_000_000,
        )
        assert result.roi_percent < 0

    def test_zero_cost(self, svc):
        result = svc.calculate_campaign_roi(
            campaign_name="Free",
            campaign_id=None,
            total_cost=0,
            leads_generated=100,
            conversions=10,
            total_revenue=1_000_000,
        )
        assert result.roi_percent == 0  # can't divide by zero
        assert result.cost_per_lead == 0

    def test_break_even(self, svc):
        result = svc.calculate_campaign_roi(
            campaign_name="test",
            campaign_id=None,
            total_cost=1_000_000,
            leads_generated=100,
            conversions=10,
            total_revenue=5_000_000,
        )
        assert result.break_even_conversions > 0


# ── Retention Tests ──────────────────────────────────


class TestRetention:
    def test_retention_curves(self, svc):
        now = datetime.utcnow()
        cohorts_data = [
            {
                "cohort_label": "2026-W01",
                "cohort_start": now - timedelta(days=56),
                "contacts": [
                    {"created_at": now - timedelta(days=56), "last_activity_date": now - timedelta(days=10), "is_active": True},
                    {"created_at": now - timedelta(days=56), "last_activity_date": now - timedelta(days=50), "is_active": False},
                    {"created_at": now - timedelta(days=55), "last_activity_date": now - timedelta(days=2), "is_active": True},
                ],
            },
        ]
        result = svc.calculate_retention(cohorts_data, "weekly", 8)
        assert len(result.cohorts) == 1
        assert result.cohorts[0].cohort_size == 3
        assert 0 in result.cohorts[0].retention_by_period
        assert result.overall_churn_rate >= 0

    def test_empty_cohorts(self, svc):
        result = svc.calculate_retention([], "weekly", 4)
        assert len(result.cohorts) == 0

    def test_average_retention(self, svc):
        now = datetime.utcnow()
        cohorts_data = [
            {
                "cohort_label": "C1",
                "cohort_start": now - timedelta(days=28),
                "contacts": [
                    {"created_at": now - timedelta(days=28), "last_activity_date": now, "is_active": True},
                    {"created_at": now - timedelta(days=28), "last_activity_date": now, "is_active": True},
                ],
            },
            {
                "cohort_label": "C2",
                "cohort_start": now - timedelta(days=21),
                "contacts": [
                    {"created_at": now - timedelta(days=21), "last_activity_date": now, "is_active": True},
                ],
            },
        ]
        result = svc.calculate_retention(cohorts_data, "weekly", 4)
        assert len(result.cohorts) == 2
        assert 0 in result.average_retention_by_period

