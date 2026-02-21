"""
Base SQLAlchemy Repository Implementation

Generic repository that bridges SQLAlchemy models to domain entities.
All queries are scoped by tenant_id for multi-tenant isolation.
"""

from abc import abstractmethod
from typing import Any, Generic, TypeVar, Type
from uuid import UUID

from sqlalchemy import select, func, delete, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.database.session import Base

TModel = TypeVar("TModel", bound=Base)
TEntity = TypeVar("TEntity")


class SqlAlchemyRepository(Generic[TModel, TEntity]):
    """
    Base repository using SQLAlchemy async sessions.
    Provides CRUD operations with automatic tenant scoping.
    """

    def __init__(self, session: AsyncSession, tenant_id: UUID, model_class: Type[TModel]):
        self._session = session
        self._tenant_id = tenant_id
        self._model_class = model_class

    @property
    def tenant_id(self) -> UUID:
        return self._tenant_id

    @abstractmethod
    def _to_entity(self, model: TModel) -> TEntity:
        """Convert SQLAlchemy model to domain entity."""
        ...

    @abstractmethod
    def _to_model(self, entity: TEntity) -> TModel:
        """Convert domain entity to SQLAlchemy model."""
        ...

    def _base_query(self):
        """Base query scoped to tenant."""
        stmt = select(self._model_class)
        if hasattr(self._model_class, "tenant_id"):
            stmt = stmt.where(self._model_class.tenant_id == self._tenant_id)
        return stmt

    async def get(self, id: UUID) -> TEntity | None:
        """Get entity by ID."""
        stmt = self._base_query().where(self._model_class.id == id)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def get_by_id(self, id: UUID) -> TEntity | None:
        """Alias for get()."""
        return await self.get(id)

    async def get_all(
        self,
        skip: int = 0,
        limit: int = 100,
        **filters: Any,
    ) -> list[TEntity]:
        """Get all entities with pagination."""
        stmt = self._base_query()
        for key, value in filters.items():
            if hasattr(self._model_class, key) and value is not None:
                stmt = stmt.where(getattr(self._model_class, key) == value)
        stmt = stmt.offset(skip).limit(limit)
        result = await self._session.execute(stmt)
        return [self._to_entity(m) for m in result.scalars().all()]

    async def add(self, entity: TEntity) -> TEntity:
        """Add a new entity."""
        model = self._to_model(entity)
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return self._to_entity(model)

    async def update(self, entity: TEntity) -> TEntity:
        """Update an existing entity."""
        model = self._to_model(entity)
        merged = await self._session.merge(model)
        await self._session.flush()
        await self._session.refresh(merged)
        return self._to_entity(merged)

    async def delete(self, id: UUID) -> bool:
        """Delete an entity by ID."""
        stmt = delete(self._model_class).where(
            self._model_class.id == id,
        )
        if hasattr(self._model_class, "tenant_id"):
            stmt = stmt.where(self._model_class.tenant_id == self._tenant_id)
        result = await self._session.execute(stmt)
        await self._session.flush()
        return result.rowcount > 0

    async def count(self, **filters: Any) -> int:
        """Count entities matching filters."""
        stmt = select(func.count()).select_from(self._model_class)
        if hasattr(self._model_class, "tenant_id"):
            stmt = stmt.where(self._model_class.tenant_id == self._tenant_id)
        for key, value in filters.items():
            if hasattr(self._model_class, key) and value is not None:
                stmt = stmt.where(getattr(self._model_class, key) == value)
        result = await self._session.execute(stmt)
        return result.scalar_one()

    async def exists(self, id: UUID) -> bool:
        """Check if entity exists."""
        stmt = select(func.count()).select_from(self._model_class).where(
            self._model_class.id == id,
        )
        if hasattr(self._model_class, "tenant_id"):
            stmt = stmt.where(self._model_class.tenant_id == self._tenant_id)
        result = await self._session.execute(stmt)
        return result.scalar_one() > 0

    async def save(self, entity: TEntity) -> TEntity:
        """Save (upsert) an aggregate."""
        model = self._to_model(entity)
        merged = await self._session.merge(model)
        await self._session.flush()
        await self._session.refresh(merged)
        return self._to_entity(merged)

