"""
Segmentation Module - Segment Rule Repository
"""

from uuid import UUID

from sqlalchemy import select, update as sa_update, delete as sa_delete
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.database.models.segment_rules import SegmentRuleModel
from src.modules.segmentation.domain.segment_rules import NamedSegmentRule


class SegmentRuleRepository:
    """Async repository for tenant-scoped segment rules."""

    def __init__(self, session: AsyncSession, tenant_id: UUID):
        self._session = session
        self._tenant_id = tenant_id

    def _to_entity(self, m: SegmentRuleModel) -> NamedSegmentRule:
        return NamedSegmentRule(
            id=m.id,
            tenant_id=m.tenant_id,
            name=m.name,
            description=m.description,
            color=m.color,
            priority=m.priority,
            r_min=m.r_min, r_max=m.r_max,
            f_min=m.f_min, f_max=m.f_max,
            m_min=m.m_min, m_max=m.m_max,
            created_at=m.created_at,
            updated_at=m.updated_at,
        )

    def _to_model(self, e: NamedSegmentRule) -> SegmentRuleModel:
        return SegmentRuleModel(
            id=e.id,
            tenant_id=e.tenant_id,
            name=e.name,
            description=e.description,
            color=e.color,
            priority=e.priority,
            r_min=e.r_min, r_max=e.r_max,
            f_min=e.f_min, f_max=e.f_max,
            m_min=e.m_min, m_max=e.m_max,
        )

    async def create(self, rule: NamedSegmentRule) -> NamedSegmentRule:
        model = self._to_model(rule)
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return self._to_entity(model)

    async def get(self, rule_id: UUID) -> NamedSegmentRule | None:
        stmt = (
            select(SegmentRuleModel)
            .where(SegmentRuleModel.tenant_id == self._tenant_id)
            .where(SegmentRuleModel.id == rule_id)
        )
        result = await self._session.execute(stmt)
        m = result.scalar_one_or_none()
        return self._to_entity(m) if m else None

    async def list_by_tenant(self) -> list[NamedSegmentRule]:
        stmt = (
            select(SegmentRuleModel)
            .where(SegmentRuleModel.tenant_id == self._tenant_id)
            .where(SegmentRuleModel.is_active == True)
            .order_by(SegmentRuleModel.priority.asc())
        )
        result = await self._session.execute(stmt)
        return [self._to_entity(m) for m in result.scalars().all()]

    async def update(self, rule: NamedSegmentRule) -> NamedSegmentRule | None:
        stmt = (
            sa_update(SegmentRuleModel)
            .where(SegmentRuleModel.tenant_id == self._tenant_id)
            .where(SegmentRuleModel.id == rule.id)
            .values(
                name=rule.name,
                description=rule.description,
                color=rule.color,
                priority=rule.priority,
                r_min=rule.r_min, r_max=rule.r_max,
                f_min=rule.f_min, f_max=rule.f_max,
                m_min=rule.m_min, m_max=rule.m_max,
            )
            .returning(SegmentRuleModel)
        )
        result = await self._session.execute(stmt)
        m = result.scalar_one_or_none()
        return self._to_entity(m) if m else None

    async def delete(self, rule_id: UUID) -> bool:
        stmt = (
            sa_update(SegmentRuleModel)
            .where(SegmentRuleModel.tenant_id == self._tenant_id)
            .where(SegmentRuleModel.id == rule_id)
            .values(is_active=False)
        )
        result = await self._session.execute(stmt)
        return result.rowcount > 0

