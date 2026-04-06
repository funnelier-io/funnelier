"""
Notifications API Routes

Endpoints for listing, reading, and managing user notifications and preferences.
"""

from __future__ import annotations

import logging
from datetime import time as dt_time
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_current_tenant_id, get_db_session
from src.modules.auth.api.routes import require_auth, get_current_user

from .schemas import (
    CreateNotificationRequest,
    MarkReadResponse,
    NotificationListResponse,
    NotificationPreferenceResponse,
    NotificationPreferenceUpdateRequest,
    NotificationResponse,
    PushSubscriptionRequest,
    UnreadCountResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/notifications", tags=["Notifications"])


def _model_to_response(m) -> NotificationResponse:
    """Convert a NotificationModel to NotificationResponse."""
    return NotificationResponse(
        id=m.id,
        tenant_id=m.tenant_id,
        user_id=m.user_id,
        type=m.type,
        severity=m.severity,
        title=m.title,
        body=m.body,
        source_type=m.source_type,
        source_id=m.source_id,
        is_read=m.is_read,
        read_at=m.read_at,
        metadata=m.metadata_json,
        created_at=m.created_at,
    )


def _pref_to_response(p) -> NotificationPreferenceResponse:
    """Convert a NotificationPreferenceModel to response."""
    return NotificationPreferenceResponse(
        user_id=p.user_id,
        in_app_enabled=p.in_app_enabled,
        email_enabled=p.email_enabled,
        sms_enabled=p.sms_enabled,
        push_enabled=p.push_enabled,
        quiet_hours_start=p.quiet_hours_start.strftime("%H:%M") if p.quiet_hours_start else None,
        quiet_hours_end=p.quiet_hours_end.strftime("%H:%M") if p.quiet_hours_end else None,
        disabled_types=p.disabled_types or [],
    )


# ═══════════════════════════════════════════════════════════════════════
# Notification CRUD
# ═══════════════════════════════════════════════════════════════════════

@router.get("", response_model=NotificationListResponse)
async def list_notifications(
    session: AsyncSession = Depends(get_db_session),
    tenant_id: UUID = Depends(get_current_tenant_id),
    user=Depends(get_current_user),
    is_read: bool | None = Query(None),
    type: str | None = Query(None, alias="type"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """List notifications for the current user."""
    from src.modules.notifications.infrastructure.repositories import (
        NotificationRepository,
    )

    repo = NotificationRepository(session, tenant_id)
    items, total = await repo.list_for_user(
        user_id=user.id,
        is_read=is_read,
        notification_type=type,
        limit=limit,
        offset=offset,
    )
    unread = await repo.count_unread(user.id)

    return NotificationListResponse(
        items=[_model_to_response(m) for m in items],
        total=total,
        unread_count=unread,
    )


@router.get("/unread-count", response_model=UnreadCountResponse)
async def get_unread_count(
    session: AsyncSession = Depends(get_db_session),
    tenant_id: UUID = Depends(get_current_tenant_id),
    user=Depends(get_current_user),
):
    """Get the number of unread notifications."""
    from src.modules.notifications.infrastructure.repositories import (
        NotificationRepository,
    )

    repo = NotificationRepository(session, tenant_id)
    count = await repo.count_unread(user.id)
    return UnreadCountResponse(unread_count=count)


@router.post("/{notification_id}/read", response_model=MarkReadResponse)
async def mark_notification_read(
    notification_id: UUID,
    session: AsyncSession = Depends(get_db_session),
    tenant_id: UUID = Depends(get_current_tenant_id),
    user=Depends(get_current_user),
):
    """Mark a single notification as read."""
    from src.modules.notifications.infrastructure.repositories import (
        NotificationRepository,
    )

    repo = NotificationRepository(session, tenant_id)
    success = await repo.mark_read(notification_id, user.id)
    if not success:
        raise HTTPException(status_code=404, detail="Notification not found")
    return MarkReadResponse(success=True, marked_count=1)


@router.post("/read-all", response_model=MarkReadResponse)
async def mark_all_read(
    session: AsyncSession = Depends(get_db_session),
    tenant_id: UUID = Depends(get_current_tenant_id),
    user=Depends(get_current_user),
):
    """Mark all notifications as read for the current user."""
    from src.modules.notifications.infrastructure.repositories import (
        NotificationRepository,
    )

    repo = NotificationRepository(session, tenant_id)
    count = await repo.mark_all_read(user.id)
    return MarkReadResponse(success=True, marked_count=count)


@router.delete("/{notification_id}", status_code=204)
async def delete_notification(
    notification_id: UUID,
    session: AsyncSession = Depends(get_db_session),
    tenant_id: UUID = Depends(get_current_tenant_id),
    user=Depends(get_current_user),
):
    """Delete a notification."""
    from src.modules.notifications.infrastructure.repositories import (
        NotificationRepository,
    )

    repo = NotificationRepository(session, tenant_id)
    success = await repo.delete_notification(notification_id, user.id)
    if not success:
        raise HTTPException(status_code=404, detail="Notification not found")


# ═══════════════════════════════════════════════════════════════════════
# Admin: Create notification (broadcast to users)
# ═══════════════════════════════════════════════════════════════════════

@router.post("", response_model=NotificationResponse, status_code=201)
async def create_notification(
    body: CreateNotificationRequest,
    session: AsyncSession = Depends(get_db_session),
    tenant_id: UUID = Depends(get_current_tenant_id),
    user=Depends(get_current_user),
):
    """Create a notification. If user_id is omitted, sends to all admins/managers."""
    from src.modules.notifications.infrastructure.repositories import (
        NotificationRepository,
    )

    repo = NotificationRepository(session, tenant_id)

    if body.user_id:
        # Direct notification to a specific user
        model = await repo.create({
            "user_id": body.user_id,
            "type": body.type,
            "severity": body.severity,
            "title": body.title,
            "body": body.body,
            "source_type": body.source_type,
            "source_id": body.source_id,
            "metadata": body.metadata,
        })
    else:
        # Send to the current user as a demo / fallback
        model = await repo.create({
            "user_id": user.id,
            "type": body.type,
            "severity": body.severity,
            "title": body.title,
            "body": body.body,
            "source_type": body.source_type,
            "source_id": body.source_id,
            "metadata": body.metadata,
        })

    # Publish to WebSocket for real-time delivery
    try:
        import json
        import redis
        from src.core.config import settings

        r = redis.from_url(settings.redis.url)
        r.publish("funnelier:ws:events", json.dumps({
            "type": "notification_new",
            "payload": {
                "tenant_id": str(tenant_id),
                "notification_id": str(model.id),
                "user_id": str(model.user_id),
                "type": model.type,
                "severity": model.severity,
                "title": model.title,
                "body": model.body,
            },
        }))
    except Exception as e:
        logger.warning(f"Failed to publish notification to WS: {e}")

    return _model_to_response(model)


# ═══════════════════════════════════════════════════════════════════════
# Preferences
# ═══════════════════════════════════════════════════════════════════════

@router.get("/preferences", response_model=NotificationPreferenceResponse)
async def get_preferences(
    session: AsyncSession = Depends(get_db_session),
    tenant_id: UUID = Depends(get_current_tenant_id),
    user=Depends(get_current_user),
):
    """Get notification preferences for the current user."""
    from src.modules.notifications.infrastructure.repositories import (
        NotificationPreferenceRepository,
    )

    repo = NotificationPreferenceRepository(session, tenant_id)
    pref = await repo.get_or_create(user.id)
    return _pref_to_response(pref)


@router.put("/preferences", response_model=NotificationPreferenceResponse)
async def update_preferences(
    body: NotificationPreferenceUpdateRequest,
    session: AsyncSession = Depends(get_db_session),
    tenant_id: UUID = Depends(get_current_tenant_id),
    user=Depends(get_current_user),
):
    """Update notification preferences."""
    from src.modules.notifications.infrastructure.repositories import (
        NotificationPreferenceRepository,
    )

    repo = NotificationPreferenceRepository(session, tenant_id)

    update_data: dict[str, Any] = {}
    for field in [
        "in_app_enabled", "email_enabled", "sms_enabled", "push_enabled",
        "disabled_types",
    ]:
        val = getattr(body, field, None)
        if val is not None:
            update_data[field] = val

    # Parse quiet hours
    if body.quiet_hours_start is not None:
        if body.quiet_hours_start:
            h, m = body.quiet_hours_start.split(":")
            update_data["quiet_hours_start"] = dt_time(int(h), int(m))
        else:
            update_data["quiet_hours_start"] = None

    if body.quiet_hours_end is not None:
        if body.quiet_hours_end:
            h, m = body.quiet_hours_end.split(":")
            update_data["quiet_hours_end"] = dt_time(int(h), int(m))
        else:
            update_data["quiet_hours_end"] = None

    pref = await repo.update(user.id, update_data)
    return _pref_to_response(pref)


# ═══════════════════════════════════════════════════════════════════════
# Web Push Subscription
# ═══════════════════════════════════════════════════════════════════════

@router.post("/push/subscribe", status_code=201)
async def subscribe_push(
    body: PushSubscriptionRequest,
    session: AsyncSession = Depends(get_db_session),
    tenant_id: UUID = Depends(get_current_tenant_id),
    user=Depends(get_current_user),
):
    """Store a Web Push subscription for the current user."""
    from src.modules.notifications.infrastructure.repositories import (
        NotificationPreferenceRepository,
    )

    repo = NotificationPreferenceRepository(session, tenant_id)
    await repo.update(user.id, {
        "push_enabled": True,
        "push_subscription": {
            "endpoint": body.endpoint,
            "keys": body.keys,
        },
    })
    return {"status": "subscribed"}

