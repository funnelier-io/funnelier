"""
Analytics Module - Domain Layer
Funnel tracking and metrics calculation
"""

from datetime import datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from src.core.domain import FunnelStage, Percentage, TenantEntity


class FunnelStageConfig(TenantEntity[UUID]):
    """
    Custom funnel stage configuration per tenant.
    """

    id: UUID = Field(default_factory=uuid4)
    name: str
    display_name: str
    description: str | None = None
    order: int  # Stage position in funnel

    # Stage criteria
    criteria_type: str  # event_based, threshold_based, manual
    criteria_config: dict[str, Any] = Field(default_factory=dict)

    # For threshold-based stages
    min_value: float | None = None
    value_field: str | None = None  # e.g., "call_duration"

    color: str | None = None
    is_active: bool = True


class ContactFunnelProgress(TenantEntity[UUID]):
    """
    Tracks a contact's progress through the funnel.
    """

    id: UUID = Field(default_factory=uuid4)
    contact_id: UUID
    phone_number: str

    # Current state
    current_stage: FunnelStage = FunnelStage.LEAD_ACQUIRED
    current_stage_entered_at: datetime = Field(default_factory=datetime.utcnow)

    # Stage history
    stage_history: list[dict[str, Any]] = Field(default_factory=list)
    # Each entry: {stage, entered_at, exited_at, duration_seconds}

    # Attribution
    source_name: str | None = None
    campaign_id: UUID | None = None
    salesperson_id: UUID | None = None

    # Conversion tracking
    is_converted: bool = False
    converted_at: datetime | None = None
    conversion_value: int = 0  # Total value in Rial
    days_to_convert: int | None = None

    # Metrics
    total_sms_received: int = 0
    total_calls: int = 0
    total_answered_calls: int = 0

    def progress_to_stage(self, new_stage: FunnelStage) -> None:
        """Move contact to a new stage."""
        now = datetime.utcnow()

        # Record exit from current stage
        if self.stage_history:
            self.stage_history[-1]["exited_at"] = now.isoformat()
            entered_at = datetime.fromisoformat(
                self.stage_history[-1]["entered_at"]
            )
            self.stage_history[-1]["duration_seconds"] = int(
                (now - entered_at).total_seconds()
            )

        # Record entry to new stage
        self.stage_history.append({
            "stage": new_stage.value,
            "entered_at": now.isoformat(),
            "exited_at": None,
            "duration_seconds": None,
        })

        self.current_stage = new_stage
        self.current_stage_entered_at = now

        # Check for conversion
        if new_stage == FunnelStage.PAYMENT_RECEIVED:
            self.is_converted = True
            self.converted_at = now
            if self.stage_history:
                first_entry = datetime.fromisoformat(
                    self.stage_history[0]["entered_at"]
                )
                self.days_to_convert = (now - first_entry).days

    def get_stage_duration(self, stage: FunnelStage) -> int | None:
        """Get time spent in a specific stage (seconds)."""
        for entry in self.stage_history:
            if entry["stage"] == stage.value:
                return entry.get("duration_seconds")
        return None


class FunnelMetrics(BaseModel):
    """
    Funnel metrics for a time period.
    """

    # Period
    period_start: datetime
    period_end: datetime
    tenant_id: UUID

    # Stage counts
    stage_counts: dict[str, int] = Field(default_factory=dict)
    # e.g., {"lead_acquired": 1000, "sms_sent": 800, ...}

    # Conversion rates between stages
    stage_conversion_rates: dict[str, float] = Field(default_factory=dict)
    # e.g., {"lead_to_sms": 0.8, "sms_to_call": 0.3, ...}

    # Overall metrics
    total_leads: int = 0
    total_conversions: int = 0
    overall_conversion_rate: float = 0.0

    # Average time in funnel
    average_days_to_convert: float | None = None

    # Revenue metrics
    total_revenue: int = 0
    average_order_value: int = 0

    # Comparison to previous period
    leads_change_percent: float | None = None
    conversions_change_percent: float | None = None
    revenue_change_percent: float | None = None

    def calculate_conversion_rates(self) -> None:
        """Calculate conversion rates between stages."""
        stages = FunnelStage.get_order()

        for i in range(len(stages) - 1):
            current_stage = stages[i]
            next_stage = stages[i + 1]

            current_count = self.stage_counts.get(current_stage.value, 0)
            next_count = self.stage_counts.get(next_stage.value, 0)

            if current_count > 0:
                rate = next_count / current_count
            else:
                rate = 0.0

            key = f"{current_stage.value}_to_{next_stage.value}"
            self.stage_conversion_rates[key] = rate

        # Overall conversion rate
        if self.total_leads > 0:
            self.overall_conversion_rate = self.total_conversions / self.total_leads


