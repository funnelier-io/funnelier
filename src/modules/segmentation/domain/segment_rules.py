"""
Segmentation Module - Named Segment Rule Entities

A NamedSegmentRule lets tenants define custom RFM-range buckets with
a human-readable name, colour, and priority.  Rules are evaluated in
priority order; the first matching rule wins.
"""

from datetime import datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class NamedSegmentRule(BaseModel):
    """Custom RFM rule defined by a tenant."""

    id: UUID = Field(default_factory=uuid4)
    tenant_id: UUID

    name: str
    description: str | None = None
    color: str = "#6366f1"     # Tailwind indigo-500 default
    priority: int = 0          # Lower number = higher priority

    # RFM range filters (inclusive, 1-5)
    r_min: int = Field(default=1, ge=1, le=5)
    r_max: int = Field(default=5, ge=1, le=5)
    f_min: int = Field(default=1, ge=1, le=5)
    f_max: int = Field(default=5, ge=1, le=5)
    m_min: int = Field(default=1, ge=1, le=5)
    m_max: int = Field(default=5, ge=1, le=5)

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    def evaluate(self, recency: int, frequency: int, monetary: int) -> bool:
        """Return True if (R, F, M) scores fall inside this rule's ranges."""
        return (
            self.r_min <= recency <= self.r_max
            and self.f_min <= frequency <= self.f_max
            and self.m_min <= monetary <= self.m_max
        )


class SegmentRulePreview(BaseModel):
    """Preview result for a segment rule."""
    rule_id: UUID
    matching_count: int
    sample_contact_ids: list[UUID] = Field(default_factory=list)


class BulkAssignResult(BaseModel):
    """Result of bulk-assigning contacts to a named segment."""
    rule_id: UUID
    rule_name: str
    assigned_count: int

