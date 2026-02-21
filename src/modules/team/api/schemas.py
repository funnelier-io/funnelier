"""
Team API Schemas

Pydantic schemas for team/salesperson management.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


# ============================================================================
# Salesperson Schemas
# ============================================================================

class SalespersonBase(BaseModel):
    """Base schema for salesperson."""
    name: str
    phone_number: str
    email: str | None = None
    role: str = "salesperson"  # salesperson, team_lead, manager
    regions: list[str] = Field(default_factory=list)
    is_active: bool = True
    max_leads: int | None = None  # Maximum leads that can be assigned
    metadata: dict[str, Any] = Field(default_factory=dict)


class CreateSalespersonRequest(SalespersonBase):
    """Schema for creating a salesperson."""
    user_id: UUID | None = None  # Link to user account if exists


class UpdateSalespersonRequest(BaseModel):
    """Schema for updating a salesperson."""
    name: str | None = None
    phone_number: str | None = None
    email: str | None = None
    role: str | None = None
    regions: list[str] | None = None
    is_active: bool | None = None
    max_leads: int | None = None
    metadata: dict[str, Any] | None = None


class SalespersonResponse(SalespersonBase):
    """Schema for salesperson response."""
    id: UUID
    tenant_id: UUID
    user_id: UUID | None = None
    assigned_leads: int = 0
    active_leads: int = 0
    created_at: datetime
    updated_at: datetime | None = None

    class Config:
        from_attributes = True


class SalespersonListResponse(BaseModel):
    """Schema for salesperson list."""
    salespeople: list[SalespersonResponse]
    total_count: int


# ============================================================================
# Performance Schemas
# ============================================================================

class PerformanceMetricsSchema(BaseModel):
    """Schema for performance metrics."""
    total_calls: int = 0
    answered_calls: int = 0
    successful_calls: int = 0
    total_call_duration: int = 0
    average_call_duration: float = 0.0
    answer_rate: float = 0.0
    success_rate: float = 0.0

    assigned_leads: int = 0
    contacted_leads: int = 0
    contact_rate: float = 0.0

    invoices_created: int = 0
    invoices_paid: int = 0
    conversion_rate: float = 0.0

    total_revenue: int = 0
    average_deal_size: int = 0


class SalespersonPerformanceResponse(BaseModel):
    """Schema for salesperson performance."""
    salesperson_id: UUID
    salesperson_name: str
    period_start: datetime
    period_end: datetime
    metrics: PerformanceMetricsSchema
    rank_by_revenue: int | None = None
    rank_by_conversions: int | None = None
    rank_by_calls: int | None = None
    trend: dict[str, Any] = Field(default_factory=dict)  # Comparison to previous period


class TeamPerformanceResponse(BaseModel):
    """Schema for team performance summary."""
    period_start: datetime
    period_end: datetime
    total_metrics: PerformanceMetricsSchema
    by_salesperson: list[SalespersonPerformanceResponse]
    top_performers: list[dict[str, Any]]
    improvement_needed: list[dict[str, Any]]


class PerformanceComparisonResponse(BaseModel):
    """Schema for comparing salesperson performances."""
    period_start: datetime
    period_end: datetime
    salespeople: list[dict[str, Any]]
    metrics_compared: list[str]


# ============================================================================
# Activity Schemas
# ============================================================================

class ActivityLogSchema(BaseModel):
    """Schema for activity log entry."""
    id: UUID
    salesperson_id: UUID
    activity_type: str  # call, sms, invoice, payment, note
    description: str
    contact_id: UUID | None = None
    contact_phone: str | None = None
    timestamp: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)


class ActivityLogListResponse(BaseModel):
    """Schema for activity log list."""
    activities: list[ActivityLogSchema]
    total_count: int
    page: int
    page_size: int


class DailyActivitySummaryResponse(BaseModel):
    """Schema for daily activity summary."""
    date: datetime
    salesperson_id: UUID
    salesperson_name: str
    calls_made: int = 0
    calls_answered: int = 0
    sms_sent: int = 0
    invoices_created: int = 0
    payments_received: int = 0
    revenue: int = 0


# ============================================================================
# Assignment Schemas
# ============================================================================

class AssignmentRuleBase(BaseModel):
    """Base schema for assignment rules."""
    name: str
    rule_type: str  # round_robin, balanced, region_based, skill_based
    is_active: bool = True
    priority: int = 0
    conditions: dict[str, Any] = Field(default_factory=dict)
    salesperson_ids: list[UUID] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class CreateAssignmentRuleRequest(AssignmentRuleBase):
    """Schema for creating an assignment rule."""
    pass


class AssignmentRuleResponse(AssignmentRuleBase):
    """Schema for assignment rule response."""
    id: UUID
    tenant_id: UUID
    leads_assigned: int = 0
    created_at: datetime
    updated_at: datetime | None = None

    class Config:
        from_attributes = True


class AssignmentRuleListResponse(BaseModel):
    """Schema for assignment rule list."""
    rules: list[AssignmentRuleResponse]
    total_count: int


# ============================================================================
# Target & Goal Schemas
# ============================================================================

class SalesTargetBase(BaseModel):
    """Base schema for sales target."""
    salesperson_id: UUID
    period_type: str  # daily, weekly, monthly, quarterly
    period_start: datetime
    period_end: datetime
    target_calls: int | None = None
    target_contacts: int | None = None
    target_conversions: int | None = None
    target_revenue: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class CreateSalesTargetRequest(SalesTargetBase):
    """Schema for creating a sales target."""
    pass


class SalesTargetResponse(SalesTargetBase):
    """Schema for sales target response."""
    id: UUID
    tenant_id: UUID
    actual_calls: int = 0
    actual_contacts: int = 0
    actual_conversions: int = 0
    actual_revenue: int = 0
    calls_achievement: float = 0.0
    contacts_achievement: float = 0.0
    conversions_achievement: float = 0.0
    revenue_achievement: float = 0.0
    created_at: datetime
    updated_at: datetime | None = None

    class Config:
        from_attributes = True


class SalesTargetListResponse(BaseModel):
    """Schema for sales target list."""
    targets: list[SalesTargetResponse]
    total_count: int


class TeamTargetSummaryResponse(BaseModel):
    """Schema for team target summary."""
    period_start: datetime
    period_end: datetime
    team_target_revenue: int
    team_actual_revenue: int
    team_achievement: float
    by_salesperson: list[dict[str, Any]]

