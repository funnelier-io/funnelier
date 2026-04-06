"""
Export & Reporting — Domain Schemas

Pydantic models for export request/response types.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


# ── Enums ────────────────────────────────────────────────────────────────

class ExportFormat(str, Enum):
    csv = "csv"
    xlsx = "xlsx"
    pdf = "pdf"


class ReportType(str, Enum):
    funnel_summary = "funnel_summary"
    team_performance = "team_performance"
    rfm_breakdown = "rfm_breakdown"
    contacts = "contacts"
    invoices = "invoices"
    call_logs = "call_logs"
    sms_logs = "sms_logs"
    payments = "payments"
    campaign_results = "campaign_results"
    custom = "custom"


class ScheduleFrequency(str, Enum):
    daily = "daily"
    weekly = "weekly"
    monthly = "monthly"


# ── Request Schemas ──────────────────────────────────────────────────────

class ExportRequest(BaseModel):
    """Generic data export request."""
    report_type: ReportType
    format: ExportFormat = ExportFormat.xlsx
    start_date: date | None = None
    end_date: date | None = None
    filters: dict[str, Any] = Field(default_factory=dict)
    columns: list[str] | None = None  # None = all columns


class ScheduledReportRequest(BaseModel):
    """Create / update a scheduled report."""
    name: str = Field(..., min_length=1, max_length=255)
    report_type: ReportType
    format: ExportFormat = ExportFormat.xlsx
    frequency: ScheduleFrequency = ScheduleFrequency.weekly
    recipients: list[str] = Field(default_factory=list, description="Email addresses")
    filters: dict[str, Any] = Field(default_factory=dict)
    columns: list[str] | None = None
    is_active: bool = True


class CustomReportRequest(BaseModel):
    """Build a custom report with arbitrary column selection."""
    name: str = Field(..., min_length=1, max_length=255)
    data_sources: list[ReportType] = Field(..., min_length=1)
    format: ExportFormat = ExportFormat.xlsx
    start_date: date | None = None
    end_date: date | None = None
    filters: dict[str, Any] = Field(default_factory=dict)
    columns: dict[str, list[str]] = Field(
        default_factory=dict,
        description="Per-source column selection, e.g. {'contacts': ['name','phone_number']}"
    )
    group_by: str | None = None
    order_by: str | None = None


# ── Response Schemas ─────────────────────────────────────────────────────

class ExportJobResponse(BaseModel):
    """Returned immediately — client polls or receives file URL."""
    job_id: str
    status: str = "processing"
    message: str = "Export started"
    download_url: str | None = None


class ExportFileResponse(BaseModel):
    """After file is ready."""
    job_id: str
    status: str = "completed"
    filename: str
    download_url: str
    file_size: int = 0
    row_count: int = 0
    created_at: datetime


class ScheduledReportResponse(BaseModel):
    id: UUID
    name: str
    report_type: str
    format: str
    frequency: str
    recipients: list[str]
    filters: dict[str, Any]
    columns: list[str] | None
    is_active: bool
    last_run_at: datetime | None = None
    next_run_at: datetime | None = None
    created_at: datetime


class ScheduledReportListResponse(BaseModel):
    items: list[ScheduledReportResponse]
    total: int


class ReportColumnInfo(BaseModel):
    """Describes an available column for a report type."""
    key: str
    label: str
    label_fa: str
    type: str = "string"  # string, number, date, boolean


class AvailableColumnsResponse(BaseModel):
    """Per-report-type available columns."""
    report_type: str
    columns: list[ReportColumnInfo]

