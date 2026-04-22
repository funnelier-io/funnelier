"""
Campaigns Module — A/B Test Domain Logic

Pure domain functions for A/B test winner determination and split logic.
"""

from __future__ import annotations

import math
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


WinnerCriteria = Literal["open_rate", "conversion_rate"]


class ABTestVariant(BaseModel):
    """Tracks live metrics for one variant of an A/B test."""

    id: UUID = Field(default_factory=uuid4)
    campaign_id: UUID
    variant_name: Literal["A", "B"]
    message_content: str
    split_percent: int = 50          # 10–90

    total_sent: int = 0
    total_opens: int = 0             # proxy: calls received
    total_conversions: int = 0

    @property
    def open_rate(self) -> float:
        return self.total_opens / self.total_sent if self.total_sent else 0.0

    @property
    def conversion_rate(self) -> float:
        return self.total_conversions / self.total_sent if self.total_sent else 0.0


class ABTestConfig(BaseModel):
    """Configuration for launching an A/B test on a campaign."""

    message_a: str
    message_b: str
    split_percent: int = Field(default=50, ge=10, le=90)
    winner_criteria: WinnerCriteria = "open_rate"
    min_sample_size: int = 50


def compute_winner(
    variant_a: ABTestVariant,
    variant_b: ABTestVariant,
    criteria: WinnerCriteria = "open_rate",
    min_sample_size: int = 50,
) -> str | None:
    """
    Return "A", "B", or None (no winner yet / tie).

    Uses a simple z-test at ~95 % confidence.  Returns None when either
    variant hasn't reached min_sample_size or the difference is not
    statistically significant.
    """
    if variant_a.total_sent < min_sample_size or variant_b.total_sent < min_sample_size:
        return None

    p_a = variant_a.open_rate if criteria == "open_rate" else variant_a.conversion_rate
    p_b = variant_b.open_rate if criteria == "open_rate" else variant_b.conversion_rate

    if p_a == 0 and p_b == 0:
        return None

    # Pooled standard error
    n_a, n_b = variant_a.total_sent, variant_b.total_sent
    p_pool = (p_a * n_a + p_b * n_b) / (n_a + n_b)

    if p_pool == 0 or p_pool == 1:
        return None

    se = math.sqrt(p_pool * (1 - p_pool) * (1 / n_a + 1 / n_b))
    if se == 0:
        return None

    z = (p_a - p_b) / se
    # |z| > 1.96 ≈ 95 % confidence
    if abs(z) < 1.96:
        return None

    return "A" if z > 0 else "B"

