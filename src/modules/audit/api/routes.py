"""
Audit Trail API Routes

Endpoints for viewing audit logs and activity history.
"""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_db_session
from src.modules.auth.api.routes import require_admin, require_auth
from src.modules.auth.domain.entities import User
from src.modules.audit.infrastructure.repositories import AuditLogRepository
from src.modules.audit.domain.entities import AuditLogEntry

from .schemas import (
    AuditLogListResponse,
    AuditLogResponse,
    AuditStatsResponse,
    UserActivitySummary,
    ActionBreakdown,
)

router = APIRouter(prefix="/audit", tags=["audit"])


def _entry_to_response(entry: AuditLogEntry) -> AuditLogResponse:
    return AuditLogResponse(
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
        created_at=entry.created_at,
    )


@router.get("", response_model=AuditLogListResponse)
async def list_audit_logs(
    admin: Annotated[User, Depends(require_admin)],
    session: AsyncSession = Depends(get_db_session),
    user_id: UUID | None = Query(default=None),
    action: str | None = Query(default=None),
    resource_type: str | None = Query(default=None),
    resource_id: str | None = Query(default=None),
    start_date: datetime | None = Query(default=None),
    end_date: datetime | None = Query(default=None),
    search: str | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
):
    """List audit log entries with filters (admin only)."""
    repo = AuditLogRepository(session)
    entries, total = await repo.list(
        tenant_id=admin.tenant_id,
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        start_date=start_date,
        end_date=end_date,
        search=search,
        offset=offset,
        limit=limit,
    )
    return AuditLogListResponse(
        items=[_entry_to_response(e) for e in entries],
        total=total,
        offset=offset,
        limit=limit,
    )


@router.get("/stats", response_model=AuditStatsResponse)
async def get_audit_stats(
    admin: Annotated[User, Depends(require_admin)],
    session: AsyncSession = Depends(get_db_session),
    days: int = Query(default=30, ge=1, le=365),
):
    """Get audit activity statistics (admin only)."""
    repo = AuditLogRepository(session)

    # Total count
    _, total = await repo.list(tenant_id=admin.tenant_id, limit=0)
    user_activity = await repo.get_user_activity_summary(admin.tenant_id, days)
    action_breakdown = await repo.get_action_breakdown(admin.tenant_id, days)

    return AuditStatsResponse(
        total_entries=total,
        user_activity=[UserActivitySummary(**ua) for ua in user_activity],
        action_breakdown=[ActionBreakdown(**ab) for ab in action_breakdown],
    )


# ============================================================================
# Audit log helper — used by other modules to record actions
# ============================================================================

async def record_audit(
    session: AsyncSession,
    user: User,
    action: str,
    resource_type: str,
    description: str,
    resource_id: str | None = None,
    changes: dict | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> None:
    """
    Record an audit log entry. Call from any endpoint that modifies data.
    Non-blocking — flushes but does not commit (relies on request session).
    """
    repo = AuditLogRepository(session)
    entry = AuditLogEntry(
        tenant_id=user.tenant_id,
        user_id=user.id,
        user_name=user.full_name or user.username,
        user_role=user.role.value,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        description=description,
        changes=changes,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    await repo.add(entry)

