"""
Unit Tests — A/B Test Domain & Service (Phase 39)

Covers:
- ABTestVariant metrics (open_rate, conversion_rate)
- ABTestConfig defaults and constraints
- compute_winner: statistical significance, min sample, ties
- ABTestService mocked operations
"""

import pytest
from uuid import uuid4, UUID
from unittest.mock import AsyncMock, MagicMock, patch

from src.modules.campaigns.domain.ab_test import (
    ABTestConfig,
    ABTestVariant,
    compute_winner,
)


# ─── ABTestVariant ────────────────────────────────────────────────────────────

class TestABTestVariant:
    def _make_variant(self, name="A", sent=0, opens=0, conversions=0) -> ABTestVariant:
        return ABTestVariant(
            campaign_id=uuid4(),
            variant_name=name,
            message_content="Hello {name}",
            total_sent=sent,
            total_opens=opens,
            total_conversions=conversions,
        )

    def test_open_rate_zero_when_no_sends(self):
        v = self._make_variant()
        assert v.open_rate == 0.0

    def test_conversion_rate_zero_when_no_sends(self):
        v = self._make_variant()
        assert v.conversion_rate == 0.0

    def test_open_rate_calculation(self):
        v = self._make_variant(sent=100, opens=25)
        assert v.open_rate == pytest.approx(0.25)

    def test_conversion_rate_calculation(self):
        v = self._make_variant(sent=100, conversions=10)
        assert v.conversion_rate == pytest.approx(0.10)

    def test_open_rate_100_percent(self):
        v = self._make_variant(sent=50, opens=50)
        assert v.open_rate == pytest.approx(1.0)

    def test_variant_b(self):
        v = self._make_variant(name="B", sent=200, opens=40)
        assert v.variant_name == "B"
        assert v.open_rate == pytest.approx(0.2)

    def test_default_split_percent(self):
        v = self._make_variant()
        assert v.split_percent == 50

    def test_auto_uuid(self):
        v = self._make_variant()
        assert isinstance(v.id, UUID)


# ─── ABTestConfig ─────────────────────────────────────────────────────────────

class TestABTestConfig:
    def test_default_split(self):
        cfg = ABTestConfig(message_a="A", message_b="B")
        assert cfg.split_percent == 50

    def test_default_winner_criteria(self):
        cfg = ABTestConfig(message_a="A", message_b="B")
        assert cfg.winner_criteria == "open_rate"

    def test_default_min_sample(self):
        cfg = ABTestConfig(message_a="A", message_b="B")
        assert cfg.min_sample_size == 50

    def test_custom_split(self):
        cfg = ABTestConfig(message_a="A", message_b="B", split_percent=70)
        assert cfg.split_percent == 70

    def test_split_lower_bound_validation(self):
        with pytest.raises(Exception):
            ABTestConfig(message_a="A", message_b="B", split_percent=5)

    def test_split_upper_bound_validation(self):
        with pytest.raises(Exception):
            ABTestConfig(message_a="A", message_b="B", split_percent=95)

    def test_conversion_rate_criteria(self):
        cfg = ABTestConfig(message_a="A", message_b="B", winner_criteria="conversion_rate")
        assert cfg.winner_criteria == "conversion_rate"


# ─── compute_winner ───────────────────────────────────────────────────────────

