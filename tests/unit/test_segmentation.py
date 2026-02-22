"""
Tests for RFM Segmentation
"""

import pytest
from datetime import datetime, timedelta
from uuid import uuid4

from src.core.domain import RFMSegment
from src.modules.segmentation.domain import (
    RFMConfig,
    ContactRFMProfile,
    RFMScore,
    RFMCalculationService,
    SegmentRecommendationService,
    SEGMENT_RECOMMENDATIONS,
)


class TestRFMConfig:
    """Tests for RFM configuration."""

    def test_default_config_values(self):
        """Test default RFM thresholds."""
        config = RFMConfig(tenant_id=uuid4())

        assert config.recency_thresholds == [14, 30, 60, 90]
        assert config.frequency_thresholds == [1, 2, 4, 8]
        assert config.monetary_thresholds == [100_000_000, 500_000_000, 1_000_000_000, 2_000_000_000]
        assert config.high_value_threshold == 1_000_000_000

    def test_calculate_recency_score(self):
        """Test recency score calculation."""
        config = RFMConfig(tenant_id=uuid4())

        assert config.calculate_recency_score(5) == 5    # <=14 days
        assert config.calculate_recency_score(14) == 5   # <=14 days
        assert config.calculate_recency_score(20) == 4   # 15-30 days
        assert config.calculate_recency_score(45) == 3   # 31-60 days
        assert config.calculate_recency_score(80) == 2   # 61-90 days
        assert config.calculate_recency_score(120) == 1  # >90 days
        assert config.calculate_recency_score(None) == 1 # No purchase

    def test_calculate_frequency_score(self):
        """Test frequency score calculation."""
        config = RFMConfig(tenant_id=uuid4())

        assert config.calculate_frequency_score(15) == 5  # >=8 purchases
        assert config.calculate_frequency_score(8) == 5   # >=8
        assert config.calculate_frequency_score(6) == 4   # >=4
        assert config.calculate_frequency_score(3) == 3   # >=2
        assert config.calculate_frequency_score(1) == 2   # >=1
        assert config.calculate_frequency_score(0) == 1   # 0 purchases

    def test_calculate_monetary_score(self):
        """Test monetary score calculation."""
        config = RFMConfig(tenant_id=uuid4())

        assert config.calculate_monetary_score(3_000_000_000) == 5  # >=2B
        assert config.calculate_monetary_score(1_500_000_000) == 4  # >=1B
        assert config.calculate_monetary_score(700_000_000) == 3    # >=500M
        assert config.calculate_monetary_score(200_000_000) == 2    # >=100M
        assert config.calculate_monetary_score(50_000_000) == 1     # <100M


class TestRFMScore:
    """Tests for RFMScore value object."""

    def test_rfm_string(self):
        """Test RFM string representation."""
        score = RFMScore(recency=5, frequency=4, monetary=3)
        assert score.rfm_string == "543"

    def test_total_score(self):
        """Test total score calculation."""
        score = RFMScore(recency=5, frequency=5, monetary=5)
        assert score.total_score == 15

    def test_segment_score_weighted(self):
        """Test weighted segment score."""
        score = RFMScore(recency=5, frequency=4, monetary=3)
        # 5*0.4 + 4*0.3 + 3*0.3 = 2.0 + 1.2 + 0.9 = 4.1
        assert abs(score.segment_score - 4.1) < 0.01

    def test_get_segment(self):
        """Test segment determination from score."""
        score = RFMScore(recency=5, frequency=5, monetary=5)
        assert score.get_segment() == RFMSegment.CHAMPIONS


class TestRFMSegment:
    """Tests for RFM segment determination."""

    def test_champions_segment(self):
        """Test champions segment identification."""
        assert RFMSegment.from_rfm_score(5, 5, 5) == RFMSegment.CHAMPIONS
        assert RFMSegment.from_rfm_score(5, 5, 4) == RFMSegment.CHAMPIONS
        assert RFMSegment.from_rfm_score(5, 4, 5) == RFMSegment.CHAMPIONS

    def test_loyal_segment(self):
        """Test loyal segment identification."""
        assert RFMSegment.from_rfm_score(3, 4, 5) == RFMSegment.LOYAL
        assert RFMSegment.from_rfm_score(3, 5, 4) == RFMSegment.LOYAL

    def test_at_risk_segment(self):
        """Test at risk segment identification."""
        # at_risk: low recency, high value but f<4 or m<4 individually
        # Note: (1,5,5) matches loyal first (f>=4 and m>=4)
        assert RFMSegment.from_rfm_score(2, 3, 5) == RFMSegment.AT_RISK
        assert RFMSegment.from_rfm_score(1, 3, 4) == RFMSegment.AT_RISK

    def test_lost_segment(self):
        """Test lost segment identification."""
        # (1,1,1) matches hibernating (r==1, f<=2) before lost
        # Lost is the fallback for scores not matching other patterns
        assert RFMSegment.from_rfm_score(1, 1, 1) == RFMSegment.HIBERNATING
        # These fall through to lost
        assert RFMSegment.from_rfm_score(1, 3, 1) == RFMSegment.LOST

    def test_new_customers_segment(self):
        """Test new customers segment."""
        assert RFMSegment.from_rfm_score(5, 1, 1) == RFMSegment.NEW_CUSTOMERS

    def test_promising_segment(self):
        """Test promising segment."""
        assert RFMSegment.from_rfm_score(3, 1, 1) == RFMSegment.PROMISING

    def test_segment_priority(self):
        """Test segment priority ordering."""
        assert RFMSegment.CHAMPIONS.priority > RFMSegment.LOYAL.priority
        assert RFMSegment.AT_RISK.priority > RFMSegment.HIBERNATING.priority
        assert RFMSegment.LOST.priority < RFMSegment.HIBERNATING.priority


