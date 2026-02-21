"""
Base Extractor and Registry

Provides the abstract base class for all extractors and a registry
for dynamic extractor lookup.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any, AsyncIterator, Type

from src.core.interfaces import (
    DataRecord,
    DataSourceConfig,
    ExtractionResult,
    IDataSourceConnector,
)


class BaseExtractor(IDataSourceConnector, ABC):
    """
    Abstract base class for all data extractors.
    Implements common functionality and enforces interface compliance.
    """

    def __init__(self, config: DataSourceConfig, tenant_id: str | None = None):
        self._config = config
        self._tenant_id = tenant_id
        self._connected = False
        self._connection: Any = None

    @property
    def config(self) -> DataSourceConfig:
        return self._config

    @property
    def tenant_id(self) -> str | None:
        return self._tenant_id

    @property
    def is_connected(self) -> bool:
        return self._connected

    async def __aenter__(self) -> "BaseExtractor":
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.disconnect()

    def _create_record(
        self,
        data: dict[str, Any],
        raw_data: Any | None = None,
    ) -> DataRecord:
        """Create a DataRecord from extracted data."""
        return DataRecord(
            data=data,
            source_name=self._config.name,
            source_type=self.source_type,
            extracted_at=datetime.utcnow(),
            raw_data=raw_data,
        )

    def _create_extraction_result(
        self,
        records: list[DataRecord],
        errors: list[str],
        started_at: datetime,
    ) -> ExtractionResult:
        """Create an ExtractionResult from extraction operation."""
        return ExtractionResult(
            records=records,
            total_count=len(records) + len(errors),
            success_count=len(records),
            error_count=len(errors),
            errors=errors,
            started_at=started_at,
            completed_at=datetime.utcnow(),
            metadata={
                "source_name": self._config.name,
                "source_type": self.source_type,
                "tenant_id": self._tenant_id,
            },
        )

    async def extract_all(self, batch_size: int = 1000) -> ExtractionResult:
        """
        Extract all data and return as ExtractionResult.
        Convenience method that collects all batches.
        """
        started_at = datetime.utcnow()
        all_records: list[DataRecord] = []
        all_errors: list[str] = []

        try:
            async for batch in self.extract(batch_size=batch_size):
                all_records.extend(batch)
        except Exception as e:
            all_errors.append(f"Extraction error: {str(e)}")

        return self._create_extraction_result(all_records, all_errors, started_at)


class ExtractorRegistry:
    """
    Registry for extractor types.
    Allows dynamic registration and lookup of extractors by source type.
    """

    _extractors: dict[str, Type[BaseExtractor]] = {}

    @classmethod
    def register(cls, source_type: str):
        """Decorator to register an extractor class."""

        def decorator(extractor_class: Type[BaseExtractor]):
            cls._extractors[source_type] = extractor_class
            return extractor_class

        return decorator

    @classmethod
    def get(cls, source_type: str) -> Type[BaseExtractor] | None:
        """Get extractor class by source type."""
        return cls._extractors.get(source_type)

    @classmethod
    def create(
        cls,
        config: DataSourceConfig,
        tenant_id: str | None = None,
    ) -> BaseExtractor:
        """Create an extractor instance from config."""
        extractor_class = cls._extractors.get(config.source_type)
        if not extractor_class:
            raise ValueError(f"Unknown source type: {config.source_type}")
        return extractor_class(config, tenant_id)

    @classmethod
    def list_types(cls) -> list[str]:
        """List all registered source types."""
        return list(cls._extractors.keys())