class TestComputeWinner:
    def _variant(self, name, sent, opens, conversions=0) -> ABTestVariant:
        return ABTestVariant(
            campaign_id=uuid4(),
            variant_name=name,
            message_content="msg",
            total_sent=sent,
            total_opens=opens,
            total_conversions=conversions,
        )

    def test_no_winner_below_min_sample(self):
        a = self._variant("A", sent=10, opens=8)
        b = self._variant("B", sent=10, opens=2)
        assert compute_winner(a, b, min_sample_size=50) is None

    def test_no_winner_both_zero_rates(self):
        a = self._variant("A", sent=100, opens=0)
        b = self._variant("B", sent=100, opens=0)
        assert compute_winner(a, b) is None

    def test_a_wins_open_rate(self):
        # A has 80% open rate, B has 20% — large statistically significant gap
        a = self._variant("A", sent=1000, opens=800)
        b = self._variant("B", sent=1000, opens=200)
        result = compute_winner(a, b, criteria="open_rate", min_sample_size=50)
        assert result == "A"

    def test_b_wins_open_rate(self):
        a = self._variant("A", sent=1000, opens=200)
        b = self._variant("B", sent=1000, opens=800)
        result = compute_winner(a, b, criteria="open_rate", min_sample_size=50)
        assert result == "B"

    def test_no_winner_close_rates(self):
        # Nearly equal rates — not statistically significant
        a = self._variant("A", sent=100, opens=50)
        b = self._variant("B", sent=100, opens=51)
        result = compute_winner(a, b, min_sample_size=50)
        assert result is None

    def test_conversion_rate_a_wins(self):
        a = self._variant("A", sent=1000, opens=0, conversions=900)
        b = self._variant("B", sent=1000, opens=0, conversions=100)
        result = compute_winner(a, b, criteria="conversion_rate", min_sample_size=50)
        assert result == "A"

    def test_conversion_rate_b_wins(self):
        a = self._variant("A", sent=1000, opens=0, conversions=100)
        b = self._variant("B", sent=1000, opens=0, conversions=900)
        result = compute_winner(a, b, criteria="conversion_rate", min_sample_size=50)
        assert result == "B"

    def test_no_winner_when_b_below_min(self):
        a = self._variant("A", sent=200, opens=160)
        b = self._variant("B", sent=40, opens=4)   # below min_sample_size=50
        assert compute_winner(a, b, min_sample_size=50) is None

    def test_100_percent_pool_returns_none(self):
        a = self._variant("A", sent=100, opens=100)
        b = self._variant("B", sent=100, opens=100)
        result = compute_winner(a, b, min_sample_size=50)
        assert result is None  # p_pool == 1 → None


# ─── ABTestService (mocked) ───────────────────────────────────────────────────

class TestABTestService:
    @pytest.fixture
    def mock_session(self):
        return AsyncMock()

    @pytest.fixture
    def tenant_id(self):
        return uuid4()

    @pytest.mark.asyncio
    async def test_launch_raises_for_missing_campaign(self, mock_session, tenant_id):
        from src.modules.campaigns.application.ab_test_service import ABTestService
        from src.modules.campaigns.domain.ab_test import ABTestConfig

        svc = ABTestService(mock_session, tenant_id)

        # Mock session.execute to return no campaign
        execute_result = AsyncMock()
        execute_result.scalar_one_or_none = MagicMock(return_value=None)
        mock_session.execute = AsyncMock(return_value=execute_result)

        cfg = ABTestConfig(message_a="Hi A", message_b="Hi B")
        with pytest.raises(ValueError, match="not found"):
            await svc.launch(uuid4(), cfg)

    @pytest.mark.asyncio
    async def test_get_results_returns_error_for_missing_campaign(self, mock_session, tenant_id):
        from src.modules.campaigns.application.ab_test_service import ABTestService

        svc = ABTestService(mock_session, tenant_id)

        execute_result = AsyncMock()
        execute_result.scalar_one_or_none = MagicMock(return_value=None)
        mock_session.execute = AsyncMock(return_value=execute_result)

        result = await svc.get_results(uuid4())
        assert "error" in result

    @pytest.mark.asyncio
    async def test_record_event_returns_none_for_missing_campaign(self, mock_session, tenant_id):
        from src.modules.campaigns.application.ab_test_service import ABTestService

        svc = ABTestService(mock_session, tenant_id)

        execute_result = AsyncMock()
        execute_result.scalar_one_or_none = MagicMock(return_value=None)
        mock_session.execute = AsyncMock(return_value=execute_result)

        result = await svc.record_event(uuid4(), "A", "open")
        assert result is None



