"""
Core Interfaces - Repository Pattern
Abstract base classes for repositories following DDD
"""

from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar
from uuid import UUID

from src.core.domain.entities import AggregateRoot, Entity

TEntity = TypeVar("TEntity", bound=Entity)
TAggregate = TypeVar("TAggregate", bound=AggregateRoot)
TId = TypeVar("TId", bound=UUID | int | str)


class IRepository(ABC, Generic[TEntity, TId]):
    """
    Base repository interface.
    Defines standard CRUD operations.
    """

    @abstractmethod
    async def get_by_id(self, id: TId) -> TEntity | None:
        """Get entity by ID."""
        pass

    @abstractmethod
    async def get_all(
        self,
        skip: int = 0,
        limit: int = 100,
        **filters: Any,
    ) -> list[TEntity]:
        """Get all entities with pagination and filtering."""
        pass

    @abstractmethod
    async def add(self, entity: TEntity) -> TEntity:
        """Add a new entity."""
        pass

    @abstractmethod
    async def update(self, entity: TEntity) -> TEntity:
        """Update an existing entity."""
        pass

    @abstractmethod
    async def delete(self, id: TId) -> bool:
        """Delete an entity by ID."""
        pass

    @abstractmethod
    async def count(self, **filters: Any) -> int:
        """Count entities matching filters."""
        pass

    @abstractmethod
    async def exists(self, id: TId) -> bool:
        """Check if entity exists."""
        pass


class ITenantRepository(IRepository[TEntity, TId]):
    """
    Tenant-scoped repository interface.
    All operations are scoped to a specific tenant.
    """

    @property
    @abstractmethod
    def tenant_id(self) -> UUID:
        """Get the current tenant ID."""
        pass

    @abstractmethod
    async def get_by_id(self, id: TId) -> TEntity | None:
        """Get entity by ID within tenant scope."""
        pass


class IAggregateRepository(IRepository[TAggregate, TId]):
    """
    Repository for aggregate roots.
    Handles domain events on save.
    """

    @abstractmethod
    async def save(self, aggregate: TAggregate) -> TAggregate:
        """
        Save aggregate and publish domain events.
        This is the preferred method for aggregates.
        """
        pass


class IUnitOfWork(ABC):
    """
    Unit of Work pattern interface.
    Manages transactions across multiple repositories.
    """

    @abstractmethod
    async def __aenter__(self) -> "IUnitOfWork":
        """Enter the unit of work context."""
        pass

    @abstractmethod
    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit the unit of work context."""
        pass

    @abstractmethod
    async def commit(self) -> None:
        """Commit the transaction."""
        pass

    @abstractmethod
    async def rollback(self) -> None:
        """Rollback the transaction."""
        pass


class IEventPublisher(ABC):
    """
    Event publisher interface.
    Publishes domain events to message bus.
    """

    @abstractmethod
    async def publish(self, event: Any) -> None:
        """Publish a single event."""
        pass

    @abstractmethod
    async def publish_many(self, events: list[Any]) -> None:
        """Publish multiple events."""
        pass


class IEventSubscriber(ABC):
    """
    Event subscriber interface.
    Subscribes to domain events.
    """

    @abstractmethod
    async def subscribe(self, event_type: str, handler: Any) -> None:
        """Subscribe to an event type."""
        pass

    @abstractmethod
    async def unsubscribe(self, event_type: str, handler: Any) -> None:
        """Unsubscribe from an event type."""
        pass


class ICacheService(ABC):
    """
    Cache service interface.
    """

    @abstractmethod
    async def get(self, key: str) -> Any | None:
        """Get value from cache."""
        pass

    @abstractmethod
    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        """Set value in cache."""
        pass

    @abstractmethod
    async def delete(self, key: str) -> None:
        """Delete value from cache."""
        pass

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        pass

    @abstractmethod
    async def clear_pattern(self, pattern: str) -> None:
        """Clear all keys matching pattern."""
        pass