class TestRFMCalculationService:
    """Tests for RFM calculation service."""

    def test_calculate_champion_profile(self):
        """Test full RFM profile calculation for a champion."""
        config = RFMConfig(tenant_id=uuid4())
        service = RFMCalculationService(config)
        now = datetime.utcnow()

        profile = service.calculate_profile(
            tenant_id=uuid4(), contact_id=uuid4(),
            phone_number="9123456789",
            last_purchase_date=now - timedelta(days=2),
            purchase_count=12, total_spend=2_500_000_000,
            current_date=now,
        )

        assert profile.rfm_score is not None
        assert profile.rfm_score.recency == 5
        assert profile.rfm_score.frequency == 5
        assert profile.rfm_score.monetary == 5
        assert profile.segment == RFMSegment.CHAMPIONS

    def test_calculate_lost_customer_profile(self):
        """Test RFM calculation for lost customer."""
        config = RFMConfig(tenant_id=uuid4())
        service = RFMCalculationService(config)
        now = datetime.utcnow()

        profile = service.calculate_profile(
            tenant_id=uuid4(), contact_id=uuid4(),
            phone_number="9123456789",
            last_purchase_date=now - timedelta(days=120),
            purchase_count=0, total_spend=0,
            current_date=now,
        )

        assert profile.rfm_score.recency == 1
        assert profile.rfm_score.frequency == 1
        assert profile.rfm_score.monetary == 1

    def test_calculate_no_purchase_date(self):
        """Test RFM calculation with no purchase date."""
        config = RFMConfig(tenant_id=uuid4())
        service = RFMCalculationService(config)

        profile = service.calculate_profile(
            tenant_id=uuid4(), contact_id=uuid4(),
            phone_number="9123456789",
            last_purchase_date=None, purchase_count=0, total_spend=0,
        )

        assert profile.rfm_score.recency == 1
        assert profile.segment is not None

    def test_calculate_score_directly(self):
        """Test direct score calculation."""
        config = RFMConfig(tenant_id=uuid4())
        service = RFMCalculationService(config)

        score = service.calculate_score(
            days_since_last_purchase=5,
            purchase_count=10, total_spend=1_500_000_000,
        )

        assert score.recency == 5
        assert score.frequency == 5
        assert score.monetary == 4


class TestSegmentRecommendationService:
    """Tests for segment recommendations."""

    def test_all_segments_have_recommendations(self):
        """Test that all segments have recommendations."""
        service = SegmentRecommendationService()

        for segment in RFMSegment:
            rec = service.get_recommendation(segment)
            assert rec is not None
            assert rec.segment_name_fa
            assert rec.recommended_message_types
            assert rec.channel_priority

    def test_champions_recommendations(self):
        """Test recommendations for champions segment."""
        service = SegmentRecommendationService()
        rec = service.get_recommendation(RFMSegment.CHAMPIONS)

        assert any(t in rec.recommended_message_types for t in ["exclusive", "vip", "new_product"])
        assert rec.discount_allowed is False
        assert rec.max_discount_percent == 0

    def test_at_risk_recommendations(self):
        """Test recommendations for at risk segment."""
        service = SegmentRecommendationService()
        rec = service.get_recommendation(RFMSegment.AT_RISK)

        assert rec.discount_allowed is True
        assert rec.max_discount_percent > 0

    def test_message_types_for_segment(self):
        """Test getting message types for a segment."""
        service = SegmentRecommendationService()
        types = service.get_message_types_for_segment(RFMSegment.NEW_CUSTOMERS)

        assert isinstance(types, list)
        assert len(types) > 0

    def test_discount_strategy(self):
        """Test discount strategy for different segments."""
        service = SegmentRecommendationService()

        champ = service.get_discount_strategy(RFMSegment.CHAMPIONS)
        assert champ["allowed"] is False

        risk = service.get_discount_strategy(RFMSegment.AT_RISK)
        assert risk["allowed"] is True
        assert risk["max_percent"] > 0

    def test_segment_contacts_for_vip_campaign(self):
        """Test filtering contacts for VIP campaign."""
        service = SegmentRecommendationService()
        tid = uuid4()

        profiles = []
        for segment in [RFMSegment.CHAMPIONS, RFMSegment.LOYAL, RFMSegment.LOST]:
            p = ContactRFMProfile(
                tenant_id=tid, contact_id=uuid4(), phone_number="912345",
            )
            p.segment = segment
            p.rfm_score = RFMScore(recency=5, frequency=5, monetary=5)
            profiles.append(p)

        vip_contacts = service.segment_contacts_for_campaign(profiles, "vip")
        assert len(vip_contacts) == 2
        for c in vip_contacts:
            assert c.segment in [RFMSegment.CHAMPIONS, RFMSegment.LOYAL]
