"""
Analytics API Schemas

Pydantic models for API request/response validation.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


# Funnel Metrics Schemas

class StageCountSchema(BaseModel):
    """Stage count in funnel."""

    stage: str
    count: int
    percentage: float = 0.0


class ConversionRateSchema(BaseModel):
    """Conversion rate between stages."""

    from_stage: str
    to_stage: str
    rate: float


class FunnelMetricsResponse(BaseModel):
    """Response for funnel metrics endpoint."""

    period_start: datetime
    period_end: datetime
    tenant_id: UUID

    # Stage data
    stage_counts: list[StageCountSchema]
    conversion_rates: list[ConversionRateSchema]

    # Summary
    total_leads: int
    total_conversions: int
    overall_conversion_rate: float
    average_days_to_convert: float | None = None

    # Revenue
    total_revenue: int = 0
    average_order_value: int = 0

    # Comparison
    leads_change_percent: float | None = None
    conversions_change_percent: float | None = None
    revenue_change_percent: float | None = None


class DailySnapshotSchema(BaseModel):
    """Daily funnel snapshot."""

    date: datetime
    new_leads: int
    new_conversions: int
    daily_revenue: int
    conversion_rate: float


class FunnelTrendResponse(BaseModel):
    """Response for funnel trend endpoint."""

    period_start: datetime
    period_end: datetime
    snapshots: list[DailySnapshotSchema]


# Report Schemas

class DailyReportResponse(BaseModel):
    """Response for daily report endpoint."""

    report_date: datetime
    tenant_id: UUID

    leads: dict[str, Any]
    sms: dict[str, Any]
    calls: dict[str, Any]
    revenue: dict[str, Any]


class WeeklyReportResponse(BaseModel):
    """Response for weekly report endpoint."""

    period_start: datetime
    period_end: datetime
    tenant_id: UUID

    summary: dict[str, Any]
    overall_conversion_rate: float


# Salesperson Schemas

class SalespersonMetricsResponse(BaseModel):
    """Response for salesperson metrics."""

    salesperson_id: UUID
    salesperson_name: str

    # Activity
    total_calls: int
    answered_calls: int
    successful_calls: int
    total_call_duration: int
    average_call_duration: int

    # Performance
    assigned_leads: int
    contacted_leads: int
    contact_rate: float
    conversion_rate: float

    # Revenue
    invoices_created: int
    invoices_paid: int
    total_revenue: int

    # Ranking
    rank_by_revenue: int | None = None
    rank_by_conversions: int | None = None


class SalespersonListResponse(BaseModel):
    """Response for list of salesperson metrics."""

    period_start: datetime
    period_end: datetime
    salespeople: list[SalespersonMetricsResponse]


# Cohort Schemas

class CohortDataSchema(BaseModel):
    """Cohort analysis data."""

    cohort_date: datetime
    cohort_size: int
    conversion_by_period: dict[int, int]
    cumulative_rates: dict[int, float]


class CohortAnalysisResponse(BaseModel):
    """Response for cohort analysis endpoint."""

    cohort_type: str  # weekly, monthly
    num_cohorts: int
    cohorts: list[CohortDataSchema]


# Alert Schemas

class AlertRuleSchema(BaseModel):
    """Alert rule configuration."""

    id: UUID | None = None
    name: str
    metric_name: str
    condition: str  # above, below, change_percent
    threshold_value: float
    severity: str = "warning"
    notification_channels: list[str] = Field(default_factory=list)
    recipient_emails: list[str] = Field(default_factory=list)
    recipient_phones: list[str] = Field(default_factory=list)
    webhook_url: str | None = None
    is_active: bool = True


class AlertResponse(BaseModel):
    """Response for alert instance."""

    id: UUID
    rule_id: UUID
    rule_name: str
    triggered_at: datetime
    metric_name: str
    metric_value: float
    threshold_value: float
    severity: str
    message: str
    is_acknowledged: bool
    acknowledged_at: datetime | None = None


class AlertListResponse(BaseModel):
    """Response for list of alerts."""

    alerts: list[AlertResponse]
    total_count: int
    unacknowledged_count: int


# Optimization Schemas

class OptimizationOpportunitySchema(BaseModel):
    """Optimization opportunity."""

    type: str
    severity: str
    details: dict[str, Any]
    recommendation: str


class OptimizationResponse(BaseModel):
    """Response for optimization opportunities."""

    opportunities: list[OptimizationOpportunitySchema]
    analysis_date: datetime


# Request Schemas

class DateRangeRequest(BaseModel):
    """Request with date range."""

    start_date: datetime
    end_date: datetime


class CreateAlertRuleRequest(BaseModel):
    """Request to create alert rule."""

    name: str
    metric_name: str
    condition: str
    threshold_value: float
    severity: str = "warning"
    notification_channels: list[str] = Field(default_factory=list)
    recipient_emails: list[str] = Field(default_factory=list)
    recipient_phones: list[str] = Field(default_factory=list)
    webhook_url: str | None = None


class AcknowledgeAlertRequest(BaseModel):
    """Request to acknowledge an alert."""

    alert_id: UUID

