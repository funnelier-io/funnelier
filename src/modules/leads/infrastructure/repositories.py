"""
Leads Module - Repository Implementations
Concrete SQLAlchemy repositories for leads domain entities.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select, func, or_

from src.core.domain.entities import PhoneNumber
from src.infrastructure.database.repositories import SqlAlchemyRepository
from src.infrastructure.database.models.leads import (
    ContactModel,
    LeadCategoryModel,
    LeadSourceModel,
)
from src.modules.leads.domain.entities import Contact, LeadCategory, LeadSourceConfig
from src.modules.leads.domain.repositories import (
    IContactRepository,
    ILeadCategoryRepository,
    ILeadSourceRepository,
)


class ContactRepository(SqlAlchemyRepository[ContactModel, Contact], IContactRepository):
    """SQLAlchemy implementation of IContactRepository."""

    def __init__(self, session, tenant_id: UUID):
        super().__init__(session, tenant_id, ContactModel)

    def _to_entity(self, model: ContactModel) -> Contact:
        return Contact(
            id=model.id,
            tenant_id=model.tenant_id,
            phone_number=PhoneNumber.from_string(model.phone_number),
            name=model.name,
            email=model.email,
            source_id=model.source_id,
            source_name=model.source_name,
            category_id=model.category_id,
            category_name=model.category_name,
            assigned_to=model.assigned_to,
            assigned_at=model.assigned_at,
            current_stage=model.current_stage,
            stage_entered_at=model.stage_entered_at or datetime.utcnow(),
            rfm_segment=model.rfm_segment,
            rfm_score=model.rfm_score,
            recency_score=model.recency_score,
            frequency_score=model.frequency_score,
            monetary_score=model.monetary_score,
            last_rfm_update=model.last_rfm_update,
            total_sms_sent=model.total_sms_sent,
            total_sms_delivered=model.total_sms_delivered,
            total_calls=model.total_calls,
            total_answered_calls=model.total_answered_calls,
            total_call_duration=model.total_call_duration,
            total_invoices=model.total_invoices,
            total_paid_invoices=model.total_paid_invoices,
            total_revenue=model.total_revenue,
            last_purchase_at=model.last_purchase_at,
            first_purchase_at=model.first_purchase_at,
            is_active=model.is_active,
            is_blocked=model.is_blocked,
            blocked_reason=model.blocked_reason,
            tags=model.tags or [],
            custom_fields=model.custom_fields or {},
            notes=model.notes,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    def _to_model(self, entity: Contact) -> ContactModel:
        return ContactModel(
            id=entity.id,
            tenant_id=entity.tenant_id,
            phone_number=entity.phone_number.normalized if isinstance(entity.phone_number, PhoneNumber) else entity.phone_number,
            name=entity.name,
            email=entity.email,
            source_id=entity.source_id,
            source_name=entity.source_name,
            category_id=entity.category_id,
            category_name=entity.category_name,
            assigned_to=entity.assigned_to,
            assigned_at=entity.assigned_at,
            current_stage=entity.current_stage,
            stage_entered_at=entity.stage_entered_at,
            rfm_segment=entity.rfm_segment,
            rfm_score=entity.rfm_score,
            recency_score=entity.recency_score,
            frequency_score=entity.frequency_score,
            monetary_score=entity.monetary_score,
            last_rfm_update=entity.last_rfm_update,
            total_sms_sent=entity.total_sms_sent,
            total_sms_delivered=entity.total_sms_delivered,
            total_calls=entity.total_calls,
            total_answered_calls=entity.total_answered_calls,
            total_call_duration=entity.total_call_duration,
            total_invoices=entity.total_invoices,
            total_paid_invoices=entity.total_paid_invoices,
            total_revenue=entity.total_revenue,
            last_purchase_at=entity.last_purchase_at,
            first_purchase_at=entity.first_purchase_at,
            is_active=entity.is_active,
            is_blocked=entity.is_blocked,
            blocked_reason=entity.blocked_reason,
            tags=entity.tags,
            custom_fields=entity.custom_fields,
            notes=entity.notes,
        )

    async def get_by_phone(self, phone_number: str) -> Contact | None:
        phone = PhoneNumber.from_string(phone_number)
        stmt = self._base_query().where(ContactModel.phone_number == phone.normalized)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def get_by_category(self, category_id: UUID, skip: int = 0, limit: int = 100) -> list[Contact]:
        stmt = self._base_query().where(ContactModel.category_id == category_id).offset(skip).limit(limit)
        result = await self._session.execute(stmt)
        return [self._to_entity(m) for m in result.scalars().all()]

    async def get_by_source(self, source_id: UUID, skip: int = 0, limit: int = 100) -> list[Contact]:
        stmt = self._base_query().where(ContactModel.source_id == source_id).offset(skip).limit(limit)
        result = await self._session.execute(stmt)
        return [self._to_entity(m) for m in result.scalars().all()]

    async def get_by_segment(self, segment: str, skip: int = 0, limit: int = 100) -> list[Contact]:
        stmt = self._base_query().where(ContactModel.rfm_segment == segment).offset(skip).limit(limit)
        result = await self._session.execute(stmt)
        return [self._to_entity(m) for m in result.scalars().all()]

    async def get_by_stage(self, stage: str, skip: int = 0, limit: int = 100) -> list[Contact]:
        stmt = self._base_query().where(ContactModel.current_stage == stage).offset(skip).limit(limit)
        result = await self._session.execute(stmt)
        return [self._to_entity(m) for m in result.scalars().all()]

    async def get_by_salesperson(self, salesperson_id: UUID, skip: int = 0, limit: int = 100) -> list[Contact]:
        stmt = self._base_query().where(ContactModel.assigned_to == salesperson_id).offset(skip).limit(limit)
        result = await self._session.execute(stmt)
        return [self._to_entity(m) for m in result.scalars().all()]

    async def get_unassigned(self, skip: int = 0, limit: int = 100) -> list[Contact]:
        stmt = self._base_query().where(ContactModel.assigned_to.is_(None)).offset(skip).limit(limit)
        result = await self._session.execute(stmt)
        return [self._to_entity(m) for m in result.scalars().all()]

    async def search(self, query: str, skip: int = 0, limit: int = 100) -> list[Contact]:
        stmt = self._base_query().where(
            or_(
                ContactModel.phone_number.ilike(f"%{query}%"),
                ContactModel.name.ilike(f"%{query}%"),
            )
        ).offset(skip).limit(limit)
        result = await self._session.execute(stmt)
        return [self._to_entity(m) for m in result.scalars().all()]

    async def bulk_create(self, contacts: list[Contact]) -> tuple[int, int, list[str]]:
        success, errors_list = 0, []
        for contact in contacts:
            try:
                existing = await self.get_by_phone(
                    contact.phone_number.normalized if isinstance(contact.phone_number, PhoneNumber) else contact.phone_number
                )
                if existing:
                    errors_list.append(f"Duplicate: {contact.phone_number}")
                    continue
                model = self._to_model(contact)
                self._session.add(model)
                success += 1
            except Exception as e:
                errors_list.append(str(e))
        await self._session.flush()
        return success, len(errors_list), errors_list

    async def bulk_update_category(self, contact_ids: list[UUID], category_id: UUID, category_name: str) -> int:
        from sqlalchemy import update as sa_update
        stmt = (
            sa_update(ContactModel)
            .where(ContactModel.tenant_id == self._tenant_id)
            .where(ContactModel.id.in_(contact_ids))
            .values(category_id=category_id, category_name=category_name)
        )
        result = await self._session.execute(stmt)
        await self._session.flush()
        return result.rowcount

    async def bulk_assign(self, contact_ids: list[UUID], salesperson_id: UUID) -> int:
        from sqlalchemy import update as sa_update
        stmt = (
            sa_update(ContactModel)
            .where(ContactModel.tenant_id == self._tenant_id)
            .where(ContactModel.id.in_(contact_ids))
            .values(assigned_to=salesperson_id, assigned_at=datetime.utcnow())
        )
        result = await self._session.execute(stmt)
        await self._session.flush()
        return result.rowcount

    # ─────────────── Analytics Query Helpers ───────────────

    async def get_stage_counts(self, tenant_id: UUID | None = None) -> dict[str, int]:
        """Count contacts per funnel stage."""
        tid = tenant_id or self._tenant_id
        stmt = (
            select(ContactModel.current_stage, func.count())
            .where(ContactModel.tenant_id == tid)
            .group_by(ContactModel.current_stage)
        )
        result = await self._session.execute(stmt)
        return {row[0]: row[1] for row in result.all()}

    async def count_new_contacts(
        self, tenant_id: UUID | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> int:
        """Count contacts created within a date range."""
        tid = tenant_id or self._tenant_id
        stmt = (
            select(func.count())
            .select_from(ContactModel)
            .where(ContactModel.tenant_id == tid)
        )
        if start_date:
            stmt = stmt.where(ContactModel.created_at >= start_date)
        if end_date:
            stmt = stmt.where(ContactModel.created_at <= end_date)
        result = await self._session.execute(stmt)
        return result.scalar_one()

    async def get_contacts_with_stages(
        self, tenant_id: UUID | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[dict]:
        """Get contacts with their stage info for funnel calculation."""
        tid = tenant_id or self._tenant_id
        stmt = (
            select(
                ContactModel.id,
                ContactModel.current_stage,
                ContactModel.category_name,
                ContactModel.source_name,
                ContactModel.assigned_to,
                ContactModel.total_revenue,
                ContactModel.created_at,
            )
            .where(ContactModel.tenant_id == tid)
        )
        if start_date:
            stmt = stmt.where(ContactModel.created_at >= start_date)
        if end_date:
            stmt = stmt.where(ContactModel.created_at <= end_date)
        result = await self._session.execute(stmt)
        return [
            {
                "id": row.id,
                "current_stage": row.current_stage,
                "category_name": row.category_name,
                "source_name": row.source_name,
                "assigned_to": row.assigned_to,
                "total_revenue": row.total_revenue,
                "created_at": row.created_at,
            }
            for row in result.all()
        ]

    async def get_contacts_grouped_by_source(
        self, tenant_id: UUID | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> dict[str, list[dict]]:
        """Get contacts grouped by source_name."""
        contacts = await self.get_contacts_with_stages(tenant_id, start_date, end_date)
        groups: dict[str, list[dict]] = {}
        for c in contacts:
            src = c.get("source_name") or "unknown"
            groups.setdefault(src, []).append(c)
        return groups

    async def get_contacts_grouped_by_category(
        self, tenant_id: UUID | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> dict[str, list[dict]]:
        """Get contacts grouped by category_name."""
        contacts = await self.get_contacts_with_stages(tenant_id, start_date, end_date)
        groups: dict[str, list[dict]] = {}
        for c in contacts:
            cat = c.get("category_name") or "uncategorized"
            groups.setdefault(cat, []).append(c)
        return groups

    async def get_stage_transitions(
        self, tenant_id: UUID | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[dict]:
        """Get stage transition counts (simplified — based on current stage distribution)."""
        # In a full implementation this would track stage change events.
        # For now, derive from current stage distribution.
        stage_counts = await self.get_stage_counts(tenant_id)
        stages = [
            "lead_acquired", "sms_sent", "sms_delivered",
            "call_attempted", "call_answered", "invoice_issued", "payment_received",
        ]
        transitions = []
        for i in range(len(stages) - 1):
            from_count = stage_counts.get(stages[i], 0)
            to_count = stage_counts.get(stages[i + 1], 0)
            transitions.append({
                "from_stage": stages[i],
                "to_stage": stages[i + 1],
                "count": min(from_count, to_count),
            })
        return transitions

    async def get_salespeople(self, tenant_id: UUID | None = None) -> list[dict]:
        """Get distinct salespeople from assigned contacts."""
        tid = tenant_id or self._tenant_id
        stmt = (
            select(
                ContactModel.assigned_to,
                func.count().label("contact_count"),
            )
            .where(ContactModel.tenant_id == tid)
            .where(ContactModel.assigned_to.isnot(None))
            .group_by(ContactModel.assigned_to)
        )
        result = await self._session.execute(stmt)
        return [
            {"salesperson_id": row.assigned_to, "contact_count": row.contact_count}
            for row in result.all()
        ]

    async def get_rfm_distribution(self, tenant_id: UUID | None = None) -> dict[str, int]:
        """Count contacts per RFM segment."""
        tid = tenant_id or self._tenant_id
        stmt = (
            select(ContactModel.rfm_segment, func.count())
            .where(ContactModel.tenant_id == tid)
            .where(ContactModel.rfm_segment.isnot(None))
            .group_by(ContactModel.rfm_segment)
        )
        result = await self._session.execute(stmt)
        return {row[0]: row[1] for row in result.all()}

    async def get_contacts_by_rfm_segment(
        self, segment: str, skip: int = 0, limit: int = 100,
    ) -> list[Contact]:
        """Get contacts in a specific RFM segment."""
        return await self.get_by_segment(segment, skip, limit)


class LeadCategoryRepository(SqlAlchemyRepository[LeadCategoryModel, LeadCategory], ILeadCategoryRepository):
    """SQLAlchemy implementation of ILeadCategoryRepository."""

    def __init__(self, session, tenant_id: UUID):
        super().__init__(session, tenant_id, LeadCategoryModel)

    def _to_entity(self, model: LeadCategoryModel) -> LeadCategory:
        return LeadCategory(
            id=model.id,
            tenant_id=model.tenant_id,
            name=model.name,
            description=model.description,
            parent_id=model.parent_id,
            color=model.color,
            is_active=model.is_active,
            metadata=model.metadata_ or {},
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    def _to_model(self, entity: LeadCategory) -> LeadCategoryModel:
        return LeadCategoryModel(
            id=entity.id,
            tenant_id=entity.tenant_id,
            name=entity.name,
            description=entity.description,
            parent_id=entity.parent_id,
            color=entity.color,
            is_active=entity.is_active,
            metadata_=entity.metadata,
        )

    async def get_by_name(self, name: str) -> LeadCategory | None:
        stmt = self._base_query().where(LeadCategoryModel.name == name)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def get_children(self, parent_id: UUID) -> list[LeadCategory]:
        stmt = self._base_query().where(LeadCategoryModel.parent_id == parent_id)
        result = await self._session.execute(stmt)
        return [self._to_entity(m) for m in result.scalars().all()]

    async def get_root_categories(self) -> list[LeadCategory]:
        stmt = self._base_query().where(LeadCategoryModel.parent_id.is_(None))
        result = await self._session.execute(stmt)
        return [self._to_entity(m) for m in result.scalars().all()]

    async def get_with_contact_count(self) -> list[tuple[LeadCategory, int]]:
        stmt = (
            select(LeadCategoryModel, func.count(ContactModel.id))
            .outerjoin(ContactModel, ContactModel.category_id == LeadCategoryModel.id)
            .where(LeadCategoryModel.tenant_id == self._tenant_id)
            .group_by(LeadCategoryModel.id)
        )
        result = await self._session.execute(stmt)
        return [(self._to_entity(row[0]), row[1]) for row in result.all()]


class LeadSourceRepository(SqlAlchemyRepository[LeadSourceModel, LeadSourceConfig], ILeadSourceRepository):
    """SQLAlchemy implementation of ILeadSourceRepository."""

    def __init__(self, session, tenant_id: UUID):
        super().__init__(session, tenant_id, LeadSourceModel)

    def _to_entity(self, model: LeadSourceModel) -> LeadSourceConfig:
        from src.core.domain import LeadSource
        return LeadSourceConfig(
            id=model.id,
            tenant_id=model.tenant_id,
            name=model.name,
            source_type=LeadSource(model.source_type),
            file_path=model.file_path,
            category_id=model.category_id,
            is_active=model.is_active,
            last_import_at=model.last_import_at,
            total_leads=model.total_leads,
            metadata=model.metadata_ or {},
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    def _to_model(self, entity: LeadSourceConfig) -> LeadSourceModel:
        return LeadSourceModel(
            id=entity.id,
            tenant_id=entity.tenant_id,
            name=entity.name,
            source_type=entity.source_type.value if hasattr(entity.source_type, 'value') else entity.source_type,
            file_path=entity.file_path,
            category_id=entity.category_id,
            is_active=entity.is_active,
            last_import_at=entity.last_import_at,
            total_leads=entity.total_leads,
            metadata_=entity.metadata,
        )

    async def get_by_name(self, name: str) -> LeadSourceConfig | None:
        stmt = self._base_query().where(LeadSourceModel.name == name)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def get_active_sources(self) -> list[LeadSourceConfig]:
        stmt = self._base_query().where(LeadSourceModel.is_active.is_(True))
        result = await self._session.execute(stmt)
        return [self._to_entity(m) for m in result.scalars().all()]

    async def update_import_stats(self, source_id: UUID, total_leads: int) -> None:
        from sqlalchemy import update as sa_update
        stmt = (
            sa_update(LeadSourceModel)
            .where(LeadSourceModel.id == source_id)
            .where(LeadSourceModel.tenant_id == self._tenant_id)
            .values(total_leads=total_leads, last_import_at=datetime.utcnow())
        )
        await self._session.execute(stmt)
        await self._session.flush()

