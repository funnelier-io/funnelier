"""
Unit tests for Team module and RFM calculation.

Tests team helper functions, RFM calculation logic, and segment assignment.
"""

import pytest
from datetime import datetime, timedelta
from uuid import UUID, uuid4

from src.modules.segmentation.domain.services import (
    RFMCalculationService,
    SegmentRecommendationService,
)
from src.modules.segmentation.domain.entities import RFMConfig, RFMScore
from src.core.domain import RFMSegment


# ============================================================================
# RFM Calculation Tests
# ============================================================================

class TestRFMCalculationService:
    """Tests for RFMCalculationService."""

    def setup_method(self):
        self.tenant_id = uuid4()
        self.config = RFMConfig(tenant_id=self.tenant_id)
        self.service = RFMCalculationService(self.config)

    def test_calculate_score_champion(self):
        """Champion: recent purchase, high frequency, high monetary."""
        score = self.service.calculate_score(
            days_since_last_purchase=2,
            purchase_count=15,
            total_spend=2_000_000_000,
        )
        assert score.recency >= 4
        assert score.frequency >= 4
        assert score.monetary >= 4

    def test_calculate_score_lost(self):
        """Lost: old purchase, low frequency, low monetary."""
        score = self.service.calculate_score(
            days_since_last_purchase=120,
            purchase_count=1,
            total_spend=20_000_000,
        )
        assert score.recency <= 2
        assert score.frequency <= 2
        assert score.monetary <= 2

    def test_calculate_score_no_purchase(self):
        """No purchase history: all scores should be 1."""
        score = self.service.calculate_score(
            days_since_last_purchase=None,
            purchase_count=0,
            total_spend=0,
        )
        assert score.recency == 1
        assert score.frequency == 1
        assert score.monetary == 1

    def test_calculate_score_new_customer(self):
        """New customer: very recent, low frequency, moderate spend."""
        score = self.service.calculate_score(
            days_since_last_purchase=3,
            purchase_count=1,
            total_spend=200_000_000,
        )
        assert score.recency >= 4  # Very recent
        assert score.frequency <= 2  # Only 1 purchase
        assert score.monetary >= 2  # Moderate spend

    def test_calculate_profile(self):
        """Test full profile calculation."""
        profile = self.service.calculate_profile(
            tenant_id=self.tenant_id,
            contact_id=uuid4(),
            phone_number="9123456789",
            last_purchase_date=datetime.utcnow() - timedelta(days=5),
            purchase_count=8,
            total_spend=800_000_000,
        )
        assert profile.rfm_score is not None
        assert profile.segment is not None
        assert profile.average_order_value == 100_000_000

    def test_calculate_profile_no_purchases(self):
        """Test profile with no purchase history."""
        profile = self.service.calculate_profile(
            tenant_id=self.tenant_id,
            contact_id=uuid4(),
            phone_number="9123456789",
            last_purchase_date=None,
            purchase_count=0,
            total_spend=0,
        )
        assert profile.rfm_score.recency == 1
        assert profile.rfm_score.frequency == 1
        assert profile.rfm_score.monetary == 1
        assert profile.average_order_value == 0

    def test_batch_calculate(self):
        """Test batch calculation of multiple contacts."""
        contacts = [
            {
                "tenant_id": self.tenant_id,
                "contact_id": uuid4(),
                "phone_number": "9123456789",
                "last_purchase_date": datetime.utcnow() - timedelta(days=2),
                "purchase_count": 15,
                "total_spend": 2_000_000_000,
            },
            {
                "tenant_id": self.tenant_id,
                "contact_id": uuid4(),
                "phone_number": "9351234567",
                "last_purchase_date": None,
                "purchase_count": 0,
                "total_spend": 0,
            },
        ]
        profiles = self.service.batch_calculate(contacts)
        assert len(profiles) == 2
        # First should be champion-ish, second should be lost
        assert profiles[0].rfm_score.recency > profiles[1].rfm_score.recency

    def test_analyze_segments(self):
        """Test segment analysis."""
        contacts = [
            {
                "tenant_id": self.tenant_id,
                "contact_id": uuid4(),
                "phone_number": f"912345678{i}",
                "last_purchase_date": datetime.utcnow() - timedelta(days=i * 10),
                "purchase_count": max(1, 10 - i),
                "total_spend": max(100_000_000, 2_000_000_000 - i * 200_000_000),
            }
            for i in range(5)
        ]
        profiles = self.service.batch_calculate(contacts)
        result = self.service.analyze_segments(self.tenant_id, profiles)

        assert result.total_contacts_analyzed == 5
        assert result.contacts_with_purchases > 0
        assert len(result.segment_summaries) > 0


