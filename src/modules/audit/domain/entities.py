"""Audit domain entities and constants."""

from datetime import datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


# ============================================================================
# Action types
# ============================================================================
ACTION_TYPES = [
    "create",
    "update",
    "delete",
    "login",
    "logout",
    "import",
    "export",
    "approve",
    "reject",
    "activate",
    "deactivate",
    "role_change",
    "password_reset",
    "password_change",
    "sync",
    "send_sms",
    "send_bulk_sms",
    "campaign_start",
    "campaign_pause",
    "alert_acknowledge",
]

# ============================================================================
# Resource types
# ============================================================================
RESOURCE_TYPES = [
    "user",
    "contact",
    "campaign",
    "invoice",
    "payment",
    "product",
    "sms_template",
    "sms_log",
    "call_log",
    "import_job",
    "report",
    "alert_rule",
    "alert",
    "notification",
    "data_source",
    "setting",
    "tenant",
]


class AuditLogEntry(BaseModel):
    """Domain entity for an audit log entry."""
    id: UUID = Field(default_factory=uuid4)
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
    user_agent: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

