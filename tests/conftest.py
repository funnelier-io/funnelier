"""
Test configuration and fixtures
"""

import pytest
from uuid import uuid4


@pytest.fixture
def tenant_id():
    """Generate a test tenant ID."""
    return uuid4()


@pytest.fixture
def sample_phone_numbers():
    """Sample Iranian phone numbers for testing."""
    return [
        "9123456789",
        "9351234567",
        "9901234567",
        "9121234567",
    ]


@pytest.fixture
def sample_rfm_data():
    """Sample RFM data for testing."""
    return {
        "champions": {
            "days_since_purchase": 2,
            "total_purchases": 15,
            "total_spend": 2_000_000_000,
        },
        "loyal": {
            "days_since_purchase": 10,
            "total_purchases": 8,
            "total_spend": 800_000_000,
        },
        "at_risk": {
            "days_since_purchase": 45,
            "total_purchases": 12,
            "total_spend": 1_200_000_000,
        },
        "lost": {
            "days_since_purchase": 120,
            "total_purchases": 1,
            "total_spend": 20_000_000,
        },
    }

