"""
Base Loader and Registry

Provides the abstract base class for all loaders and a registry
for dynamic loader lookup.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Type

from src.core.interfaces import DataRecord, IDataLoader


@dataclass
class LoadResult:
    """Result of a load operation."""

    success_count: int
    error_count: int
    errors: list[str]
    created_count: int = 0
    updated_count: int = 0
    skipped_count: int = 0
    started_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def total_count(self) -> int:
        return self.success_count + self.error_count

    @property
    def duration_seconds(self) -> float | None:
        if self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None

    def complete(self) -> None:
        """Mark the load operation as complete."""
        self.completed_at = datetime.utcnow()


class BaseLoader(IDataLoader, ABC):
    """
    Abstract base class for all data loaders.
    Implements common loading logic.
    """

    def __init__(self, tenant_id: str | None = None):
        self._tenant_id = tenant_id
        self._connection: Any = None
        self._connected = False

    @property
    def tenant_id(self) -> str | None:
        return self._tenant_id

    @property
    def is_connected(self) -> bool:
        return self._connected

    async def __aenter__(self) -> "BaseLoader":
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.disconnect()

    @abstractmethod
    async def connect(self) -> bool:
        """Establish connection to the target."""
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Close the connection."""
        pass

    async def load(
        self,
        records: list[DataRecord],
        target: str,
        upsert: bool = True,
    ) -> tuple[int, int, list[str]]:
        """
        Load records into target.
        Returns (success_count, error_count, errors).
        """
        result = await self.load_with_result(records, target, upsert)
        return result.success_count, result.error_count, result.errors

    async def bulk_load(
        self,
        records: list[DataRecord],
        target: str,
        batch_size: int = 1000,
    ) -> tuple[int, int, list[str]]:
        """
        Bulk load records in batches.
        """
        total_success = 0
        total_errors = 0
        all_errors: list[str] = []

        # Process in batches
        for i in range(0, len(records), batch_size):
            batch = records[i : i + batch_size]
            success, errors, error_msgs = await self.load(batch, target)
            total_success += success
            total_errors += errors
            all_errors.extend(error_msgs)

        return total_success, total_errors, all_errors

    @abstractmethod
    async def load_with_result(
        self,
        records: list[DataRecord],
        target: str,
        upsert: bool = True,
    ) -> LoadResult:
        """
        Load records and return detailed result.
        """
        pass

    def _prepare_record(self, record: DataRecord) -> dict[str, Any]:
        """Prepare a record for loading."""
        data = dict(record.data)

        # Remove internal metadata fields
        data.pop("raw_data", None)

        # Add tracking fields
        data["_source_name"] = record.source_name
        data["_source_type"] = record.source_type
        data["_extracted_at"] = record.extracted_at.isoformat()
        data["_loaded_at"] = datetime.utcnow().isoformat()

        # Add tenant ID if available
        if self._tenant_id:
            data["tenant_id"] = self._tenant_id

        return data


class LoaderRegistry:
    """
    Registry for loader types.
    Allows dynamic registration and lookup of loaders.
    """

    _loaders: dict[str, Type[BaseLoader]] = {}

    @classmethod
    def register(cls, name: str):
        """Decorator to register a loader class."""

        def decorator(loader_class: Type[BaseLoader]):
            cls._loaders[name] = loader_class
            return loader_class

        return decorator

    @classmethod
    def get(cls, name: str) -> Type[BaseLoader] | None:
        """Get loader class by name."""
        return cls._loaders.get(name)

    @classmethod
    def create(cls, name: str, tenant_id: str | None = None, **kwargs) -> BaseLoader:
        """Create a loader instance."""
        loader_class = cls._loaders.get(name)
        if not loader_class:
            raise ValueError(f"Unknown loader: {name}")
        return loader_class(tenant_id=tenant_id, **kwargs)

    @classmethod
    def list_loaders(cls) -> list[str]:
        """List all registered loaders."""
        return list(cls._loaders.keys())

