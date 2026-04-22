"""
Segmentation Application Service — Segment Rule Operations

Handles business logic for named segment rules:
- Preview: count + sample contacts matching a rule
- Bulk assign: stamp rfm_segment on matching contacts
"""

from uuid import UUID

from sqlalchemy import select, update as sa_update, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.database.models.leads import ContactModel
from src.modules.segmentation.domain.segment_rules import (
    BulkAssignResult,
    NamedSegmentRule,
    SegmentRulePreview,
)
from src.modules.segmentation.infrastructure.repositories import SegmentRuleRepository


class SegmentRuleService:
    """Application service for NamedSegmentRule CRUD and operations."""

    def __init__(self, session: AsyncSession, tenant_id: UUID):
        self._session = session
        self._tenant_id = tenant_id
        self._repo = SegmentRuleRepository(session, tenant_id)

    # ── CRUD ────────────────────────────────────────────────────────────────

    async def create(self, rule: NamedSegmentRule) -> NamedSegmentRule:
        rule.tenant_id = self._tenant_id
        return await self._repo.create(rule)

    async def get(self, rule_id: UUID) -> NamedSegmentRule | None:
        return await self._repo.get(rule_id)

    async def list_rules(self) -> list[NamedSegmentRule]:
        return await self._repo.list_by_tenant()

    async def update(self, rule: NamedSegmentRule) -> NamedSegmentRule | None:
        return await self._repo.update(rule)

    async def delete(self, rule_id: UUID) -> bool:
        return await self._repo.delete(rule_id)

    # ── Preview ─────────────────────────────────────────────────────────────

    async def preview(self, rule_id: UUID, sample_size: int = 20) -> SegmentRulePreview:
        """Count + sample contacts matching this rule (pure DB query)."""
        rule = await self._repo.get(rule_id)
        if not rule:
            return SegmentRulePreview(rule_id=rule_id, matching_count=0)

        base = (
            select(ContactModel)
            .where(ContactModel.tenant_id == self._tenant_id)
            .where(ContactModel.is_active == True)
            .where(ContactModel.recency_score >= rule.r_min)
            .where(ContactModel.recency_score <= rule.r_max)
            .where(ContactModel.frequency_score >= rule.f_min)
            .where(ContactModel.frequency_score <= rule.f_max)
            .where(ContactModel.monetary_score >= rule.m_min)
            .where(ContactModel.monetary_score <= rule.m_max)
        )

        count_stmt = select(func.count()).select_from(base.subquery())
        count_result = await self._session.execute(count_stmt)
        total = count_result.scalar() or 0

        sample_stmt = base.limit(sample_size)
        sample_result = await self._session.execute(sample_stmt)
        sample_ids = [c.id for c in sample_result.scalars().all()]

        return SegmentRulePreview(
            rule_id=rule_id,
            matching_count=total,
            sample_contact_ids=sample_ids,
        )

    # ── Bulk Assign ──────────────────────────────────────────────────────────

    async def bulk_assign(self, rule_id: UUID) -> BulkAssignResult:
        """Stamp rfm_segment = rule.name on all contacts matching the rule."""
        rule = await self._repo.get(rule_id)
        if not rule:
            return BulkAssignResult(rule_id=rule_id, rule_name="", assigned_count=0)

        stmt = (
            sa_update(ContactModel)
            .where(ContactModel.tenant_id == self._tenant_id)
            .where(ContactModel.is_active == True)
            .where(ContactModel.recency_score >= rule.r_min)
            .where(ContactModel.recency_score <= rule.r_max)
            .where(ContactModel.frequency_score >= rule.f_min)
            .where(ContactModel.frequency_score <= rule.f_max)
            .where(ContactModel.monetary_score >= rule.m_min)
            .where(ContactModel.monetary_score <= rule.m_max)
            .values(rfm_segment=rule.name)
        )
        result = await self._session.execute(stmt)
        await self._session.commit()

        return BulkAssignResult(
            rule_id=rule_id,
            rule_name=rule.name,
            assigned_count=result.rowcount,
        )

