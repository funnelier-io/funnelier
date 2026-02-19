"""
Core Interfaces - Data Source Connectors
Abstract interfaces for ETL and data source adapters
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, AsyncIterator

from pydantic import BaseModel


class DataSourceConfig(BaseModel):
    """Base configuration for data sources."""

    name: str
    source_type: str
    enabled: bool = True
    metadata: dict[str, Any] = {}


class FileSourceConfig(DataSourceConfig):
    """Configuration for file-based data sources."""

    source_type: str = "file"
    file_path: str | None = None
    file_pattern: str | None = None  # Glob pattern for multiple files
    encoding: str = "utf-8"
    delimiter: str = ","  # For CSV


class DatabaseSourceConfig(DataSourceConfig):
    """Configuration for database data sources."""

    source_type: str = "database"
    connection_string: str
    database_name: str | None = None
    collection_or_table: str | None = None
    query: str | None = None


class APISourceConfig(DataSourceConfig):
    """Configuration for API data sources."""

    source_type: str = "api"
    base_url: str
    endpoint: str
    method: str = "GET"
    headers: dict[str, str] = {}
    auth_type: str | None = None  # bearer, api_key, basic
    auth_config: dict[str, str] = {}
    pagination_type: str | None = None  # offset, cursor, page
    pagination_config: dict[str, Any] = {}


@dataclass
class DataRecord:
    """Represents a single record from a data source."""

    data: dict[str, Any]
    source_name: str
    source_type: str
    extracted_at: datetime
    raw_data: Any | None = None  # Original raw data if needed


@dataclass
class ExtractionResult:
    """Result of a data extraction operation."""

    records: list[DataRecord]
    total_count: int
    success_count: int
    error_count: int
    errors: list[str]
    started_at: datetime
    completed_at: datetime
    metadata: dict[str, Any] = None

    @property
    def duration_seconds(self) -> float:
        return (self.completed_at - self.started_at).total_seconds()


class IDataSourceConnector(ABC):
    """
    Abstract interface for data source connectors.
    Each connector type implements this interface.
    """

    @property
    @abstractmethod
    def source_type(self) -> str:
        """Get the type of this data source."""
        pass

    @property
    @abstractmethod
    def config(self) -> DataSourceConfig:
        """Get the configuration for this connector."""
        pass

    @abstractmethod
    async def connect(self) -> bool:
        """
        Establish connection to the data source.
        Returns True if successful.
        """
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Close the connection."""
        pass

    @abstractmethod
    async def test_connection(self) -> tuple[bool, str]:
        """
        Test the connection.
        Returns (success, message).
        """
        pass

    @abstractmethod
    async def extract(
        self,
        batch_size: int = 1000,
        **kwargs: Any,
    ) -> AsyncIterator[list[DataRecord]]:
        """
        Extract data in batches.
        Yields batches of records for memory efficiency.
        """
        pass

    @abstractmethod
    async def get_schema(self) -> dict[str, Any]:
        """
        Get the schema/structure of the data source.
        Returns field names and types if available.
        """
        pass

    @abstractmethod
    async def get_record_count(self) -> int | None:
        """
        Get total record count if available.
        Returns None if count is not available.
        """
        pass


class IFileConnector(IDataSourceConnector):
    """Interface for file-based connectors (CSV, Excel, JSON)."""

    @abstractmethod
    async def read_file(self, file_path: Path | str) -> list[DataRecord]:
        """Read all records from a single file."""
        pass

    @abstractmethod
    async def read_files(
        self,
        file_paths: list[Path | str],
    ) -> AsyncIterator[list[DataRecord]]:
        """Read records from multiple files."""
        pass


class IDatabaseConnector(IDataSourceConnector):
    """Interface for database connectors."""

    @abstractmethod
    async def execute_query(
        self,
        query: str,
        params: dict[str, Any] | None = None,
    ) -> list[DataRecord]:
        """Execute a query and return results."""
        pass

    @abstractmethod
    async def get_tables(self) -> list[str]:
        """Get list of tables/collections."""
        pass


class IAPIConnector(IDataSourceConnector):
    """Interface for API connectors."""

    @abstractmethod
    async def fetch(
        self,
        endpoint: str | None = None,
        params: dict[str, Any] | None = None,
    ) -> list[DataRecord]:
        """Fetch data from API endpoint."""
        pass

    @abstractmethod
    async def fetch_paginated(
        self,
        endpoint: str | None = None,
        params: dict[str, Any] | None = None,
    ) -> AsyncIterator[list[DataRecord]]:
        """Fetch paginated data from API."""
        pass


class DataTransformationType(str, Enum):
    """Types of data transformations."""

    MAP = "map"
    FILTER = "filter"
    AGGREGATE = "aggregate"
    JOIN = "join"
    NORMALIZE = "normalize"
    VALIDATE = "validate"
    ENRICH = "enrich"


@dataclass
class TransformationRule:
    """Defines a data transformation rule."""

    name: str
    type: DataTransformationType
    config: dict[str, Any]
    order: int = 0


class IDataTransformer(ABC):
    """
    Interface for data transformation.
    Transforms extracted data before loading.
    """

    @abstractmethod
    async def transform(
        self,
        records: list[DataRecord],
        rules: list[TransformationRule],
    ) -> list[DataRecord]:
        """Apply transformation rules to records."""
        pass

    @abstractmethod
    def validate(self, records: list[DataRecord]) -> tuple[list[DataRecord], list[str]]:
        """
        Validate records.
        Returns (valid_records, error_messages).
        """
        pass


class IDataLoader(ABC):
    """
    Interface for loading transformed data.
    Loads data into the target system.
    """

    @abstractmethod
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
        pass

    @abstractmethod
    async def bulk_load(
        self,
        records: list[DataRecord],
        target: str,
        batch_size: int = 1000,
    ) -> tuple[int, int, list[str]]:
        """
        Bulk load records in batches.
        """
        pass


@dataclass
class ETLPipelineConfig:
    """Configuration for an ETL pipeline."""

    name: str
    source_config: DataSourceConfig
    transformations: list[TransformationRule]
    target: str
    schedule: str | None = None  # Cron expression
    enabled: bool = True
    batch_size: int = 1000
    retry_count: int = 3
    retry_delay_seconds: int = 60


class IETLPipeline(ABC):
    """
    Interface for ETL pipeline orchestration.
    Coordinates extract, transform, load operations.
    """

    @property
    @abstractmethod
    def config(self) -> ETLPipelineConfig:
        """Get pipeline configuration."""
        pass

    @abstractmethod
    async def run(self) -> ExtractionResult:
        """Run the complete ETL pipeline."""
        pass

    @abstractmethod
    async def run_extract(self) -> list[DataRecord]:
        """Run only the extract phase."""
        pass

    @abstractmethod
    async def run_transform(self, records: list[DataRecord]) -> list[DataRecord]:
        """Run only the transform phase."""
        pass

    @abstractmethod
    async def run_load(self, records: list[DataRecord]) -> tuple[int, int, list[str]]:
        """Run only the load phase."""
        pass

