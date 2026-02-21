"""
ETL Pipeline

Orchestrates the Extract-Transform-Load process with
configurable pipelines for different data types.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from src.core.interfaces import (
    DataRecord,
    DataSourceConfig,
    ExtractionResult,
    TransformationRule,
)

from .extractors import BaseExtractor, ExtractorRegistry
from .transformers import BaseTransformer, TransformerRegistry
from .loaders import BaseLoader, LoaderRegistry, LoadResult


class PipelineStatus(str, Enum):
    """Pipeline execution status."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class PipelineConfig:
    """Configuration for an ETL pipeline."""

    name: str
    source_type: str
    source_config: dict[str, Any]
    transformer_name: str
    transformation_rules: list[dict[str, Any]] = field(default_factory=list)
    loader_name: str = "mongodb"
    loader_config: dict[str, Any] = field(default_factory=dict)
    target_collection: str = ""
    batch_size: int = 1000
    upsert: bool = True
    enabled: bool = True
    schedule: str | None = None  # Cron expression
    retry_count: int = 3
    retry_delay_seconds: int = 60
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class PipelineResult:
    """Result of a pipeline execution."""

    pipeline_name: str
    status: PipelineStatus
    started_at: datetime
    completed_at: datetime | None = None
    extraction_result: ExtractionResult | None = None
    transform_count: int = 0
    load_result: LoadResult | None = None
    errors: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def duration_seconds(self) -> float | None:
        if self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None

    @property
    def success(self) -> bool:
        return self.status == PipelineStatus.COMPLETED

    def to_dict(self) -> dict[str, Any]:
        """Convert result to dictionary."""
        return {
            "pipeline_name": self.pipeline_name,
            "status": self.status.value,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_seconds": self.duration_seconds,
            "extraction": {
                "total_count": self.extraction_result.total_count if self.extraction_result else 0,
                "success_count": self.extraction_result.success_count if self.extraction_result else 0,
                "error_count": self.extraction_result.error_count if self.extraction_result else 0,
            },
            "transform_count": self.transform_count,
            "load": {
                "success_count": self.load_result.success_count if self.load_result else 0,
                "created_count": self.load_result.created_count if self.load_result else 0,
                "updated_count": self.load_result.updated_count if self.load_result else 0,
                "error_count": self.load_result.error_count if self.load_result else 0,
            },
            "errors": self.errors,
            "metadata": self.metadata,
        }


