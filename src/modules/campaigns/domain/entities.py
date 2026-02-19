"""
Campaigns Module - Domain Layer
Campaign management for SMS marketing
"""

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import Field

from src.core.domain import CampaignStatus, TenantAggregateRoot, TenantEntity


class Campaign(TenantAggregateRoot[UUID]):
    """
    SMS marketing campaign.
    """

    id: UUID = Field(default_factory=uuid4)
    name: str
    description: str | None = None

    # Template
    template_id: UUID | None = None
    message_content: str

    # Targeting
    target_segment: str | None = None  # RFM segment
    target_category_id: UUID | None = None
    target_filters: dict[str, Any] = Field(default_factory=dict)

    # Recipients
    total_recipients: int = 0
    recipient_ids: list[UUID] = Field(default_factory=list)

    # Schedule
    scheduled_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None

    # Status
    status: CampaignStatus = CampaignStatus.DRAFT

    # Results
    total_sent: int = 0
    total_delivered: int = 0
    total_failed: int = 0
    total_calls_received: int = 0
    total_conversions: int = 0
    total_revenue: int = 0

    # A/B Testing
    is_ab_test: bool = False
    variant_name: str | None = None
    parent_campaign_id: UUID | None = None

    # Cost tracking
    estimated_cost: int = 0
    actual_cost: int = 0

    created_by: UUID | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def delivery_rate(self) -> float:
        """Calculate delivery rate."""
        if self.total_sent == 0:
            return 0.0
        return self.total_delivered / self.total_sent

    @property
    def response_rate(self) -> float:
        """Calculate response rate (calls received)."""
        if self.total_delivered == 0:
            return 0.0
        return self.total_calls_received / self.total_delivered

    @property
    def conversion_rate(self) -> float:
        """Calculate conversion rate."""
        if self.total_delivered == 0:
            return 0.0
        return self.total_conversions / self.total_delivered

    @property
    def roi(self) -> float:
        """Calculate return on investment."""
        if self.actual_cost == 0:
            return 0.0
        return (self.total_revenue - self.actual_cost) / self.actual_cost

    def start(self) -> None:
        """Start the campaign."""
        if self.status not in [CampaignStatus.DRAFT, CampaignStatus.SCHEDULED]:
            raise ValueError(f"Cannot start campaign in status {self.status}")

        self.status = CampaignStatus.RUNNING
        self.started_at = datetime.utcnow()

    def pause(self) -> None:
        """Pause the campaign."""
        if self.status != CampaignStatus.RUNNING:
            raise ValueError("Can only pause running campaigns")

        self.status = CampaignStatus.PAUSED

    def resume(self) -> None:
        """Resume a paused campaign."""
        if self.status != CampaignStatus.PAUSED:
            raise ValueError("Can only resume paused campaigns")

        self.status = CampaignStatus.RUNNING

    def complete(self) -> None:
        """Mark campaign as completed."""
        self.status = CampaignStatus.COMPLETED
        self.completed_at = datetime.utcnow()

    def cancel(self) -> None:
        """Cancel the campaign."""
        if self.status == CampaignStatus.COMPLETED:
            raise ValueError("Cannot cancel completed campaigns")

        self.status = CampaignStatus.CANCELLED

    def record_send(self, delivered: bool = False, failed: bool = False) -> None:
        """Record an SMS send."""
        self.total_sent += 1
        if delivered:
            self.total_delivered += 1
        if failed:
            self.total_failed += 1

    def record_response(self) -> None:
        """Record a response (call received)."""
        self.total_calls_received += 1

    def record_conversion(self, revenue: int = 0) -> None:
        """Record a conversion."""
        self.total_conversions += 1
        self.total_revenue += revenue


class CampaignSchedule(TenantEntity[UUID]):
    """
    Recurring campaign schedule.
    """

    id: UUID = Field(default_factory=uuid4)
    name: str

    # Template for creating campaigns
    campaign_template: dict[str, Any] = Field(default_factory=dict)

    # Schedule (cron expression)
    cron_expression: str
    timezone: str = "Asia/Tehran"

    # State
    is_active: bool = True
    last_run_at: datetime | None = None
    next_run_at: datetime | None = None

    # Stats
    total_campaigns_created: int = 0

    metadata: dict[str, Any] = Field(default_factory=dict)

