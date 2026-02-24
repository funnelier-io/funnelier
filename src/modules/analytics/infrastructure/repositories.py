"""
Analytics Module - Repository Implementations
Concrete SQLAlchemy repositories for funnel snapshots, alerts, and import logs.
"""

from datetime import datetime, date
from typing import Any
from uuid import UUID

from sqlalchemy import select, func, update as sa_update

from src.infrastructure.database.repositories import SqlAlchemyRepository
from src.infrastructure.database.models.analytics import (
    FunnelSnapshotModel,
    AlertRuleModel,
    AlertInstanceModel,
)
from src.infrastructure.database.models.etl import ImportLogModel


class FunnelSnapshotRepository:
    """Repository for funnel snapshots — persists and queries daily snapshots."""

    def __init__(self, session, tenant_id: UUID):
        self._session = session
        self._tenant_id = tenant_id

    async def save(self, snapshot) -> None:
        """Upsert a daily funnel snapshot."""
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        snapshot_date = snapshot.snapshot_date
        if isinstance(snapshot_date, datetime):
            snapshot_date = snapshot_date.date()

        values = {
            "tenant_id": self._tenant_id,
            "snapshot_date": snapshot_date,
            "stage_counts": getattr(snapshot, "stage_counts", {}),
            "new_leads": getattr(snapshot, "new_leads", 0),
            "new_sms_sent": getattr(snapshot, "new_sms_sent", 0),
            "new_sms_delivered": getattr(snapshot, "new_sms_delivered", 0),
            "new_calls": getattr(snapshot, "new_calls", 0),
            "new_answered_calls": getattr(snapshot, "new_answered_calls", 0),
            "new_successful_calls": getattr(snapshot, "new_successful_calls", 0),
            "new_invoices": getattr(snapshot, "new_invoices", 0),
            "new_payments": getattr(snapshot, "new_payments", 0),
            "new_conversions": getattr(snapshot, "new_conversions", 0),
            "daily_revenue": getattr(snapshot, "daily_revenue", 0),
            "conversion_rates": getattr(snapshot, "conversion_rates", {}),
            "overall_conversion_rate": getattr(snapshot, "conversion_rate", 0.0),
            "stage_transitions": getattr(snapshot, "stage_transitions", []),
        }

        # Try upsert
        stmt = pg_insert(FunnelSnapshotModel).values(**values)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_funnel_snapshot_tenant_date",
            set_={k: v for k, v in values.items() if k not in ("tenant_id", "snapshot_date")},
        )
        await self._session.execute(stmt)
        await self._session.flush()

    async def get_snapshots(
        self,
        tenant_id: UUID | None = None,
        start_date: datetime | date | None = None,
        end_date: datetime | date | None = None,
    ) -> list[dict]:
        """Get snapshots within a date range."""
        tid = tenant_id or self._tenant_id
        stmt = (
            select(FunnelSnapshotModel)
            .where(FunnelSnapshotModel.tenant_id == tid)
            .order_by(FunnelSnapshotModel.snapshot_date.asc())
        )
        if start_date:
            d = start_date.date() if isinstance(start_date, datetime) else start_date
            stmt = stmt.where(FunnelSnapshotModel.snapshot_date >= d)
        if end_date:
            d = end_date.date() if isinstance(end_date, datetime) else end_date
            stmt = stmt.where(FunnelSnapshotModel.snapshot_date <= d)
        result = await self._session.execute(stmt)
        snapshots = []
        for m in result.scalars().all():
            snapshots.append({
                "id": m.id,
                "snapshot_date": m.snapshot_date,
                "stage_counts": m.stage_counts or {},
                "new_leads": m.new_leads,
                "new_conversions": m.new_conversions,
                "daily_revenue": m.daily_revenue,
                "overall_conversion_rate": m.overall_conversion_rate,
                "conversion_rates": m.conversion_rates or {},
                "new_sms_sent": m.new_sms_sent,
                "new_calls": m.new_calls,
                "new_answered_calls": m.new_answered_calls,
            })
        return snapshots

    async def get_latest(self, tenant_id: UUID | None = None) -> dict | None:
        """Get the most recent snapshot."""
        tid = tenant_id or self._tenant_id
        stmt = (
            select(FunnelSnapshotModel)
            .where(FunnelSnapshotModel.tenant_id == tid)
            .order_by(FunnelSnapshotModel.snapshot_date.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        m = result.scalar_one_or_none()
        if not m:
            return None
        return {
            "id": m.id,
            "snapshot_date": m.snapshot_date,
            "stage_counts": m.stage_counts or {},
            "new_leads": m.new_leads,
            "new_conversions": m.new_conversions,
            "daily_revenue": m.daily_revenue,
            "overall_conversion_rate": m.overall_conversion_rate,
        }


class AlertRuleRepository:
    """Repository for alert rules."""

    def __init__(self, session, tenant_id: UUID):
        self._session = session
        self._tenant_id = tenant_id

    async def create(self, data: dict) -> AlertRuleModel:
        model = AlertRuleModel(**data, tenant_id=self._tenant_id)
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return model

    async def get_all(self, active_only: bool = False) -> list[AlertRuleModel]:
        stmt = select(AlertRuleModel).where(
            AlertRuleModel.tenant_id == self._tenant_id
        )
        if active_only:
            stmt = stmt.where(AlertRuleModel.is_active.is_(True))
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_id(self, rule_id: UUID) -> AlertRuleModel | None:
        stmt = (
            select(AlertRuleModel)
            .where(AlertRuleModel.id == rule_id)
            .where(AlertRuleModel.tenant_id == self._tenant_id)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def update(self, rule_id: UUID, data: dict) -> AlertRuleModel | None:
        stmt = (
            sa_update(AlertRuleModel)
            .where(AlertRuleModel.id == rule_id)
            .where(AlertRuleModel.tenant_id == self._tenant_id)
            .values(**data)
            .returning(AlertRuleModel)
        )
        result = await self._session.execute(stmt)
        await self._session.flush()
        return result.scalar_one_or_none()

    async def delete(self, rule_id: UUID) -> bool:
        from sqlalchemy import delete as sa_delete
        stmt = (
            sa_delete(AlertRuleModel)
            .where(AlertRuleModel.id == rule_id)
            .where(AlertRuleModel.tenant_id == self._tenant_id)
        )
        result = await self._session.execute(stmt)
        await self._session.flush()
        return result.rowcount > 0


class AlertInstanceRepository:
    """Repository for triggered alert instances."""

    def __init__(self, session, tenant_id: UUID):
        self._session = session
        self._tenant_id = tenant_id

    async def create(self, data: dict) -> AlertInstanceModel:
        model = AlertInstanceModel(**data, tenant_id=self._tenant_id)
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return model

    async def get_active(self, limit: int = 50) -> list[AlertInstanceModel]:
        stmt = (
            select(AlertInstanceModel)
            .where(AlertInstanceModel.tenant_id == self._tenant_id)
            .where(AlertInstanceModel.status == "active")
            .order_by(AlertInstanceModel.created_at.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_all(self, skip: int = 0, limit: int = 50) -> list[AlertInstanceModel]:
        stmt = (
            select(AlertInstanceModel)
            .where(AlertInstanceModel.tenant_id == self._tenant_id)
            .order_by(AlertInstanceModel.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def acknowledge(self, alert_id: UUID, user_id: UUID) -> bool:
        stmt = (
            sa_update(AlertInstanceModel)
            .where(AlertInstanceModel.id == alert_id)
            .where(AlertInstanceModel.tenant_id == self._tenant_id)
            .values(
                status="acknowledged",
                acknowledged_at=datetime.utcnow(),
                acknowledged_by=user_id,
            )
        )
        result = await self._session.execute(stmt)
        await self._session.flush()
        return result.rowcount > 0

    async def resolve(self, alert_id: UUID) -> bool:
        stmt = (
            sa_update(AlertInstanceModel)
            .where(AlertInstanceModel.id == alert_id)
            .where(AlertInstanceModel.tenant_id == self._tenant_id)
            .values(status="resolved", resolved_at=datetime.utcnow())
        )
        result = await self._session.execute(stmt)
        await self._session.flush()
        return result.rowcount > 0

    async def count_active(self) -> int:
        stmt = (
            select(func.count())
            .select_from(AlertInstanceModel)
            .where(AlertInstanceModel.tenant_id == self._tenant_id)
            .where(AlertInstanceModel.status == "active")
        )
        result = await self._session.execute(stmt)
        return result.scalar_one()


class ImportLogRepository:
    """Repository for import job tracking."""

    def __init__(self, session, tenant_id: UUID):
        self._session = session
        self._tenant_id = tenant_id

    async def create(self, data: dict) -> ImportLogModel:
        model = ImportLogModel(**data, tenant_id=self._tenant_id)
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return model

    async def update_status(
        self, log_id: UUID, status: str,
        imported: int = 0, duplicates: int = 0, errors: int = 0,
        total_records: int = 0, error_details: list | None = None,
    ) -> None:
        values: dict[str, Any] = {"status": status}
        if status == "running":
            values["started_at"] = datetime.utcnow()
        elif status in ("completed", "failed"):
            values["completed_at"] = datetime.utcnow()
            values["imported"] = imported
            values["duplicates"] = duplicates
            values["errors"] = errors
            values["total_records"] = total_records
            if error_details:
                values["error_details"] = error_details
        stmt = (
            sa_update(ImportLogModel)
            .where(ImportLogModel.id == log_id)
            .values(**values)
        )
        await self._session.execute(stmt)
        await self._session.flush()

    async def get_all(self, skip: int = 0, limit: int = 50) -> list[ImportLogModel]:
        stmt = (
            select(ImportLogModel)
            .where(ImportLogModel.tenant_id == self._tenant_id)
            .order_by(ImportLogModel.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_task_id(self, task_id: str) -> ImportLogModel | None:
        stmt = (
            select(ImportLogModel)
            .where(ImportLogModel.tenant_id == self._tenant_id)
            .where(ImportLogModel.task_id == task_id)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_type(self, import_type: str, skip: int = 0, limit: int = 50) -> list[ImportLogModel]:
        stmt = (
            select(ImportLogModel)
            .where(ImportLogModel.tenant_id == self._tenant_id)
            .where(ImportLogModel.import_type == import_type)
            .order_by(ImportLogModel.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_stats(self) -> dict:
        """Get import stats summary."""
        stmt = (
            select(
                ImportLogModel.import_type,
                ImportLogModel.status,
                func.count().label("count"),
                func.sum(ImportLogModel.imported).label("total_imported"),
            )
            .where(ImportLogModel.tenant_id == self._tenant_id)
            .group_by(ImportLogModel.import_type, ImportLogModel.status)
        )
        result = await self._session.execute(stmt)
        stats: dict[str, dict] = {}
        for row in result.all():
            key = row.import_type
            if key not in stats:
                stats[key] = {"total_jobs": 0, "total_imported": 0, "by_status": {}}
            stats[key]["total_jobs"] += row.count
            stats[key]["total_imported"] += row.total_imported or 0
            stats[key]["by_status"][row.status] = row.count
        return stats

