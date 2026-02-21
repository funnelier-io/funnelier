"""
JSON Extractor

Extracts data from JSON files, supporting:
- VoIP call logs from Asterisk
- Nested JSON structures
- JSON Lines format
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, AsyncIterator

import aiofiles

from src.core.interfaces import DataRecord, FileSourceConfig

from .base import BaseExtractor, ExtractorRegistry


@ExtractorRegistry.register("json")
class JSONExtractor(BaseExtractor):
    """
    Extractor for JSON files.
    Primary use case: VoIP call logs from self-hosted Asterisk.
    """

    def __init__(self, config: FileSourceConfig, tenant_id: str | None = None):
        super().__init__(config, tenant_id)
        self._file_config: FileSourceConfig = config
        self._files: list[Path] = []
        # JSON-specific options
        self._json_path: str | None = config.metadata.get("json_path")
        self._format: str = config.metadata.get("format", "json")  # json or jsonl

    @property
    def source_type(self) -> str:
        return "json"

    async def connect(self) -> bool:
        """Discover JSON files matching pattern."""
        try:
            if self._file_config.file_path:
                path = Path(self._file_config.file_path)
                if path.exists() and path.suffix in (".json", ".jsonl"):
                    self._files = [path]
                else:
                    return False
            elif self._file_config.file_pattern:
                base_path = Path(self._file_config.file_pattern).parent
                pattern = Path(self._file_config.file_pattern).name
                if base_path.exists():
                    self._files = list(base_path.glob(pattern))
                else:
                    self._files = list(Path.cwd().glob(self._file_config.file_pattern))

            self._connected = bool(self._files)
            return self._connected
        except Exception:
            return False

    async def disconnect(self) -> None:
        """Clean up resources."""
        self._files = []
        self._connected = False

    async def test_connection(self) -> tuple[bool, str]:
        """Test if JSON files are accessible and valid."""
        if not self._files:
            success = await self.connect()
            if not success:
                return False, "No JSON files found matching pattern"

        for file_path in self._files:
            if not file_path.exists():
                return False, f"File not found: {file_path}"
            try:
                async with aiofiles.open(file_path, mode="r") as f:
                    content = await f.read()
                    if self._format == "jsonl":
                        # Validate first line
                        first_line = content.split("\n")[0]
                        json.loads(first_line)
                    else:
                        json.loads(content)
            except json.JSONDecodeError as e:
                return False, f"Invalid JSON in {file_path}: {str(e)}"

        return True, f"Found {len(self._files)} valid JSON file(s)"

    async def extract(
        self,
        batch_size: int = 1000,
        **kwargs: Any,
    ) -> AsyncIterator[list[DataRecord]]:
        """Extract records from JSON files in batches."""
        if not self._connected:
            await self.connect()

        for file_path in self._files:
            if self._format == "jsonl":
                async for batch in self._extract_jsonl(file_path, batch_size):
                    yield batch
            else:
                async for batch in self._extract_json(file_path, batch_size):
                    yield batch

    async def _extract_json(
        self,
        file_path: Path,
        batch_size: int,
    ) -> AsyncIterator[list[DataRecord]]:
        """Extract records from a standard JSON file."""
        async with aiofiles.open(file_path, mode="r", encoding="utf-8") as f:
            content = await f.read()

        data = json.loads(content)

        # Navigate to the target path if specified
        if self._json_path:
            for key in self._json_path.split("."):
                if isinstance(data, dict):
                    data = data.get(key, [])
                elif isinstance(data, list) and key.isdigit():
                    data = data[int(key)]

        # Ensure we have a list
        if isinstance(data, dict):
            data = [data]
        elif not isinstance(data, list):
            data = []

        batch: list[DataRecord] = []
        for item in data:
            if isinstance(item, dict):
                item["_source_file"] = file_path.name
                record = self._create_record(
                    data=item,
                    raw_data={"file": str(file_path)},
                )
                batch.append(record)

                if len(batch) >= batch_size:
                    yield batch
                    batch = []

        if batch:
            yield batch

    async def _extract_jsonl(
        self,
        file_path: Path,
        batch_size: int,
    ) -> AsyncIterator[list[DataRecord]]:
        """Extract records from a JSON Lines file."""
        batch: list[DataRecord] = []
        line_num = 0

        async with aiofiles.open(file_path, mode="r", encoding="utf-8") as f:
            async for line in f:
                line_num += 1
                line = line.strip()
                if not line:
                    continue

                try:
                    item = json.loads(line)
                    item["_source_file"] = file_path.name
                    item["_line_number"] = line_num
                    record = self._create_record(
                        data=item,
                        raw_data={"file": str(file_path), "line": line_num},
                    )
                    batch.append(record)

                    if len(batch) >= batch_size:
                        yield batch
                        batch = []
                except json.JSONDecodeError:
                    continue

        if batch:
            yield batch

    async def get_schema(self) -> dict[str, Any]:
        """Infer schema from first record."""
        if not self._files:
            await self.connect()

        if not self._files:
            return {}

        async with aiofiles.open(self._files[0], mode="r", encoding="utf-8") as f:
            content = await f.read()

        if self._format == "jsonl":
            first_line = content.split("\n")[0]
            sample = json.loads(first_line)
        else:
            data = json.loads(content)
            if self._json_path:
                for key in self._json_path.split("."):
                    if isinstance(data, dict):
                        data = data.get(key, [])
            if isinstance(data, list) and data:
                sample = data[0]
            elif isinstance(data, dict):
                sample = data
            else:
                sample = {}

        return {
            "fields": list(sample.keys()) if isinstance(sample, dict) else [],
            "format": self._format,
            "file_count": len(self._files),
        }

    async def get_record_count(self) -> int | None:
        """Get approximate record count."""
        if not self._files:
            await self.connect()

        total = 0
        for file_path in self._files:
            async with aiofiles.open(file_path, mode="r", encoding="utf-8") as f:
                content = await f.read()

            if self._format == "jsonl":
                total += sum(1 for line in content.split("\n") if line.strip())
            else:
                data = json.loads(content)
                if self._json_path:
                    for key in self._json_path.split("."):
                        if isinstance(data, dict):
                            data = data.get(key, [])
                if isinstance(data, list):
                    total += len(data)
                else:
                    total += 1

        return total


class VoIPLogExtractor(JSONExtractor):
    """
    Specialized extractor for VoIP call logs from Asterisk.
    Normalizes call data to standard format.
    """

    # Expected fields from Asterisk CDR
    ASTERISK_FIELDS = [
        "uniqueid",
        "src",
        "dst",
        "dcontext",
        "channel",
        "dstchannel",
        "lastapp",
        "lastdata",
        "start",
        "answer",
        "end",
        "duration",
        "billsec",
        "disposition",
        "amaflags",
        "accountcode",
        "userfield",
    ]

    async def _extract_json(
        self,
        file_path: Path,
        batch_size: int,
    ) -> AsyncIterator[list[DataRecord]]:
        """Extract and normalize VoIP call records."""
        async for batch in super()._extract_json(file_path, batch_size):
            normalized_batch = []
            for record in batch:
                normalized = self._normalize_voip_record(record.data)
                normalized_batch.append(
                    self._create_record(normalized, record.raw_data)
                )
            yield normalized_batch

    async def _extract_jsonl(
        self,
        file_path: Path,
        batch_size: int,
    ) -> AsyncIterator[list[DataRecord]]:
        """Extract and normalize VoIP call records from JSONL."""
        async for batch in super()._extract_jsonl(file_path, batch_size):
            normalized_batch = []
            for record in batch:
                normalized = self._normalize_voip_record(record.data)
                normalized_batch.append(
                    self._create_record(normalized, record.raw_data)
                )
            yield normalized_batch

    def _normalize_voip_record(self, data: dict[str, Any]) -> dict[str, Any]:
        """Normalize VoIP record to standard call log format."""
        # Extract phone number from source or destination
        src = data.get("src", "")
        dst = data.get("dst", "")

        # Determine call direction and extract external number
        is_outbound = self._is_internal_number(src) and not self._is_internal_number(dst)
        external_number = dst if is_outbound else src

        # Parse timestamps
        start_time = self._parse_timestamp(data.get("start"))
        answer_time = self._parse_timestamp(data.get("answer"))
        end_time = self._parse_timestamp(data.get("end"))

        # Calculate duration
        duration = data.get("billsec") or data.get("duration") or 0
        if isinstance(duration, str):
            try:
                duration = int(duration)
            except ValueError:
                duration = 0

        # Determine call status
        disposition = data.get("disposition", "").upper()
        answered = disposition == "ANSWERED"
        successful = answered and duration >= 90  # 1.5 minutes threshold

        return {
            "call_id": data.get("uniqueid"),
            "phone_number": self._normalize_phone(external_number),
            "direction": "outbound" if is_outbound else "inbound",
            "extension": src if is_outbound else dst,
            "start_time": start_time,
            "answer_time": answer_time,
            "end_time": end_time,
            "duration_seconds": duration,
            "disposition": disposition,
            "answered": answered,
            "successful": successful,
            "channel": data.get("channel"),
            "context": data.get("dcontext"),
            "account_code": data.get("accountcode"),
            "raw_data": data,
        }

    def _is_internal_number(self, number: str) -> bool:
        """Check if number is internal extension."""
        if not number:
            return False
        # Internal extensions are typically short (3-4 digits)
        digits = "".join(c for c in number if c.isdigit())
        return len(digits) <= 4

    def _normalize_phone(self, phone: str | None) -> str | None:
        """Normalize phone number to standard format."""
        if not phone:
            return None
        digits = "".join(c for c in phone if c.isdigit())
        if digits.startswith("0"):
            digits = "98" + digits[1:]
        elif not digits.startswith("98"):
            digits = "98" + digits
        return digits if len(digits) >= 10 else None

    def _parse_timestamp(self, timestamp: str | None) -> datetime | None:
        """Parse timestamp string to datetime."""
        if not timestamp:
            return None
        formats = [
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%dT%H:%M:%S.%f",
        ]
        for fmt in formats:
            try:
                return datetime.strptime(timestamp, fmt)
            except ValueError:
                continue
        return None

