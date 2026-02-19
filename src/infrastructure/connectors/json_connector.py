"""
ETL Connectors - JSON File Connector
For importing VoIP call logs from JSON files
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, AsyncIterator

from src.core.interfaces import (
    DataRecord,
    FileSourceConfig,
    IFileConnector,
)


class JSONFileConnector(IFileConnector):
    """
    Connector for JSON file data sources.
    Handles VoIP call logs and other JSON-based data.
    """

    def __init__(self, config: FileSourceConfig):
        self._config = config
        self._encoding = config.encoding or "utf-8"
        # Path to array of records in JSON (e.g., "data.calls")
        self._records_path = config.metadata.get("records_path")

    @property
    def source_type(self) -> str:
        return "json_file"

    @property
    def config(self) -> FileSourceConfig:
        return self._config

    async def connect(self) -> bool:
        """JSON files don't need connection, just verify file exists."""
        if self._config.file_path:
            return Path(self._config.file_path).exists()
        return True

    async def disconnect(self) -> None:
        """Nothing to disconnect for file sources."""
        pass

    async def test_connection(self) -> tuple[bool, str]:
        """Test if JSON file is readable and valid."""
        if not self._config.file_path:
            return False, "No file path specified"

        path = Path(self._config.file_path)
        if not path.exists():
            return False, f"File not found: {path}"

        try:
            with open(path, "r", encoding=self._encoding) as f:
                data = json.load(f)

            # Get record count
            records = self._extract_records_from_data(data)
            if isinstance(records, list):
                return True, f"File readable. Found {len(records)} records."
            return True, "File readable."
        except json.JSONDecodeError as e:
            return False, f"Invalid JSON: {str(e)}"
        except Exception as e:
            return False, f"Error reading file: {str(e)}"

    def _extract_records_from_data(self, data: Any) -> list[dict]:
        """Extract records array from JSON data."""
        if self._records_path:
            # Navigate to the specified path
            current = data
            for key in self._records_path.split("."):
                if isinstance(current, dict) and key in current:
                    current = current[key]
                else:
                    return []
            return current if isinstance(current, list) else [current]

        # If no path specified, assume root is either list or dict
        if isinstance(data, list):
            return data
        elif isinstance(data, dict):
            # Look for common array keys
            for key in ["data", "records", "items", "calls", "results"]:
                if key in data and isinstance(data[key], list):
                    return data[key]
            # Return the dict as a single record
            return [data]

        return []

    async def extract(
        self,
        batch_size: int = 1000,
        **kwargs: Any,
    ) -> AsyncIterator[list[DataRecord]]:
        """
        Extract data from JSON file in batches.
        """
        if not self._config.file_path:
            return

        path = Path(self._config.file_path)

        try:
            with open(path, "r", encoding=self._encoding) as f:
                data = json.load(f)

            records_data = self._extract_records_from_data(data)

            # Process in batches
            for start in range(0, len(records_data), batch_size):
                end = min(start + batch_size, len(records_data))
                batch = records_data[start:end]

                records = []
                for item in batch:
                    record = DataRecord(
                        data=item if isinstance(item, dict) else {"value": item},
                        source_name=self._config.name,
                        source_type=self.source_type,
                        extracted_at=datetime.utcnow(),
                        raw_data=item,
                    )
                    records.append(record)

                yield records

        except Exception as e:
            raise RuntimeError(f"Error extracting from JSON: {str(e)}")

    async def read_file(self, file_path: Path | str) -> list[DataRecord]:
        """Read all records from a single JSON file."""
        path = Path(file_path)
        records = []

        try:
            with open(path, "r", encoding=self._encoding) as f:
                data = json.load(f)

            records_data = self._extract_records_from_data(data)

            for item in records_data:
                record = DataRecord(
                    data=item if isinstance(item, dict) else {"value": item},
                    source_name=self._config.name,
                    source_type=self.source_type,
                    extracted_at=datetime.utcnow(),
                    raw_data=item,
                )
                records.append(record)

        except Exception as e:
            raise RuntimeError(f"Error reading JSON file {path}: {str(e)}")

        return records

    async def read_files(
        self,
        file_paths: list[Path | str],
    ) -> AsyncIterator[list[DataRecord]]:
        """Read records from multiple JSON files."""
        for file_path in file_paths:
            records = await self.read_file(file_path)
            if records:
                yield records

    async def get_schema(self) -> dict[str, Any]:
        """Infer schema from JSON file."""
        if not self._config.file_path:
            return {}

        path = Path(self._config.file_path)

        try:
            with open(path, "r", encoding=self._encoding) as f:
                data = json.load(f)

            records = self._extract_records_from_data(data)

            if not records:
                return {"error": "No records found"}

            # Analyze first few records for schema
            sample = records[:10]
            all_keys = set()
            key_types = {}
            key_samples = {}

            for record in sample:
                if isinstance(record, dict):
                    for key, value in record.items():
                        all_keys.add(key)

                        value_type = type(value).__name__
                        if key not in key_types:
                            key_types[key] = set()
                        key_types[key].add(value_type)

                        if key not in key_samples:
                            key_samples[key] = []
                        if len(key_samples[key]) < 3 and value is not None:
                            key_samples[key].append(value)

            schema = {
                "total_records": len(records),
                "fields": list(all_keys),
                "field_types": {k: list(v) for k, v in key_types.items()},
                "sample_values": key_samples,
            }
            return schema

        except Exception as e:
            return {"error": str(e)}

    async def get_record_count(self) -> int | None:
        """Get total number of records in JSON file."""
        if not self._config.file_path:
            return None

        path = Path(self._config.file_path)

        try:
            with open(path, "r", encoding=self._encoding) as f:
                data = json.load(f)

            records = self._extract_records_from_data(data)
            return len(records)
        except Exception:
            return None