class ETLPipeline:
    """
    ETL Pipeline orchestrator.
    Coordinates extraction, transformation, and loading of data.
    """

    def __init__(
        self,
        config: PipelineConfig,
        tenant_id: str | None = None,
    ):
        self._config = config
        self._tenant_id = tenant_id
        self._extractor: BaseExtractor | None = None
        self._transformer: BaseTransformer | None = None
        self._loader: BaseLoader | None = None
        self._status = PipelineStatus.PENDING
        self._result: PipelineResult | None = None

    @property
    def config(self) -> PipelineConfig:
        return self._config

    @property
    def status(self) -> PipelineStatus:
        return self._status

    @property
    def result(self) -> PipelineResult | None:
        return self._result

    async def run(self) -> PipelineResult:
        """Run the complete ETL pipeline."""
        self._status = PipelineStatus.RUNNING
        self._result = PipelineResult(
            pipeline_name=self._config.name,
            status=PipelineStatus.RUNNING,
            started_at=datetime.utcnow(),
        )

        try:
            # Initialize components
            await self._initialize_components()

            # Extract
            records = await self._run_extract()
            if not records:
                self._result.errors.append("No records extracted")
                self._complete(PipelineStatus.COMPLETED)
                return self._result

            # Transform
            transformed = await self._run_transform(records)
            self._result.transform_count = len(transformed)

            # Load
            if transformed:
                await self._run_load(transformed)

            self._complete(PipelineStatus.COMPLETED)

        except Exception as e:
            self._result.errors.append(f"Pipeline error: {str(e)}")
            self._complete(PipelineStatus.FAILED)

        finally:
            await self._cleanup()

        return self._result

    async def run_extract_only(self) -> list[DataRecord]:
        """Run only the extract phase."""
        await self._initialize_extractor()
        return await self._run_extract()

    async def run_transform_only(self, records: list[DataRecord]) -> list[DataRecord]:
        """Run only the transform phase."""
        await self._initialize_transformer()
        return await self._run_transform(records)

    async def run_load_only(self, records: list[DataRecord]) -> LoadResult:
        """Run only the load phase."""
        await self._initialize_loader()
        return await self._loader.load_with_result(
            records,
            self._config.target_collection,
            self._config.upsert,
        )

    async def _initialize_components(self) -> None:
        """Initialize all pipeline components."""
        await self._initialize_extractor()
        await self._initialize_transformer()
        await self._initialize_loader()

    async def _initialize_extractor(self) -> None:
        """Initialize the extractor."""
        # Build source config
        source_config = self._build_source_config()

        # Create extractor
        self._extractor = ExtractorRegistry.create(
            source_config,
            self._tenant_id,
        )

        # Connect
        connected = await self._extractor.connect()
        if not connected:
            raise RuntimeError(f"Failed to connect to source: {self._config.source_type}")

    async def _initialize_transformer(self) -> None:
        """Initialize the transformer."""
        self._transformer = TransformerRegistry.create(
            self._config.transformer_name,
            self._tenant_id,
        )

    async def _initialize_loader(self) -> None:
        """Initialize the loader."""
        loader_config = dict(self._config.loader_config)
        self._loader = LoaderRegistry.create(
            self._config.loader_name,
            tenant_id=self._tenant_id,
            **loader_config,
        )

        connected = await self._loader.connect()
        if not connected:
            raise RuntimeError(f"Failed to connect to loader: {self._config.loader_name}")

    def _build_source_config(self) -> DataSourceConfig:
        """Build source configuration from pipeline config."""
        from src.core.interfaces import FileSourceConfig, DatabaseSourceConfig, APISourceConfig

        source_type = self._config.source_type
        source_cfg = self._config.source_config

        if source_type in ("csv", "excel", "json"):
            return FileSourceConfig(
                name=self._config.name,
                source_type=source_type,
                file_path=source_cfg.get("file_path"),
                file_pattern=source_cfg.get("file_pattern"),
                encoding=source_cfg.get("encoding", "utf-8"),
                delimiter=source_cfg.get("delimiter", ","),
                metadata=source_cfg.get("metadata", {}),
            )
        elif source_type == "mongodb":
            return DatabaseSourceConfig(
                name=self._config.name,
                source_type=source_type,
                connection_string=source_cfg.get("connection_string", ""),
                database_name=source_cfg.get("database_name"),
                collection_or_table=source_cfg.get("collection"),
                query=source_cfg.get("query"),
            )
        elif source_type in ("api", "kavenegar"):
            return APISourceConfig(
                name=self._config.name,
                source_type=source_type,
                base_url=source_cfg.get("base_url", ""),
                endpoint=source_cfg.get("endpoint", ""),
                method=source_cfg.get("method", "GET"),
                headers=source_cfg.get("headers", {}),
                auth_type=source_cfg.get("auth_type"),
                auth_config=source_cfg.get("auth_config", {}),
                pagination_type=source_cfg.get("pagination_type"),
                pagination_config=source_cfg.get("pagination_config", {}),
                metadata=source_cfg.get("metadata", {}),
            )
        else:
            return DataSourceConfig(
                name=self._config.name,
                source_type=source_type,
                metadata=source_cfg,
            )

    async def _run_extract(self) -> list[DataRecord]:
        """Run the extraction phase."""
        all_records: list[DataRecord] = []

        async for batch in self._extractor.extract(batch_size=self._config.batch_size):
            all_records.extend(batch)

        # Create extraction result
        self._result.extraction_result = ExtractionResult(
            records=all_records,
            total_count=len(all_records),
            success_count=len(all_records),
            error_count=0,
            errors=[],
            started_at=self._result.started_at,
            completed_at=datetime.utcnow(),
        )

        return all_records

    async def _run_transform(self, records: list[DataRecord]) -> list[DataRecord]:
        """Run the transformation phase."""
        # Build transformation rules
        rules = [
            TransformationRule(
                name=rule.get("name", f"rule_{i}"),
                type=rule.get("type"),
                config=rule.get("config", {}),
                order=rule.get("order", i),
            )
            for i, rule in enumerate(self._config.transformation_rules)
        ]

        # Add default normalize rule if not specified
        if not any(r.type == "normalize" for r in rules):
            rules.insert(
                0,
                TransformationRule(
                    name="normalize",
                    type="normalize",
                    config={},
                    order=-1,
                ),
            )

        return await self._transformer.transform(records, rules)

    async def _run_load(self, records: list[DataRecord]) -> None:
        """Run the load phase."""
        self._result.load_result = await self._loader.load_with_result(
            records,
            self._config.target_collection,
            self._config.upsert,
        )

        if self._result.load_result.errors:
            self._result.errors.extend(self._result.load_result.errors)

    def _complete(self, status: PipelineStatus) -> None:
        """Mark pipeline as complete."""
        self._status = status
        self._result.status = status
        self._result.completed_at = datetime.utcnow()

    async def _cleanup(self) -> None:
        """Clean up resources."""
        if self._extractor:
            await self._extractor.disconnect()
        if self._loader:
            await self._loader.disconnect()


