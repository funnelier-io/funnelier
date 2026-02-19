"""
Tests for Core Domain Entities
"""

import pytest
from uuid import uuid4

from src.core.domain import PhoneNumber, Money, FunnelStage


class TestPhoneNumber:
    """Tests for PhoneNumber value object."""

    def test_from_international_format(self):
        """Test parsing international format (+98XXXXXXXXXX)."""
        phone = PhoneNumber.from_string("+989123456789")

        assert phone.number == "9123456789"
        assert phone.country_code == "98"
        assert phone.full_number == "+989123456789"
        assert phone.local_format == "09123456789"

    def test_from_local_format(self):
        """Test parsing local format (0XXXXXXXXXX)."""
        phone = PhoneNumber.from_string("09123456789")

        assert phone.number == "9123456789"
        assert phone.local_format == "09123456789"

    def test_from_raw_format(self):
        """Test parsing raw format (XXXXXXXXXX)."""
        phone = PhoneNumber.from_string("9123456789")

        assert phone.number == "9123456789"
        assert phone.normalized == "9123456789"

    def test_with_special_characters(self):
        """Test parsing phone with special characters."""
        phone = PhoneNumber.from_string("+98 912-345-6789")

        assert phone.number == "9123456789"

    def test_equality(self):
        """Test phone number equality."""
        phone1 = PhoneNumber.from_string("+989123456789")
        phone2 = PhoneNumber.from_string("09123456789")

        assert phone1.normalized == phone2.normalized


class TestMoney:
    """Tests for Money value object."""

    def test_create_in_rial(self):
        """Test creating money in Rial."""
        money = Money(amount=1_000_000_000)

        assert money.amount == 1_000_000_000
        assert money.currency == "IRR"
        assert money.in_toman == 100_000_000

    def test_from_toman(self):
        """Test creating money from Toman."""
        money = Money.from_toman(100_000_000)

        assert money.amount == 1_000_000_000
        assert money.in_toman == 100_000_000

    def test_string_representation(self):
        """Test money string representation."""
        money = Money(amount=1_000_000)

        assert "1,000,000" in str(money)
        assert "IRR" in str(money)


class TestFunnelStage:
    """Tests for FunnelStage enum."""

    def test_stage_order(self):
        """Test that stages are in correct order."""
        stages = FunnelStage.get_order()

        assert stages[0] == FunnelStage.LEAD_ACQUIRED
        assert stages[-1] == FunnelStage.PAYMENT_RECEIVED
        assert len(stages) == 7

    def test_stage_number(self):
        """Test stage number property."""
        assert FunnelStage.LEAD_ACQUIRED.stage_number == 1
        assert FunnelStage.SMS_SENT.stage_number == 2
        assert FunnelStage.PAYMENT_RECEIVED.stage_number == 7

    def test_stage_progression(self):
        """Test that stages progress correctly."""
        stages = FunnelStage.get_order()

        for i in range(len(stages) - 1):
            current = stages[i]
            next_stage = stages[i + 1]
            assert current.stage_number < next_stage.stage_number

