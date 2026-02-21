"""
Base Transformer and Registry

Provides the abstract base class for all transformers and a registry
for dynamic transformer lookup.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Type

from src.core.interfaces import DataRecord, DataTransformationType, IDataTransformer, TransformationRule


@dataclass
class TransformationError:
    """Represents a transformation error."""

    record_index: int
    field: str | None
    error: str
    raw_data: Any | None = None


class BaseTransformer(IDataTransformer, ABC):
    """
    Abstract base class for all data transformers.
    Implements common transformation logic.
    """

    def __init__(self, tenant_id: str | None = None):
        self._tenant_id = tenant_id
        self._errors: list[TransformationError] = []

    @property
    def tenant_id(self) -> str | None:
        return self._tenant_id

    @property
    def errors(self) -> list[TransformationError]:
        return self._errors

    def clear_errors(self) -> None:
        """Clear accumulated errors."""
        self._errors = []

    async def transform(
        self,
        records: list[DataRecord],
        rules: list[TransformationRule],
    ) -> list[DataRecord]:
        """Apply transformation rules to records."""
        self.clear_errors()

        # Sort rules by order
        sorted_rules = sorted(rules, key=lambda r: r.order)

        result = records
        for rule in sorted_rules:
            result = await self._apply_rule(result, rule)

        return result

    async def _apply_rule(
        self,
        records: list[DataRecord],
        rule: TransformationRule,
    ) -> list[DataRecord]:
        """Apply a single transformation rule."""
        if rule.type == DataTransformationType.MAP:
            return await self._apply_map(records, rule.config)
        elif rule.type == DataTransformationType.FILTER:
            return await self._apply_filter(records, rule.config)
        elif rule.type == DataTransformationType.NORMALIZE:
            return await self._apply_normalize(records, rule.config)
        elif rule.type == DataTransformationType.VALIDATE:
            return await self._apply_validate(records, rule.config)
        elif rule.type == DataTransformationType.ENRICH:
            return await self._apply_enrich(records, rule.config)
        else:
            return records

    async def _apply_map(
        self,
        records: list[DataRecord],
        config: dict[str, Any],
    ) -> list[DataRecord]:
        """Apply field mapping transformation."""
        field_map = config.get("field_map", {})
        result = []

        for record in records:
            new_data = {}
            for target_field, source_field in field_map.items():
                if isinstance(source_field, str):
                    new_data[target_field] = record.data.get(source_field)
                elif callable(source_field):
                    try:
                        new_data[target_field] = source_field(record.data)
                    except Exception as e:
                        self._errors.append(
                            TransformationError(
                                record_index=len(result),
                                field=target_field,
                                error=str(e),
                            )
                        )
            result.append(
                DataRecord(
                    data=new_data,
                    source_name=record.source_name,
                    source_type=record.source_type,
                    extracted_at=record.extracted_at,
                    raw_data=record.raw_data,
                )
            )

        return result

    async def _apply_filter(
        self,
        records: list[DataRecord],
        config: dict[str, Any],
    ) -> list[DataRecord]:
        """Apply filter transformation."""
        conditions = config.get("conditions", [])
        result = []

        for record in records:
            include = True
            for condition in conditions:
                field = condition.get("field")
                operator = condition.get("operator")
                value = condition.get("value")

                record_value = record.data.get(field)

                if operator == "eq":
                    include = record_value == value
                elif operator == "ne":
                    include = record_value != value
                elif operator == "gt":
                    include = record_value is not None and record_value > value
                elif operator == "lt":
                    include = record_value is not None and record_value < value
                elif operator == "gte":
                    include = record_value is not None and record_value >= value
                elif operator == "lte":
                    include = record_value is not None and record_value <= value
                elif operator == "in":
                    include = record_value in value
                elif operator == "not_in":
                    include = record_value not in value
                elif operator == "exists":
                    include = (record_value is not None) == value
                elif operator == "contains":
                    include = value in str(record_value) if record_value else False

                if not include:
                    break

            if include:
                result.append(record)

        return result

    async def _apply_normalize(
        self,
        records: list[DataRecord],
        config: dict[str, Any],
    ) -> list[DataRecord]:
        """Apply normalization transformation."""
        # To be implemented by subclasses
        return records

    async def _apply_validate(
        self,
        records: list[DataRecord],
        config: dict[str, Any],
    ) -> list[DataRecord]:
        """Apply validation transformation."""
        required_fields = config.get("required_fields", [])
        result = []

        for idx, record in enumerate(records):
            valid = True
            for field in required_fields:
                if not record.data.get(field):
                    valid = False
                    self._errors.append(
                        TransformationError(
                            record_index=idx,
                            field=field,
                            error=f"Required field '{field}' is missing or empty",
                            raw_data=record.raw_data,
                        )
                    )

            if valid:
                result.append(record)

        return result

    async def _apply_enrich(
        self,
        records: list[DataRecord],
        config: dict[str, Any],
    ) -> list[DataRecord]:
        """Apply enrichment transformation."""
        # To be implemented by subclasses
        return records

    def validate(self, records: list[DataRecord]) -> tuple[list[DataRecord], list[str]]:
        """
        Validate records.
        Returns (valid_records, error_messages).
        """
        valid_records = []
        error_messages = []

        for idx, record in enumerate(records):
            is_valid, error = self._validate_record(record)
            if is_valid:
                valid_records.append(record)
            else:
                error_messages.append(f"Record {idx}: {error}")

        return valid_records, error_messages

    @abstractmethod
    def _validate_record(self, record: DataRecord) -> tuple[bool, str | None]:
        """Validate a single record. Returns (is_valid, error_message)."""
        pass


class TransformerRegistry:
    """
    Registry for transformer types.
    Allows dynamic registration and lookup of transformers.
    """

    _transformers: dict[str, Type[BaseTransformer]] = {}

    @classmethod
    def register(cls, name: str):
        """Decorator to register a transformer class."""

        def decorator(transformer_class: Type[BaseTransformer]):
            cls._transformers[name] = transformer_class
            return transformer_class

        return decorator

    @classmethod
    def get(cls, name: str) -> Type[BaseTransformer] | None:
        """Get transformer class by name."""
        return cls._transformers.get(name)

    @classmethod
    def create(cls, name: str, tenant_id: str | None = None) -> BaseTransformer:
        """Create a transformer instance."""
        transformer_class = cls._transformers.get(name)
        if not transformer_class:
            raise ValueError(f"Unknown transformer: {name}")
        return transformer_class(tenant_id)

    @classmethod
    def list_transformers(cls) -> list[str]:
        """List all registered transformers."""
        return list(cls._transformers.keys())