class PipelineManager:
    """
    Manages multiple ETL pipelines.
    Provides registration, execution, and monitoring.
    """

    def __init__(self, tenant_id: str | None = None):
        self._tenant_id = tenant_id
        self._pipelines: dict[str, PipelineConfig] = {}
        self._results: dict[str, list[PipelineResult]] = {}

    def register_pipeline(self, config: PipelineConfig) -> None:
        """Register a pipeline configuration."""
        self._pipelines[config.name] = config

    def unregister_pipeline(self, name: str) -> bool:
        """Unregister a pipeline."""
        if name in self._pipelines:
            del self._pipelines[name]
            return True
        return False

    def get_pipeline(self, name: str) -> PipelineConfig | None:
        """Get pipeline configuration by name."""
        return self._pipelines.get(name)

    def list_pipelines(self) -> list[str]:
        """List all registered pipeline names."""
        return list(self._pipelines.keys())

    async def run_pipeline(self, name: str) -> PipelineResult:
        """Run a registered pipeline."""
        config = self._pipelines.get(name)
        if not config:
            raise ValueError(f"Pipeline not found: {name}")

        if not config.enabled:
            raise ValueError(f"Pipeline is disabled: {name}")

        pipeline = ETLPipeline(config, self._tenant_id)
        result = await pipeline.run()

        # Store result
        if name not in self._results:
            self._results[name] = []
        self._results[name].append(result)

        # Keep only last 100 results
        if len(self._results[name]) > 100:
            self._results[name] = self._results[name][-100:]

        return result

    async def run_all_pipelines(self) -> dict[str, PipelineResult]:
        """Run all enabled pipelines."""
        results = {}
        for name, config in self._pipelines.items():
            if config.enabled:
                try:
                    results[name] = await self.run_pipeline(name)
                except Exception as e:
                    results[name] = PipelineResult(
                        pipeline_name=name,
                        status=PipelineStatus.FAILED,
                        started_at=datetime.utcnow(),
                        completed_at=datetime.utcnow(),
                        errors=[str(e)],
                    )
        return results

    def get_pipeline_history(
        self,
        name: str,
        limit: int = 10,
    ) -> list[PipelineResult]:
        """Get execution history for a pipeline."""
        history = self._results.get(name, [])
        return history[-limit:]

    def get_last_result(self, name: str) -> PipelineResult | None:
        """Get the last execution result for a pipeline."""
        history = self._results.get(name, [])
        return history[-1] if history else None

