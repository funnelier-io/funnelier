"""
Notification Domain Entities
"""

from __future__ import annotations

from datetime import datetime, time
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class Notification(BaseModel):
    """A single user notification."""

    id: UUID = Field(default_factory=uuid4)
    tenant_id: UUID
    user_id: UUID
    type: str = "system"  # alert, import, campaign, system, sync, report, sms
    severity: str = "info"  # info, success, warning, error, critical
    title: str
    body: str | None = None
    source_type: str | None = None  # alert_instances, campaigns, import_logs, etc.
    source_id: UUID | None = None
    is_read: bool = False
    read_at: datetime | None = None
    metadata: dict[str, Any] | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class NotificationPreference(BaseModel):
    """Per-user notification delivery preferences."""

    id: UUID = Field(default_factory=uuid4)
    tenant_id: UUID
    user_id: UUID
    in_app_enabled: bool = True
    email_enabled: bool = False
    sms_enabled: bool = False
    push_enabled: bool = False
    quiet_hours_start: time | None = None
    quiet_hours_end: time | None = None
    disabled_types: list[str] = Field(default_factory=list)
    push_subscription: dict[str, Any] | None = None


# Notification type constants
NOTIFICATION_TYPES = [
    "alert",
    "import",
    "campaign",
    "system",
    "sync",
    "report",
    "sms",
]

SEVERITY_LEVELS = [
    "info",
    "success",
    "warning",
    "error",
    "critical",
]

# Which roles receive which notification types
NOTIFICATION_ROUTING: dict[str, list[str]] = {
    "alert": ["super_admin", "tenant_admin", "manager"],
    "import": ["super_admin", "tenant_admin", "manager"],
    "campaign": ["super_admin", "tenant_admin", "manager", "salesperson"],
    "system": ["super_admin", "tenant_admin"],
    "sync": ["super_admin", "tenant_admin"],
    "report": ["super_admin", "tenant_admin", "manager"],
    "sms": ["super_admin", "tenant_admin", "manager", "salesperson"],
}

