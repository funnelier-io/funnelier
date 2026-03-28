"""
Campaigns Module - Repository Implementations
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select, func, update as sa_update

from src.core.domain import CampaignStatus
from src.infrastructure.database.repositories import SqlAlchemyRepository
from src.infrastructure.database.models.campaigns import (
    CampaignModel,
    CampaignRecipientModel,
)
from src.modules.campaigns.domain.entities import Campaign


class CampaignRepository(SqlAlchemyRepository[CampaignModel, Campaign]):
    """SQLAlchemy implementation of campaign repository."""

    def __init__(self, session, tenant_id: UUID):
        super().__init__(session, tenant_id, CampaignModel)

    def _to_entity(self, model: CampaignModel) -> Campaign:
        return Campaign(
            id=model.id,
            tenant_id=model.tenant_id,
            name=model.name,
            description=model.description,
            template_id=model.template_id,
            message_content=model.message_content or "",
            target_segment=model.target_segment,
            target_category_id=model.target_category_id,
            target_filters=model.target_filters or {},
            total_recipients=model.total_recipients,
            scheduled_at=model.scheduled_at,
            started_at=model.started_at,
            completed_at=model.completed_at,
            status=CampaignStatus(model.status) if model.status else CampaignStatus.DRAFT,
            total_sent=model.total_sent,
            total_delivered=model.total_delivered,
            total_failed=model.total_failed,
            total_calls_received=model.total_calls_received,
            total_conversions=model.total_conversions,
            total_revenue=model.total_revenue,
            is_ab_test=model.is_ab_test,
            variant_name=model.variant_name,
            parent_campaign_id=model.parent_campaign_id,
            estimated_cost=model.estimated_cost,
            actual_cost=model.actual_cost,
            created_by=model.created_by,
            metadata=model.metadata_ or {},
        )

    def _to_model(self, entity: Campaign) -> CampaignModel:
        return CampaignModel(
            id=entity.id,
            tenant_id=entity.tenant_id,
            name=entity.name,
            description=entity.description,
            campaign_type="sms",
            template_id=entity.template_id,
            message_content=entity.message_content,
            target_segment=entity.target_segment,
            target_category_id=entity.target_category_id,
            target_filters=entity.target_filters,
            targeting={},
            scheduled_at=entity.scheduled_at,
            started_at=entity.started_at,
            completed_at=entity.completed_at,
            status=entity.status.value if hasattr(entity.status, "value") else entity.status,
            is_active=entity.status != CampaignStatus.CANCELLED,
            total_recipients=entity.total_recipients,
            total_sent=entity.total_sent,
            total_delivered=entity.total_delivered,
            total_failed=entity.total_failed,
            total_calls_received=entity.total_calls_received,
            total_conversions=entity.total_conversions,
            total_revenue=entity.total_revenue,
            is_ab_test=entity.is_ab_test,
            variant_name=entity.variant_name,
            parent_campaign_id=entity.parent_campaign_id,
            estimated_cost=entity.estimated_cost,
            actual_cost=entity.actual_cost,
            created_by=entity.created_by,
            metadata_=entity.metadata,
        )

    def _model_to_response_dict(self, model: CampaignModel) -> dict[str, Any]:
        """Convert model directly to dict suitable for CampaignResponse schema."""
        return {
            "id": model.id,
            "tenant_id": model.tenant_id,
            "name": model.name,
            "description": model.description,
            "campaign_type": model.campaign_type or "sms",
            "template_id": model.template_id,
            "content": model.message_content,
            "targeting": model.targeting or {},
            "schedule": model.schedule,
            "status": model.status,
            "is_active": model.is_active,
            "total_recipients": model.total_recipients,
            "sent_count": model.total_sent,
            "delivered_count": model.total_delivered,
            "failed_count": model.total_failed,
            "response_count": model.total_calls_received,
            "conversion_count": model.total_conversions,
            "started_at": model.started_at,
            "completed_at": model.completed_at,
            "created_at": model.created_at,
            "updated_at": model.updated_at,
            "metadata": model.metadata_ or {},
        }

    async def get_model(self, campaign_id: UUID) -> CampaignModel | None:
        """Get raw model by ID (for response building)."""
        stmt = self._base_query().where(CampaignModel.id == campaign_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_campaigns(
        self,
        skip: int = 0,
        limit: int = 20,
        status: str | None = None,
        campaign_type: str | None = None,
        search: str | None = None,
    ) -> tuple[list[CampaignModel], int]:
        """List campaigns with filtering. Returns (models, total_count)."""
        stmt = self._base_query()

        if status:
            stmt = stmt.where(CampaignModel.status == status)
        if campaign_type:
            stmt = stmt.where(CampaignModel.campaign_type == campaign_type)
        if search:
            stmt = stmt.where(CampaignModel.name.ilike(f"%{search}%"))

        # Count
        count_stmt = (
            select(func.count())
            .select_from(CampaignModel)
            .where(CampaignModel.tenant_id == self._tenant_id)
        )
        if status:
            count_stmt = count_stmt.where(CampaignModel.status == status)
        if campaign_type:
            count_stmt = count_stmt.where(CampaignModel.campaign_type == campaign_type)
        if search:
            count_stmt = count_stmt.where(CampaignModel.name.ilike(f"%{search}%"))

        count_result = await self._session.execute(count_stmt)
        total = count_result.scalar_one()

        # Fetch
        stmt = stmt.order_by(CampaignModel.created_at.desc()).offset(skip).limit(limit)
        result = await self._session.execute(stmt)
        models = list(result.scalars().all())

        return models, total

    async def update_status(self, campaign_id: UUID, status: str, **extra_fields) -> CampaignModel | None:
        """Update campaign status with optional extra fields."""
        values = {"status": status, **extra_fields}
        stmt = (
            sa_update(CampaignModel)
            .where(CampaignModel.id == campaign_id)
            .where(CampaignModel.tenant_id == self._tenant_id)
            .values(**values)
        )
        await self._session.execute(stmt)
        await self._session.flush()
        return await self.get_model(campaign_id)

    async def increment_counters(
        self,
        campaign_id: UUID,
        sent: int = 0,
        delivered: int = 0,
        failed: int = 0,
        calls: int = 0,
        conversions: int = 0,
        revenue: int = 0,
    ) -> None:
        """Atomically increment campaign counters."""
        values = {}
        if sent:
            values["total_sent"] = CampaignModel.total_sent + sent
        if delivered:
            values["total_delivered"] = CampaignModel.total_delivered + delivered
        if failed:
            values["total_failed"] = CampaignModel.total_failed + failed
        if calls:
            values["total_calls_received"] = CampaignModel.total_calls_received + calls
        if conversions:
            values["total_conversions"] = CampaignModel.total_conversions + conversions
        if revenue:
            values["total_revenue"] = CampaignModel.total_revenue + revenue

        if values:
            stmt = (
                sa_update(CampaignModel)
                .where(CampaignModel.id == campaign_id)
                .where(CampaignModel.tenant_id == self._tenant_id)
                .values(**values)
            )
            await self._session.execute(stmt)
            await self._session.flush()


class CampaignRecipientRepository(SqlAlchemyRepository[CampaignRecipientModel, dict]):
    """Repository for campaign recipients."""

    def __init__(self, session, tenant_id: UUID):
        super().__init__(session, tenant_id, CampaignRecipientModel)

    def _to_entity(self, model: CampaignRecipientModel) -> dict:
        return {
            "id": model.id,
            "tenant_id": model.tenant_id,
            "campaign_id": model.campaign_id,
            "contact_id": model.contact_id,
            "phone_number": model.phone_number,
            "name": model.name,
            "segment": model.segment,
            "status": model.status,
            "sms_log_id": model.sms_log_id,
            "sent_at": model.sent_at,
            "delivered_at": model.delivered_at,
            "responded_at": model.responded_at,
            "converted_at": model.converted_at,
        }

    def _to_model(self, entity: dict) -> CampaignRecipientModel:
        return CampaignRecipientModel(**entity)

    async def get_by_campaign(
        self,
        campaign_id: UUID,
        skip: int = 0,
        limit: int = 100,
        status: str | None = None,
    ) -> tuple[list[CampaignRecipientModel], int]:
        """Get recipients for a campaign."""
        stmt = (
            self._base_query()
            .where(CampaignRecipientModel.campaign_id == campaign_id)
        )
        if status:
            stmt = stmt.where(CampaignRecipientModel.status == status)

        # Count
        count_stmt = (
            select(func.count())
            .select_from(CampaignRecipientModel)
            .where(CampaignRecipientModel.tenant_id == self._tenant_id)
            .where(CampaignRecipientModel.campaign_id == campaign_id)
        )
        if status:
            count_stmt = count_stmt.where(CampaignRecipientModel.status == status)
        count_result = await self._session.execute(count_stmt)
        total = count_result.scalar_one()

        stmt = stmt.offset(skip).limit(limit)
        result = await self._session.execute(stmt)
        models = list(result.scalars().all())

        return models, total

    async def bulk_add(self, recipients: list[dict]) -> int:
        """Bulk-add recipients. Returns count added."""
        models = [CampaignRecipientModel(**r) for r in recipients]
        self._session.add_all(models)
        await self._session.flush()
        return len(models)

