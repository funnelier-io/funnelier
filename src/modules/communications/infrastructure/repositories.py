"""
Communications Module - Repository Implementations
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select, func, update as sa_update

from src.core.domain import SMSStatus, SMSDirection, CallType, CallSource
from src.infrastructure.database.repositories import SqlAlchemyRepository
from src.infrastructure.database.models.communications import (
    SMSLogModel,
    SMSTemplateModel,
    CallLogModel,
)
from src.modules.communications.domain.entities import SMSLog, SMSTemplate, CallLog
from src.modules.communications.domain.repositories import (
    ISMSLogRepository,
    ISMSTemplateRepository,
    ICallLogRepository,
)


class SMSLogRepository(SqlAlchemyRepository[SMSLogModel, SMSLog], ISMSLogRepository):
    """SQLAlchemy implementation of ISMSLogRepository."""

    def __init__(self, session, tenant_id: UUID):
        super().__init__(session, tenant_id, SMSLogModel)

    def _to_entity(self, model: SMSLogModel) -> SMSLog:
        return SMSLog(
            id=model.id,
            tenant_id=model.tenant_id,
            contact_id=model.contact_id,
            phone_number=model.phone_number,
            direction=SMSDirection.OUTBOUND,
            content=model.message_content,
            template_id=model.template_id,
            status=SMSStatus(model.status) if model.status else SMSStatus.PENDING,
            provider_message_id=model.message_id,
            sent_at=model.sent_at,
            delivered_at=model.delivered_at,
            failed_at=model.failed_at,
            failure_reason=model.status_message,
            campaign_id=model.campaign_id,
            provider_name=model.provider,
            cost=model.cost,
            metadata=model.metadata_ or {},
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    def _to_model(self, entity: SMSLog) -> SMSLogModel:
        return SMSLogModel(
            id=entity.id,
            tenant_id=entity.tenant_id,
            contact_id=entity.contact_id,
            phone_number=entity.phone_number,
            message_content=entity.content,
            template_id=entity.template_id,
            message_id=entity.provider_message_id,
            status=entity.status.value if hasattr(entity.status, 'value') else entity.status,
            status_message=entity.failure_reason,
            sent_at=entity.sent_at,
            delivered_at=entity.delivered_at,
            failed_at=entity.failed_at,
            campaign_id=entity.campaign_id,
            provider=entity.provider_name or "kavenegar",
            cost=entity.cost,
            metadata_=entity.metadata,
        )

    async def get_by_provider_id(self, provider_message_id: str) -> SMSLog | None:
        stmt = self._base_query().where(SMSLogModel.message_id == provider_message_id)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def get_by_phone(self, phone_number: str, skip: int = 0, limit: int = 100) -> list[SMSLog]:
        stmt = self._base_query().where(SMSLogModel.phone_number == phone_number).order_by(SMSLogModel.created_at.desc()).offset(skip).limit(limit)
        result = await self._session.execute(stmt)
        return [self._to_entity(m) for m in result.scalars().all()]

    async def get_by_campaign(self, campaign_id: UUID, skip: int = 0, limit: int = 100) -> list[SMSLog]:
        stmt = self._base_query().where(SMSLogModel.campaign_id == campaign_id).offset(skip).limit(limit)
        result = await self._session.execute(stmt)
        return [self._to_entity(m) for m in result.scalars().all()]

    async def get_by_status(self, status: str, skip: int = 0, limit: int = 100) -> list[SMSLog]:
        stmt = self._base_query().where(SMSLogModel.status == status).offset(skip).limit(limit)
        result = await self._session.execute(stmt)
        return [self._to_entity(m) for m in result.scalars().all()]

    async def get_by_date_range(self, start_date: datetime, end_date: datetime, skip: int = 0, limit: int = 100) -> list[SMSLog]:
        stmt = (
            self._base_query()
            .where(SMSLogModel.sent_at >= start_date)
            .where(SMSLogModel.sent_at <= end_date)
            .order_by(SMSLogModel.sent_at.desc())
            .offset(skip).limit(limit)
        )
        result = await self._session.execute(stmt)
        return [self._to_entity(m) for m in result.scalars().all()]

    async def get_delivery_stats(self, start_date: datetime | None = None, end_date: datetime | None = None) -> dict[str, int]:
        stmt = (
            select(SMSLogModel.status, func.count())
            .where(SMSLogModel.tenant_id == self._tenant_id)
            .group_by(SMSLogModel.status)
        )
        if start_date:
            stmt = stmt.where(SMSLogModel.sent_at >= start_date)
        if end_date:
            stmt = stmt.where(SMSLogModel.sent_at <= end_date)
        result = await self._session.execute(stmt)
        return {row[0]: row[1] for row in result.all()}

    async def bulk_create(self, logs: list[SMSLog]) -> tuple[int, int, list[str]]:
        success, errors_list = 0, []
        for log in logs:
            try:
                model = self._to_model(log)
                self._session.add(model)
                success += 1
            except Exception as e:
                errors_list.append(str(e))
        await self._session.flush()
        return success, len(errors_list), errors_list


class CallLogRepository(SqlAlchemyRepository[CallLogModel, CallLog], ICallLogRepository):
    """SQLAlchemy implementation of ICallLogRepository."""

    def __init__(self, session, tenant_id: UUID):
        super().__init__(session, tenant_id, CallLogModel)

    def _to_entity(self, model: CallLogModel) -> CallLog:
        type_map = {"outbound": CallType.OUTGOING, "inbound": CallType.INCOMING}
        source_map = {"mobile": CallSource.MOBILE, "voip": CallSource.VOIP}
        return CallLog(
            id=model.id,
            tenant_id=model.tenant_id,
            contact_id=model.contact_id,
            phone_number=model.phone_number,
            call_type=type_map.get(model.call_type, CallType.OUTGOING),
            source=source_map.get(model.source_type, CallSource.MOBILE),
            duration_seconds=model.duration_seconds,
            call_time=model.call_start,
            answered_at=model.call_start if model.status == "answered" else None,
            ended_at=model.call_end,
            salesperson_id=model.salesperson_id,
            salesperson_phone=model.salesperson_phone,
            salesperson_name=model.salesperson_name,
            voip_call_id=model.voip_call_id,
            voip_extension=model.voip_channel,
            recording_url=model.recording_url,
            is_successful=model.is_successful,
            metadata=model.metadata_ or {},
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    def _to_model(self, entity: CallLog) -> CallLogModel:
        type_map = {CallType.OUTGOING: "outbound", CallType.INCOMING: "inbound", CallType.MISSED: "outbound"}
        source_map = {CallSource.MOBILE: "mobile", CallSource.VOIP: "voip"}
        status = "answered" if entity.is_successful else ("no_answer" if entity.duration_seconds == 0 else "attempted")
        return CallLogModel(
            id=entity.id,
            tenant_id=entity.tenant_id,
            contact_id=entity.contact_id,
            phone_number=entity.phone_number,
            call_type=type_map.get(entity.call_type, "outbound"),
            source_type=source_map.get(entity.source, "mobile"),
            salesperson_id=entity.salesperson_id,
            salesperson_phone=entity.salesperson_phone,
            salesperson_name=entity.salesperson_name,
            call_start=entity.call_time,
            call_end=entity.ended_at,
            duration_seconds=entity.duration_seconds,
            status=status,
            is_successful=entity.is_successful,
            voip_call_id=entity.voip_call_id,
            voip_channel=entity.voip_extension,
            recording_url=entity.recording_url,
            notes=None,
            outcome=None,
            metadata_=entity.metadata,
        )

    async def get_by_phone(self, phone_number: str, skip: int = 0, limit: int = 100) -> list[CallLog]:
        stmt = self._base_query().where(CallLogModel.phone_number == phone_number).order_by(CallLogModel.call_start.desc()).offset(skip).limit(limit)
        result = await self._session.execute(stmt)
        return [self._to_entity(m) for m in result.scalars().all()]

    async def get_by_salesperson(self, salesperson_id: UUID, skip: int = 0, limit: int = 100) -> list[CallLog]:
        stmt = self._base_query().where(CallLogModel.salesperson_id == salesperson_id).order_by(CallLogModel.call_start.desc()).offset(skip).limit(limit)
        result = await self._session.execute(stmt)
        return [self._to_entity(m) for m in result.scalars().all()]

    async def get_by_date_range(self, start_date: datetime, end_date: datetime, skip: int = 0, limit: int = 100) -> list[CallLog]:
        stmt = (
            self._base_query()
            .where(CallLogModel.call_start >= start_date)
            .where(CallLogModel.call_start <= end_date)
            .order_by(CallLogModel.call_start.desc())
            .offset(skip).limit(limit)
        )
        result = await self._session.execute(stmt)
        return [self._to_entity(m) for m in result.scalars().all()]

    async def get_by_source(self, source: str, skip: int = 0, limit: int = 100) -> list[CallLog]:
        stmt = self._base_query().where(CallLogModel.source_type == source).offset(skip).limit(limit)
        result = await self._session.execute(stmt)
        return [self._to_entity(m) for m in result.scalars().all()]

    async def get_successful_calls(self, start_date: datetime | None = None, end_date: datetime | None = None, skip: int = 0, limit: int = 100) -> list[CallLog]:
        stmt = self._base_query().where(CallLogModel.is_successful.is_(True))
        if start_date:
            stmt = stmt.where(CallLogModel.call_start >= start_date)
        if end_date:
            stmt = stmt.where(CallLogModel.call_start <= end_date)
        stmt = stmt.order_by(CallLogModel.call_start.desc()).offset(skip).limit(limit)
        result = await self._session.execute(stmt)
        return [self._to_entity(m) for m in result.scalars().all()]

    async def get_call_stats(self, start_date: datetime | None = None, end_date: datetime | None = None, group_by: str | None = None) -> dict[str, Any]:
        base = select(
            func.count().label("total"),
            func.sum(CallLogModel.duration_seconds).label("total_duration"),
            func.count().filter(CallLogModel.is_successful.is_(True)).label("successful"),
        ).where(CallLogModel.tenant_id == self._tenant_id)
        if start_date:
            base = base.where(CallLogModel.call_start >= start_date)
        if end_date:
            base = base.where(CallLogModel.call_start <= end_date)
        result = await self._session.execute(base)
        row = result.one()
        return {"total": row.total, "total_duration": row.total_duration or 0, "successful": row.successful}

    async def bulk_create(self, logs: list[CallLog]) -> tuple[int, int, list[str]]:
        success, errors_list = 0, []
        for log in logs:
            try:
                model = self._to_model(log)
                self._session.add(model)
                success += 1
            except Exception as e:
                errors_list.append(str(e))
        await self._session.flush()
        return success, len(errors_list), errors_list


class SMSTemplateRepository(SqlAlchemyRepository[SMSTemplateModel, SMSTemplate], ISMSTemplateRepository):
    """SQLAlchemy implementation of ISMSTemplateRepository."""

    def __init__(self, session, tenant_id: UUID):
        super().__init__(session, tenant_id, SMSTemplateModel)

    def _to_entity(self, model: SMSTemplateModel) -> SMSTemplate:
        return SMSTemplate(
            id=model.id,
            tenant_id=model.tenant_id,
            name=model.name,
            content=model.content,
            description=model.description,
            category=model.category,
            target_segments=model.target_segments or [],
            times_used=model.times_used,
            is_active=model.is_active,
            metadata=model.metadata_ or {},
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    def _to_model(self, entity: SMSTemplate) -> SMSTemplateModel:
        return SMSTemplateModel(
            id=entity.id,
            tenant_id=entity.tenant_id,
            name=entity.name,
            content=entity.content,
            description=entity.description,
            category=entity.category,
            target_segments=entity.target_segments,
            times_used=entity.times_used,
            is_active=entity.is_active,
            metadata_=entity.metadata,
        )

    async def get_by_name(self, name: str) -> SMSTemplate | None:
        stmt = self._base_query().where(SMSTemplateModel.name == name)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def get_by_category(self, category: str, skip: int = 0, limit: int = 100) -> list[SMSTemplate]:
        stmt = self._base_query().where(SMSTemplateModel.category == category).offset(skip).limit(limit)
        result = await self._session.execute(stmt)
        return [self._to_entity(m) for m in result.scalars().all()]

    async def get_by_segment(self, segment: str) -> list[SMSTemplate]:
        stmt = self._base_query().where(SMSTemplateModel.target_segments.contains([segment]))
        result = await self._session.execute(stmt)
        return [self._to_entity(m) for m in result.scalars().all()]

    async def get_active_templates(self) -> list[SMSTemplate]:
        stmt = self._base_query().where(SMSTemplateModel.is_active.is_(True))
        result = await self._session.execute(stmt)
        return [self._to_entity(m) for m in result.scalars().all()]

    async def increment_usage(self, template_id: UUID) -> None:
        stmt = (
            sa_update(SMSTemplateModel)
            .where(SMSTemplateModel.id == template_id)
            .where(SMSTemplateModel.tenant_id == self._tenant_id)
            .values(times_used=SMSTemplateModel.times_used + 1)
        )
        await self._session.execute(stmt)
        await self._session.flush()