class DailyFunnelSnapshot(TenantEntity[UUID]):
    """
    Daily snapshot of funnel metrics.
    Used for historical analysis and trend detection.
    """

    id: UUID = Field(default_factory=uuid4)
    snapshot_date: datetime

    # Stage counts at end of day
    stage_counts: dict[str, int] = Field(default_factory=dict)

    # Daily movements
    new_leads: int = 0
    new_conversions: int = 0

    # Stage transitions
    stage_transitions: dict[str, int] = Field(default_factory=dict)
    # e.g., {"lead_acquired_to_sms_sent": 50, ...}

    # Revenue
    daily_revenue: int = 0

    # Calculated metrics
    conversion_rate: float = 0.0
    average_order_value: int = 0


class CohortAnalysis(BaseModel):
    """
    Cohort analysis results.
    Groups contacts by acquisition date and tracks conversion over time.
    """

    cohort_date: datetime  # Week or month start
    cohort_size: int
    tenant_id: UUID

    # Conversion by day/week since acquisition
    conversion_by_period: dict[int, int] = Field(default_factory=dict)
    # e.g., {0: 10, 7: 25, 14: 35, ...} - days since acquisition

    # Cumulative conversion rates
    cumulative_conversion_rates: dict[int, float] = Field(default_factory=dict)

    # Revenue by period
    revenue_by_period: dict[int, int] = Field(default_factory=dict)


class SalespersonMetrics(BaseModel):
    """
    Metrics for a salesperson.
    """

    salesperson_id: UUID
    salesperson_name: str
    tenant_id: UUID

    # Period
    period_start: datetime
    period_end: datetime

    # Activity
    total_calls: int = 0
    answered_calls: int = 0
    total_call_duration: int = 0  # seconds
    average_call_duration: int = 0

    # Leads
    assigned_leads: int = 0
    contacted_leads: int = 0

    # Conversions
    invoices_created: int = 0
    invoices_paid: int = 0
    total_revenue: int = 0

    # Rates
    contact_rate: float = 0.0  # contacted / assigned
    conversion_rate: float = 0.0  # paid / contacted

    # Ranking
    rank_by_revenue: int | None = None
    rank_by_conversions: int | None = None


class AlertRule(TenantEntity[UUID]):
    """
    Alert rule for metric monitoring.
    """

    id: UUID = Field(default_factory=uuid4)
    name: str
    description: str | None = None

    # Metric to monitor
    metric_name: str  # conversion_rate, daily_leads, etc.

    # Condition
    condition: str  # above, below, change_percent
    threshold_value: float
    comparison_period: str | None = None  # previous_day, previous_week

    # Alert configuration
    severity: str = "warning"  # info, warning, critical
    notification_channels: list[str] = Field(default_factory=list)
    # e.g., ["email", "sms", "webhook"]

    # Recipients
    recipient_emails: list[str] = Field(default_factory=list)
    recipient_phones: list[str] = Field(default_factory=list)
    webhook_url: str | None = None

    # State
    is_active: bool = True
    last_triggered_at: datetime | None = None
    trigger_count: int = 0


class AlertInstance(TenantEntity[UUID]):
    """
    Instance of a triggered alert.
    """

    id: UUID = Field(default_factory=uuid4)
    rule_id: UUID
    rule_name: str

    # Trigger details
    triggered_at: datetime = Field(default_factory=datetime.utcnow)
    metric_name: str
    metric_value: float
    threshold_value: float

    # Status
    severity: str
    message: str
    is_acknowledged: bool = False
    acknowledged_at: datetime | None = None
    acknowledged_by: UUID | None = None

    # Notification status
    notifications_sent: list[dict[str, Any]] = Field(default_factory=list)

