"""
Audit Log Repository

Persistence for audit trail entries.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.database.models.audit import AuditLogModel
from src.modules.audit.domain.entities import AuditLogEntry


class AuditLogRepository:
    """Repository for audit log entries (append-only)."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def add(self, entry: AuditLogEntry) -> AuditLogEntry:
        """Append a new audit log entry."""
        model = AuditLogModel(
            id=entry.id,
            tenant_id=entry.tenant_id,
            user_id=entry.user_id,
            user_name=entry.user_name,
            user_role=entry.user_role,
            action=entry.action,
            resource_type=entry.resource_type,
            resource_id=entry.resource_id,
            description=entry.description,
            changes=entry.changes,
            ip_address=entry.ip_address,
            user_agent=entry.user_agent,
        )
        self._session.add(model)
        await self._session.flush()
        return entry

    async def list(
        self,
        tenant_id: UUID,
        *,
        user_id: UUID | None = None,
        action: str | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        search: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[AuditLogEntry], int]:
        """List audit log entries with filters. Returns (entries, total_count)."""
        base = select(AuditLogModel).where(AuditLogModel.tenant_id == tenant_id)

        if user_id:
            base = base.where(AuditLogModel.user_id == user_id)
        if action:
            base = base.where(AuditLogModel.action == action)
        if resource_type:
            base = base.where(AuditLogModel.resource_type == resource_type)
        if resource_id:
            base = base.where(AuditLogModel.resource_id == resource_id)
        if start_date:
            base = base.where(AuditLogModel.created_at >= start_date)
        if end_date:
            base = base.where(AuditLogModel.created_at <= end_date)
        if search:
            base = base.where(AuditLogModel.description.ilike(f"%{search}%"))

        # Count
        count_stmt = select(func.count()).select_from(base.subquery())
        count_result = await self._session.execute(count_stmt)
        total = count_result.scalar_one()

        # Fetch
        stmt = base.order_by(desc(AuditLogModel.created_at)).offset(offset).limit(limit)
        result = await self._session.execute(stmt)
        entries = [self._to_entity(m) for m in result.scalars().all()]

        return entries, total

    async def get_user_activity_summary(
        self,
        tenant_id: UUID,
        days: int = 30,
    ) -> list[dict[str, Any]]:
        """Get user activity counts over the last N days."""
        since = datetime.utcnow().replace(hour=0, minute=0, second=0)
        from datetime import timedelta
        since = since - timedelta(days=days)

        stmt = (
            select(
                AuditLogModel.user_id,
                AuditLogModel.user_name,
                func.count().label("action_count"),
                func.max(AuditLogModel.created_at).label("last_action"),
            )
            .where(
                AuditLogModel.tenant_id == tenant_id,
                AuditLogModel.created_at >= since,
            )
            .group_by(AuditLogModel.user_id, AuditLogModel.user_name)
            .order_by(desc("action_count"))
        )
        result = await self._session.execute(stmt)
        return [
            {
                "user_id": str(row.user_id),
                "user_name": row.user_name,
                "action_count": row.action_count,
                "last_action": row.last_action.isoformat() if row.last_action else None,
            }
            for row in result.all()
        ]

    async def get_action_breakdown(
        self,
        tenant_id: UUID,
        days: int = 30,
    ) -> list[dict[str, Any]]:
        """Get action type breakdown over the last N days."""
        from datetime import timedelta
        since = datetime.utcnow() - timedelta(days=days)

        stmt = (
            select(
                AuditLogModel.action,
                func.count().label("count"),
            )
            .where(
                AuditLogModel.tenant_id == tenant_id,
                AuditLogModel.created_at >= since,
            )
            .group_by(AuditLogModel.action)
            .order_by(desc("count"))
        )
        result = await self._session.execute(stmt)
        return [
            {"action": row.action, "count": row.count}
            for row in result.all()
        ]

    def _to_entity(self, model: AuditLogModel) -> AuditLogEntry:
        return AuditLogEntry(
            id=model.id,
            tenant_id=model.tenant_id,
            user_id=model.user_id,
            user_name=model.user_name,
            user_role=model.user_role,
            action=model.action,
            resource_type=model.resource_type,
            resource_id=model.resource_id,
            description=model.description,
            changes=model.changes,
            ip_address=model.ip_address,
            user_agent=model.user_agent,
            created_at=model.created_at,
        )

