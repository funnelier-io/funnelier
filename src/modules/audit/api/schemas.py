"""
Audit API Schemas
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class AuditLogResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    user_id: UUID
    user_name: str
    user_role: str
    action: str
    resource_type: str
    resource_id: str | None = None
    description: str
    changes: dict | None = None
    ip_address: str | None = None
    created_at: datetime


class AuditLogListResponse(BaseModel):
    items: list[AuditLogResponse]
    total: int
    offset: int
    limit: int


class UserActivitySummary(BaseModel):
    user_id: str
    user_name: str
    action_count: int
    last_action: str | None = None


class ActionBreakdown(BaseModel):
    action: str
    count: int


class AuditStatsResponse(BaseModel):
    total_entries: int
    user_activity: list[UserActivitySummary]
    action_breakdown: list[ActionBreakdown]

