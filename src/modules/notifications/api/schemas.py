"""
Notification API Schemas
"""

from __future__ import annotations

from datetime import datetime, time
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


# ── Response schemas ──

class NotificationResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    user_id: UUID
    type: str
    severity: str
    title: str
    body: str | None = None
    source_type: str | None = None
    source_id: UUID | None = None
    is_read: bool
    read_at: datetime | None = None
    metadata: dict[str, Any] | None = None
    created_at: datetime


class NotificationListResponse(BaseModel):
    items: list[NotificationResponse]
    total: int
    unread_count: int


class UnreadCountResponse(BaseModel):
    unread_count: int


class MarkReadResponse(BaseModel):
    success: bool
    marked_count: int = 1


# ── Preference schemas ──

class NotificationPreferenceResponse(BaseModel):
    user_id: UUID
    in_app_enabled: bool
    email_enabled: bool
    sms_enabled: bool
    push_enabled: bool
    quiet_hours_start: str | None = None  # HH:MM
    quiet_hours_end: str | None = None
    disabled_types: list[str]


class NotificationPreferenceUpdateRequest(BaseModel):
    in_app_enabled: bool | None = None
    email_enabled: bool | None = None
    sms_enabled: bool | None = None
    push_enabled: bool | None = None
    quiet_hours_start: str | None = None  # HH:MM or null
    quiet_hours_end: str | None = None
    disabled_types: list[str] | None = None


# ── Push subscription ──

class PushSubscriptionRequest(BaseModel):
    """Web Push subscription object from browser PushManager.subscribe()."""
    endpoint: str
    keys: dict[str, str]  # {p256dh, auth}


# ── Create notification (admin/internal) ──

class CreateNotificationRequest(BaseModel):
    user_id: UUID | None = None  # None = broadcast to all eligible users
    type: str = "system"
    severity: str = "info"
    title: str
    body: str | None = None
    source_type: str | None = None
    source_id: UUID | None = None
    metadata: dict[str, Any] | None = None

