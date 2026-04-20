"""
Tenants Module - Repository Implementations
Concrete SQLAlchemy repositories for tenant domain entities.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select, func

from src.infrastructure.database.repositories import SqlAlchemyRepository
from src.infrastructure.database.models.tenants import (
    TenantModel,
    TenantUserModel,
    DataSourceConnectionModel,
)
from src.modules.tenants.domain.entities import Tenant, TenantUser, DataSourceConnection


class TenantRepository:
    """
    Repository for Tenant CRUD operations.
    Not tenant-scoped (operates across tenants for admin/onboarding).
    """

    def __init__(self, session):
        self._session = session

    async def get_by_id(self, tenant_id: UUID) -> Tenant | None:
        stmt = select(TenantModel).where(TenantModel.id == tenant_id)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def get_by_slug(self, slug: str) -> Tenant | None:
        stmt = select(TenantModel).where(TenantModel.slug == slug)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def slug_exists(self, slug: str) -> bool:
        stmt = select(func.count()).select_from(TenantModel).where(TenantModel.slug == slug)
        result = await self._session.execute(stmt)
        return result.scalar_one() > 0

    async def get_all(
        self,
        skip: int = 0,
        limit: int = 100,
        is_active: bool | None = None,
        search: str | None = None,
    ) -> tuple[list[Tenant], int]:
        stmt = select(TenantModel)
        count_stmt = select(func.count()).select_from(TenantModel)

        if is_active is not None:
            stmt = stmt.where(TenantModel.is_active == is_active)
            count_stmt = count_stmt.where(TenantModel.is_active == is_active)
        if search:
            pattern = f"%{search}%"
            stmt = stmt.where(
                TenantModel.name.ilike(pattern) | TenantModel.slug.ilike(pattern)
            )
            count_stmt = count_stmt.where(
                TenantModel.name.ilike(pattern) | TenantModel.slug.ilike(pattern)
            )

        total = (await self._session.execute(count_stmt)).scalar_one()
        stmt = stmt.offset(skip).limit(limit).order_by(TenantModel.created_at.desc())
        result = await self._session.execute(stmt)
        tenants = [self._to_entity(m) for m in result.scalars().all()]
        return tenants, total

    async def create(self, tenant: Tenant) -> Tenant:
        model = TenantModel(
            id=tenant.id,
            name=tenant.name,
            slug=tenant.slug,
            email=tenant.email,
            phone=tenant.phone,
            settings=tenant.settings,
            plan=tenant.plan,
            is_active=tenant.is_active,
            trial_ends_at=tenant.trial_ends_at,
            max_contacts=tenant.max_contacts,
            max_sms_per_month=tenant.max_sms_per_month,
            max_users=tenant.max_users,
            current_contacts=tenant.current_contacts,
            current_month_sms=tenant.current_month_sms,
            metadata_=tenant.metadata,
        )
        self._session.add(model)
        await self._session.flush()
        return self._to_entity(model)

    async def update(self, tenant_id: UUID, **kwargs: Any) -> Tenant | None:
        stmt = select(TenantModel).where(TenantModel.id == tenant_id)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if not model:
            return None
        for key, value in kwargs.items():
            if hasattr(model, key) and value is not None:
                setattr(model, key, value)
        await self._session.flush()
        return self._to_entity(model)

    async def count(self) -> int:
        stmt = select(func.count()).select_from(TenantModel)
        result = await self._session.execute(stmt)
        return result.scalar_one()

    def _to_entity(self, model: TenantModel) -> Tenant:
        return Tenant(
            id=model.id,
            name=model.name,
            slug=model.slug,
            email=model.email,
            phone=model.phone,
            settings=model.settings or {},
            plan=model.plan,
            is_active=model.is_active,
            trial_ends_at=model.trial_ends_at,
            max_contacts=model.max_contacts,
            max_sms_per_month=model.max_sms_per_month,
            max_users=model.max_users,
            current_contacts=model.current_contacts,
            current_month_sms=model.current_month_sms,
            metadata=model.metadata_ or {},
        )