class TestSegmentRecommendationService:
    """Tests for SegmentRecommendationService."""

    def setup_method(self):
        self.service = SegmentRecommendationService()

    def test_get_recommendation_champions(self):
        """Test recommendation for Champions segment."""
        rec = self.service.get_recommendation(RFMSegment.CHAMPIONS)
        assert rec is not None
        assert len(rec.recommended_message_types) > 0
        assert len(rec.recommended_products) > 0

    def test_get_recommendation_at_risk(self):
        """Test recommendation for At Risk segment."""
        rec = self.service.get_recommendation(RFMSegment.AT_RISK)
        assert rec is not None
        assert rec.discount_allowed is True

    def test_get_all_recommendations(self):
        """Test getting all segment recommendations."""
        all_recs = self.service.get_all_recommendations()
        assert len(all_recs) >= 7  # At least 7 segments covered

    def test_get_message_types(self):
        """Test getting message types for segment."""
        types = self.service.get_message_types_for_segment(RFMSegment.LOYAL)
        assert isinstance(types, list)
        assert len(types) > 0

    def test_get_products_for_segment(self):
        """Test getting product recommendations for segment."""
        products = self.service.get_products_for_segment(RFMSegment.CHAMPIONS)
        assert isinstance(products, list)

    def test_get_channel_priority(self):
        """Test getting channel priority for segment."""
        channels = self.service.get_channel_priority(RFMSegment.LOYAL)
        assert isinstance(channels, list)

    def test_get_discount_strategy(self):
        """Test getting discount strategy for segment."""
        strategy = self.service.get_discount_strategy(RFMSegment.AT_RISK)
        assert "allowed" in strategy
        assert "max_percent" in strategy

    def test_segment_contacts_for_campaign_promotional(self):
        """Test filtering contacts for promotional campaign."""
        config = RFMConfig(tenant_id=uuid4())
        calc_service = RFMCalculationService(config)

        contacts = [
            {
                "tenant_id": config.tenant_id,
                "contact_id": uuid4(),
                "phone_number": f"912345678{i}",
                "last_purchase_date": datetime.utcnow() - timedelta(days=i * 10),
                "purchase_count": max(1, 10 - i),
                "total_spend": max(100_000_000, 2_000_000_000 - i * 200_000_000),
            }
            for i in range(10)
        ]
        profiles = calc_service.batch_calculate(contacts)
        filtered = self.service.segment_contacts_for_campaign(profiles, "promotional")
        # Should filter to only promotional segments
        assert all(p.segment in [
            RFMSegment.POTENTIAL_LOYALIST,
            RFMSegment.PROMISING,
            RFMSegment.NEW_CUSTOMERS,
        ] for p in filtered)

    def test_prioritize_contacts(self):
        """Test contact prioritization."""
        config = RFMConfig(tenant_id=uuid4())
        calc_service = RFMCalculationService(config)

        contacts = [
            {
                "tenant_id": config.tenant_id,
                "contact_id": uuid4(),
                "phone_number": f"912345678{i}",
                "last_purchase_date": datetime.utcnow() - timedelta(days=i * 30),
                "purchase_count": max(1, 10 - i * 2),
                "total_spend": max(50_000_000, 2_000_000_000 - i * 300_000_000),
            }
            for i in range(5)
        ]
        profiles = calc_service.batch_calculate(contacts)
        prioritized = self.service.prioritize_contacts(profiles)
        assert len(prioritized) == 5
        # First contact should have higher or equal priority than last
        if prioritized[0].segment and prioritized[-1].segment:
            assert prioritized[0].segment.priority >= prioritized[-1].segment.priority


class TestRFMSegmentFromScore:
    """Tests for RFMSegment.from_rfm_score classification."""

    def test_high_scores_are_champions(self):
        """R=5, F=5, M=5 should be Champions."""
        segment = RFMSegment.from_rfm_score(5, 5, 5)
        assert segment == RFMSegment.CHAMPIONS

    def test_low_scores_are_hibernating(self):
        """R=1, F=1, M=1 should be Hibernating."""
        segment = RFMSegment.from_rfm_score(1, 1, 1)
        assert segment == RFMSegment.HIBERNATING

    def test_high_recency_low_frequency_is_new(self):
        """R=5, F=1, M=1 should be New Customers."""
        segment = RFMSegment.from_rfm_score(5, 1, 1)
        assert segment == RFMSegment.NEW_CUSTOMERS

    def test_low_recency_high_frequency_is_loyal(self):
        """R=1, F=5, M=5 — high frequency/monetary but low recency maps to Loyal."""
        segment = RFMSegment.from_rfm_score(1, 5, 5)
        assert segment == RFMSegment.LOYAL