class VoIPCallLogTransformer:
    """
    Transformer for VoIP call log JSON files.
    Handles Asterisk CDR format and similar.
    """

    # Common field mappings for VoIP CDR
    FIELD_MAPPINGS = {
        # Asterisk CDR format
        "src": "caller_number",
        "dst": "callee_number",
        "duration": "duration_seconds",
        "billsec": "billable_seconds",
        "disposition": "call_status",
        "calldate": "call_datetime",
        "channel": "channel",
        "dstchannel": "dest_channel",
        "uniqueid": "call_id",
        "accountcode": "account",
        # Common alternatives
        "caller_id": "caller_number",
        "called_number": "callee_number",
        "call_duration": "duration_seconds",
        "status": "call_status",
        "timestamp": "call_datetime",
        "call_id": "call_id",
        "extension": "extension",
    }

    # Status mappings
    STATUS_MAPPINGS = {
        "answered": "incoming",
        "no answer": "missed",
        "busy": "missed",
        "failed": "missed",
        "congestion": "missed",
        # Numeric status codes
        "0": "missed",
        "1": "incoming",
    }

    def transform_voip_record(
        self,
        data: dict[str, Any],
        default_direction: str = "incoming",
    ) -> dict[str, Any]:
        """
        Transform a raw VoIP CDR record into standardized format.
        """
        transformed = {}

        # Map fields
        for raw_field, standard_field in self.FIELD_MAPPINGS.items():
            if raw_field in data and data[raw_field] is not None:
                transformed[standard_field] = data[raw_field]

        # Also copy any unmapped fields
        for key, value in data.items():
            if key not in self.FIELD_MAPPINGS and value is not None:
                transformed[key] = value

        # Determine phone number (external party)
        # Usually we want the customer's number, not internal extension
        caller = transformed.get("caller_number", "")
        callee = transformed.get("callee_number", "")
        extension = transformed.get("extension", "")

        # Heuristic: external numbers are longer than extensions
        if len(str(caller)) > len(str(callee)):
            transformed["phone_number"] = self._clean_phone(caller)
            transformed["call_type"] = "incoming"
        else:
            transformed["phone_number"] = self._clean_phone(callee)
            transformed["call_type"] = "outgoing"

        # Parse duration
        duration = transformed.get("duration_seconds") or transformed.get("billable_seconds", 0)
        try:
            transformed["duration_seconds"] = int(duration)
        except (ValueError, TypeError):
            transformed["duration_seconds"] = 0

        # Parse status/disposition
        status = str(transformed.get("call_status", "")).lower()
        transformed["call_type"] = self.STATUS_MAPPINGS.get(
            status,
            transformed.get("call_type", default_direction),
        )

        # Parse datetime
        call_datetime = transformed.get("call_datetime")
        if call_datetime:
            if isinstance(call_datetime, str):
                for fmt in [
                    "%Y-%m-%d %H:%M:%S",
                    "%Y-%m-%dT%H:%M:%S",
                    "%Y-%m-%dT%H:%M:%SZ",
                    "%d/%m/%Y %H:%M:%S",
                ]:
                    try:
                        transformed["call_datetime"] = datetime.strptime(
                            call_datetime, fmt
                        )
                        break
                    except ValueError:
                        continue
            elif isinstance(call_datetime, (int, float)):
                # Unix timestamp
                transformed["call_datetime"] = datetime.fromtimestamp(call_datetime)

        return transformed

    def _clean_phone(self, phone: Any) -> str:
        """Clean and normalize phone number."""
        phone_str = str(phone)
        # Remove non-digits
        phone_clean = "".join(filter(str.isdigit, phone_str))

        # Handle Iranian formats
        if phone_clean.startswith("98") and len(phone_clean) == 12:
            phone_clean = phone_clean[2:]
        elif phone_clean.startswith("0") and len(phone_clean) == 11:
            phone_clean = phone_clean[1:]

        return phone_clean

