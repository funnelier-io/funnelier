"""
Notification Repositories

Database access for notifications and notification preferences.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Sequence
from uuid import UUID

from sqlalchemy import select, func, update, delete, desc, and_
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.database.models.notifications import (
    NotificationModel,
    NotificationPreferenceModel,
)

logger = logging.getLogger(__name__)


class NotificationRepository:
    """Repository for user notifications."""

    def __init__(self, session: AsyncSession, tenant_id: UUID):
        self.session = session
        self.tenant_id = tenant_id

    async def create(self, notification: dict[str, Any]) -> NotificationModel:
        """Create a new notification."""
        model = NotificationModel(
            tenant_id=self.tenant_id,
            user_id=notification["user_id"],
            type=notification.get("type", "system"),
            severity=notification.get("severity", "info"),
            title=notification["title"],
            body=notification.get("body"),
            source_type=notification.get("source_type"),
            source_id=notification.get("source_id"),
            is_read=False,
            metadata_json=notification.get("metadata"),
        )
        self.session.add(model)
        await self.session.flush()
        return model

    async def bulk_create(self, notifications: list[dict[str, Any]]) -> list[NotificationModel]:
        """Create multiple notifications at once."""
        models = []
        for n in notifications:
            model = NotificationModel(
                tenant_id=self.tenant_id,
                user_id=n["user_id"],
                type=n.get("type", "system"),
                severity=n.get("severity", "info"),
                title=n["title"],
                body=n.get("body"),
                source_type=n.get("source_type"),
                source_id=n.get("source_id"),
                is_read=False,
                metadata_json=n.get("metadata"),
            )
            models.append(model)
        self.session.add_all(models)
        await self.session.flush()
        return models

    async def get_by_id(self, notification_id: UUID) -> NotificationModel | None:
        """Get a notification by ID."""
        stmt = select(NotificationModel).where(
            and_(
                NotificationModel.tenant_id == self.tenant_id,
                NotificationModel.id == notification_id,
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_for_user(
        self,
        user_id: UUID,
        is_read: bool | None = None,
        notification_type: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[NotificationModel], int]:
        """List notifications for a user with optional filters."""
        base = select(NotificationModel).where(
            and_(
                NotificationModel.tenant_id == self.tenant_id,
                NotificationModel.user_id == user_id,
            )
        )
        count_base = select(func.count(NotificationModel.id)).where(
            and_(
                NotificationModel.tenant_id == self.tenant_id,
                NotificationModel.user_id == user_id,
            )
        )

        if is_read is not None:
            base = base.where(NotificationModel.is_read == is_read)
            count_base = count_base.where(NotificationModel.is_read == is_read)

        if notification_type:
            base = base.where(NotificationModel.type == notification_type)
            count_base = count_base.where(NotificationModel.type == notification_type)

        # Count
        count_result = await self.session.execute(count_base)
        total = count_result.scalar() or 0

        # Fetch
        stmt = base.order_by(desc(NotificationModel.created_at)).limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        items = list(result.scalars().all())

        return items, total

    async def count_unread(self, user_id: UUID) -> int:
        """Count unread notifications for a user."""
        stmt = select(func.count(NotificationModel.id)).where(
            and_(
                NotificationModel.tenant_id == self.tenant_id,
                NotificationModel.user_id == user_id,
                NotificationModel.is_read == False,
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    async def mark_read(self, notification_id: UUID, user_id: UUID) -> bool:
        """Mark a single notification as read."""
        now = datetime.now(timezone.utc)
        stmt = (
            update(NotificationModel)
            .where(
                and_(
                    NotificationModel.tenant_id == self.tenant_id,
                    NotificationModel.id == notification_id,
                    NotificationModel.user_id == user_id,
                )
            )
            .values(is_read=True, read_at=now)
        )
        result = await self.session.execute(stmt)
        return result.rowcount > 0

    async def mark_all_read(self, user_id: UUID) -> int:
        """Mark all notifications as read for a user. Returns count updated."""
        now = datetime.now(timezone.utc)
        stmt = (
            update(NotificationModel)
            .where(
                and_(
                    NotificationModel.tenant_id == self.tenant_id,
                    NotificationModel.user_id == user_id,
                    NotificationModel.is_read == False,
                )
            )
            .values(is_read=True, read_at=now)
        )
        result = await self.session.execute(stmt)
        return result.rowcount

    async def delete_notification(self, notification_id: UUID, user_id: UUID) -> bool:
        """Delete a notification."""
        stmt = delete(NotificationModel).where(
            and_(
                NotificationModel.tenant_id == self.tenant_id,
                NotificationModel.id == notification_id,
                NotificationModel.user_id == user_id,
            )
        )
        result = await self.session.execute(stmt)
        return result.rowcount > 0

    async def purge_old(self, days: int = 90) -> int:
        """Delete notifications older than N days."""
        cutoff = datetime.now(timezone.utc) - __import__("datetime").timedelta(days=days)
        stmt = delete(NotificationModel).where(
            and_(
                NotificationModel.tenant_id == self.tenant_id,
                NotificationModel.created_at < cutoff,
            )
        )
        result = await self.session.execute(stmt)
        return result.rowcount


class NotificationPreferenceRepository:
    """Repository for notification preferences."""

    def __init__(self, session: AsyncSession, tenant_id: UUID):
        self.session = session
        self.tenant_id = tenant_id

    async def get_or_create(self, user_id: UUID) -> NotificationPreferenceModel:
        """Get existing preferences or create defaults."""
        stmt = select(NotificationPreferenceModel).where(
            and_(
                NotificationPreferenceModel.tenant_id == self.tenant_id,
                NotificationPreferenceModel.user_id == user_id,
            )
        )
        result = await self.session.execute(stmt)
        pref = result.scalar_one_or_none()

        if pref is None:
            pref = NotificationPreferenceModel(
                tenant_id=self.tenant_id,
                user_id=user_id,
                in_app_enabled=True,
                email_enabled=False,
                sms_enabled=False,
                push_enabled=False,
                disabled_types=[],
            )
            self.session.add(pref)
            await self.session.flush()

        return pref

    async def update(self, user_id: UUID, data: dict[str, Any]) -> NotificationPreferenceModel:
        """Update notification preferences for a user."""
        pref = await self.get_or_create(user_id)

        for key in [
            "in_app_enabled", "email_enabled", "sms_enabled", "push_enabled",
            "quiet_hours_start", "quiet_hours_end", "disabled_types",
            "push_subscription",
        ]:
            if key in data:
                setattr(pref, key, data[key])

        await self.session.flush()
        return pref

    async def get_users_for_notification(
        self,
        notification_type: str,
        user_ids: list[UUID],
    ) -> list[UUID]:
        """
        Filter user_ids to those who have in_app_enabled and haven't muted this type.
        """
        if not user_ids:
            return []

        stmt = select(NotificationPreferenceModel).where(
            and_(
                NotificationPreferenceModel.tenant_id == self.tenant_id,
                NotificationPreferenceModel.user_id.in_(user_ids),
                NotificationPreferenceModel.in_app_enabled == True,
            )
        )
        result = await self.session.execute(stmt)
        prefs = result.scalars().all()

        # Users with preferences — check disabled_types
        enabled_users = set()
        users_with_prefs = set()
        for p in prefs:
            users_with_prefs.add(p.user_id)
            disabled = p.disabled_types or []
            if notification_type not in disabled:
                enabled_users.add(p.user_id)

        # Users without preferences get notifications by default
        users_without_prefs = set(user_ids) - users_with_prefs
        enabled_users.update(users_without_prefs)

        return list(enabled_users)

