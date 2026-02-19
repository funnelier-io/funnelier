"""
Tests for RFM Segmentation
"""

import pytest
from datetime import datetime, timedelta
from uuid import uuid4

from src.core.domain import RFMSegment
from src.modules.segmentation.domain import (
    RFMConfig,
    ContactRFMScore,
    RFMCalculationService,
    SegmentRecommendationService,
)


class TestRFMConfig:
    """Tests for RFM configuration."""

    def test_default_config_values(self):
        """Test default RFM thresholds."""
        config = RFMConfig(tenant_id=uuid4())

        assert config.recency_score_5_max == 3
        assert config.recency_score_4_max == 7
        assert config.recency_score_3_max == 14
        assert config.recency_score_2_max == 30
        assert config.frequency_score_5_min == 10
        assert config.monetary_score_5_min == 1_000_000_000

    def test_calculate_recency_score(self):
        """Test recency score calculation."""
        config = RFMConfig(tenant_id=uuid4())

        assert config.calculate_recency_score(1) == 5  # 1 day
        assert config.calculate_recency_score(5) == 4  # 5 days
        assert config.calculate_recency_score(10) == 3  # 10 days
        assert config.calculate_recency_score(20) == 2  # 20 days
        assert config.calculate_recency_score(60) == 1  # 60 days

    def test_calculate_frequency_score(self):
        """Test frequency score calculation."""
        config = RFMConfig(tenant_id=uuid4())

        assert config.calculate_frequency_score(15) == 5  # 15 purchases
        assert config.calculate_frequency_score(7) == 4  # 7 purchases
        assert config.calculate_frequency_score(3) == 3  # 3 purchases
        assert config.calculate_frequency_score(2) == 2  # 2 purchases
        assert config.calculate_frequency_score(1) == 1  # 1 purchase

    def test_calculate_monetary_score(self):
        """Test monetary score calculation."""
        config = RFMConfig(tenant_id=uuid4())

        assert config.calculate_monetary_score(2_000_000_000) == 5  # 2B
        assert config.calculate_monetary_score(700_000_000) == 4  # 700M
        assert config.calculate_monetary_score(200_000_000) == 3  # 200M
        assert config.calculate_monetary_score(70_000_000) == 2  # 70M
        assert config.calculate_monetary_score(30_000_000) == 1  # 30M


class TestContactRFMScore:
    """Tests for contact RFM score calculation."""

    def test_calculate_rfm_score(self):
        """Test full RFM score calculation."""
        config = RFMConfig(tenant_id=uuid4())
        tenant_id = uuid4()
        contact_id = uuid4()

        score = ContactRFMScore(
            tenant_id=tenant_id,
            contact_id=contact_id,
            phone_number="9123456789",
            last_purchase_date=datetime.utcnow() - timedelta(days=2),
            total_purchases=12,
            total_spend=1_500_000_000,
        )

        score.calculate(config)

        assert score.recency_score == 5  # Within 3 days
        assert score.frequency_score == 5  # 12 purchases >= 10
        assert score.monetary_score == 5  # 1.5B >= 1B
        assert score.rfm_score == "555"
        assert score.segment == RFMSegment.CHAMPIONS

    def test_calculate_lost_customer(self):
        """Test RFM calculation for lost customer."""
        config = RFMConfig(tenant_id=uuid4())
        tenant_id = uuid4()
        contact_id = uuid4()

        score = ContactRFMScore(
            tenant_id=tenant_id,
            contact_id=contact_id,
            phone_number="9123456789",
            last_purchase_date=datetime.utcnow() - timedelta(days=90),
            total_purchases=1,
            total_spend=30_000_000,
        )

        score.calculate(config)

        assert score.recency_score == 1  # > 30 days
        assert score.frequency_score == 1  # 1 purchase
        assert score.monetary_score == 1  # < 50M
        assert score.rfm_score == "111"
        assert score.segment == RFMSegment.LOST

    def test_segment_change_event(self):
        """Test that segment change triggers domain event."""
        config = RFMConfig(tenant_id=uuid4())
        tenant_id = uuid4()
        contact_id = uuid4()

        score = ContactRFMScore(
            tenant_id=tenant_id,
            contact_id=contact_id,
            phone_number="9123456789",
            last_purchase_date=datetime.utcnow() - timedelta(days=2),
            total_purchases=12,
            total_spend=1_500_000_000,
            segment=RFMSegment.LOYAL,  # Previous segment
        )

        score.calculate(config)

        # Should have segment change event
        assert len(score.domain_events) == 1
        event = score.domain_events[0]
        assert event.event_type == "segment.contact_changed"
        assert event.old_segment == "loyal"
        assert event.new_segment == "champions"


class TestRFMSegment:
    """Tests for RFM segment determination."""

    def test_champions_segment(self):
        """Test champions segment identification."""
        assert RFMSegment.from_rfm_score(5, 5, 5) == RFMSegment.CHAMPIONS
        assert RFMSegment.from_rfm_score(5, 5, 4) == RFMSegment.CHAMPIONS
        assert RFMSegment.from_rfm_score(5, 4, 5) == RFMSegment.CHAMPIONS

    def test_loyal_segment(self):
        """Test loyal segment identification."""
        assert RFMSegment.from_rfm_score(4, 4, 4) == RFMSegment.LOYAL
        assert RFMSegment.from_rfm_score(3, 4, 5) == RFMSegment.LOYAL

    def test_at_risk_segment(self):
        """Test at risk segment identification."""
        assert RFMSegment.from_rfm_score(1, 5, 5) == RFMSegment.AT_RISK
        assert RFMSegment.from_rfm_score(2, 5, 4) == RFMSegment.AT_RISK

    def test_lost_segment(self):
        """Test lost segment identification."""
        assert RFMSegment.from_rfm_score(1, 1, 1) == RFMSegment.LOST

    def test_segment_priority(self):
        """Test segment priority ordering."""
        assert RFMSegment.CHAMPIONS.priority > RFMSegment.LOYAL.priority
        assert RFMSegment.AT_RISK.priority > RFMSegment.HIBERNATING.priority
        assert RFMSegment.LOST.priority < RFMSegment.HIBERNATING.priority


class TestSegmentRecommendationService:
    """Tests for segment recommendations."""

    def test_champions_recommendations(self):
        """Test recommendations for champions segment."""
        service = SegmentRecommendationService()

        action = service.get_action_for_segment(RFMSegment.CHAMPIONS)

        assert "vip" in action.get("sms_categories", [])
        assert action.get("product_strategy") == "premium"
        assert action.get("urgency") == "low"

    def test_at_risk_recommendations(self):
        """Test recommendations for at risk segment."""
        service = SegmentRecommendationService()

        action = service.get_action_for_segment(RFMSegment.AT_RISK)

        assert "urgent" in action.get("sms_categories", [])
        assert action.get("urgency") == "critical"

    def test_product_recommendations(self):
        """Test product recommendations for segment."""
        service = SegmentRecommendationService()

        products = [
            {"id": uuid4(), "name": "Product A", "category": "cement", "price": 1_500_000_000},
            {"id": uuid4(), "name": "Product B", "category": "cement", "price": 50_000_000},
        ]

        recommendations = service.recommend_products(
            RFMSegment.CHAMPIONS,
            products,
            limit=2,
        )

        assert len(recommendations) <= 2
        # Premium products should be recommended for champions
        if recommendations:
            assert recommendations[0].score > 0