class TestRFMConfig:
    """Tests for RFMConfig entity."""

    def test_default_config(self):
        """Test default RFM configuration values."""
        config = RFMConfig(tenant_id=uuid4())
        assert len(config.recency_thresholds) == 4
        assert len(config.frequency_thresholds) == 4
        assert len(config.monetary_thresholds) == 4
        assert config.high_value_threshold == 1_000_000_000
        assert config.recent_days == 14

    def test_recency_score_calculation(self):
        """Test recency score from days since purchase."""
        config = RFMConfig(tenant_id=uuid4())
        # Very recent should be 5
        score = config.calculate_recency_score(2)
        assert score == 5
        # Very old should be 1
        score = config.calculate_recency_score(200)
        assert score == 1
        # None (never purchased) should be 1
        score = config.calculate_recency_score(None)
        assert score == 1

    def test_frequency_score_calculation(self):
        """Test frequency score from purchase count."""
        config = RFMConfig(tenant_id=uuid4())
        score = config.calculate_frequency_score(20)
        assert score >= 4
        score = config.calculate_frequency_score(0)
        assert score == 1

    def test_monetary_score_calculation(self):
        """Test monetary score from total spend."""
        config = RFMConfig(tenant_id=uuid4())
        score = config.calculate_monetary_score(5_000_000_000)
        assert score == 5
        score = config.calculate_monetary_score(0)
        assert score == 1


# ============================================================================
# Team Helper Function Tests (without DB)
# ============================================================================

class TestTeamPerformanceMetrics:
    """Tests for team performance metric calculations."""

    def test_performance_metrics_schema_defaults(self):
        """Test PerformanceMetricsSchema has proper defaults."""
        from src.modules.team.api.schemas import PerformanceMetricsSchema
        metrics = PerformanceMetricsSchema()
        assert metrics.total_calls == 0
        assert metrics.answered_calls == 0
        assert metrics.answer_rate == 0.0
        assert metrics.contact_rate == 0.0

    def test_performance_metrics_with_data(self):
        """Test PerformanceMetricsSchema with actual data."""
        from src.modules.team.api.schemas import PerformanceMetricsSchema
        metrics = PerformanceMetricsSchema(
            total_calls=100,
            answered_calls=40,
            successful_calls=20,
            total_call_duration=12000,
            average_call_duration=120.0,
            answer_rate=0.40,
            success_rate=0.20,
            assigned_leads=500,
            contacted_leads=300,
            contact_rate=0.60,
        )
        assert metrics.total_calls == 100
        assert metrics.answer_rate == 0.40
        assert metrics.contact_rate == 0.60

    def test_salesperson_response_schema(self):
        """Test SalespersonResponse schema."""
        from src.modules.team.api.schemas import SalespersonResponse
        sp = SalespersonResponse(
            id=uuid4(),
            tenant_id=uuid4(),
            name="تست",
            phone_number="9121234567",
            regions=["تهران"],
            created_at=datetime.utcnow(),
        )
        assert sp.name == "تست"
        assert sp.regions == ["تهران"]
        assert sp.assigned_leads == 0

    def test_salesperson_performance_response(self):
        """Test SalespersonPerformanceResponse schema."""
        from src.modules.team.api.schemas import (
            SalespersonPerformanceResponse,
            PerformanceMetricsSchema,
        )
        perf = SalespersonPerformanceResponse(
            salesperson_id=uuid4(),
            salesperson_name="تست",
            period_start=datetime.utcnow() - timedelta(days=30),
            period_end=datetime.utcnow(),
            metrics=PerformanceMetricsSchema(
                total_calls=150,
                answered_calls=60,
            ),
        )
        assert perf.salesperson_name == "تست"
        assert perf.metrics.total_calls == 150

    def test_daily_activity_summary(self):
        """Test DailyActivitySummaryResponse schema."""
        from src.modules.team.api.schemas import DailyActivitySummaryResponse
        summary = DailyActivitySummaryResponse(
            date=datetime.utcnow(),
            salesperson_id=uuid4(),
            salesperson_name="تست",
            calls_made=25,
            calls_answered=10,
        )
        assert summary.calls_made == 25
        assert summary.sms_sent == 0  # default

    def test_team_performance_aggregation(self):
        """Test that team performance can be aggregated from individual metrics."""
        from src.modules.team.api.schemas import PerformanceMetricsSchema

        sp_metrics = [
            PerformanceMetricsSchema(total_calls=100, answered_calls=40, successful_calls=20),
            PerformanceMetricsSchema(total_calls=80, answered_calls=32, successful_calls=16),
            PerformanceMetricsSchema(total_calls=60, answered_calls=24, successful_calls=12),
        ]

        total_calls = sum(m.total_calls for m in sp_metrics)
        total_answered = sum(m.answered_calls for m in sp_metrics)
        total_successful = sum(m.successful_calls for m in sp_metrics)

        assert total_calls == 240
        assert total_answered == 96
        assert total_successful == 48

        answer_rate = total_answered / total_calls
        success_rate = total_successful / total_calls
        assert abs(answer_rate - 0.40) < 0.01
        assert abs(success_rate - 0.20) < 0.01

