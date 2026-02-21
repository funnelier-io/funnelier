"""
CSV Extractor

Extracts data from CSV files, supporting:
- Single file extraction
- Batch processing of multiple files
- Custom delimiters and encoding
- Call logs and SMS logs formats
"""

import csv
from datetime import datetime
from pathlib import Path
from typing import Any, AsyncIterator

import aiofiles

from src.core.interfaces import DataRecord, FileSourceConfig

from .base import BaseExtractor, ExtractorRegistry


@ExtractorRegistry.register("csv")
class CSVExtractor(BaseExtractor):
    """
    Extractor for CSV files.
    Supports call logs from sales team phones and SMS delivery reports.
    """

    def __init__(self, config: FileSourceConfig, tenant_id: str | None = None):
        super().__init__(config, tenant_id)
        self._file_config: FileSourceConfig = config
        self._files: list[Path] = []

    @property
    def source_type(self) -> str:
        return "csv"

    async def connect(self) -> bool:
        """Discover files matching pattern."""
        try:
            if self._file_config.file_path:
                path = Path(self._file_config.file_path)
                if path.exists():
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
        """Test if files are accessible."""
        if not self._files:
            success = await self.connect()
            if not success:
                return False, "No files found matching pattern"

        for file_path in self._files:
            if not file_path.exists():
                return False, f"File not found: {file_path}"
            if not file_path.is_file():
                return False, f"Not a file: {file_path}"

        return True, f"Found {len(self._files)} file(s)"

    async def extract(
        self,
        batch_size: int = 1000,
        **kwargs: Any,
    ) -> AsyncIterator[list[DataRecord]]:
        """Extract records from CSV files in batches."""
        if not self._connected:
            await self.connect()

        for file_path in self._files:
            async for batch in self._extract_file(file_path, batch_size):
                yield batch

    async def _extract_file(
        self,
        file_path: Path,
        batch_size: int,
    ) -> AsyncIterator[list[DataRecord]]:
        """Extract records from a single CSV file."""
        batch: list[DataRecord] = []

        async with aiofiles.open(
            file_path,
            mode="r",
            encoding=self._file_config.encoding,
        ) as f:
            content = await f.read()

        # Parse CSV content
        reader = csv.DictReader(
            content.splitlines(),
            delimiter=self._file_config.delimiter,
        )

        for row in reader:
            # Clean up field names (remove BOM and whitespace)
            cleaned_row = {
                k.strip().lstrip("\ufeff"): v.strip() if v else None
                for k, v in row.items()
                if k
            }

            record = self._create_record(
                data=cleaned_row,
                raw_data={"file": str(file_path), "row": row},
            )
            batch.append(record)

            if len(batch) >= batch_size:
                yield batch
                batch = []

        if batch:
            yield batch

    async def get_schema(self) -> dict[str, Any]:
        """Get schema from first file."""
        if not self._files:
            await self.connect()

        if not self._files:
            return {}

        async with aiofiles.open(
            self._files[0],
            mode="r",
            encoding=self._file_config.encoding,
        ) as f:
            first_line = await f.readline()

        reader = csv.reader(
            [first_line],
            delimiter=self._file_config.delimiter,
        )
        headers = next(reader, [])

        return {
            "fields": [h.strip().lstrip("\ufeff") for h in headers],
            "file_count": len(self._files),
            "delimiter": self._file_config.delimiter,
            "encoding": self._file_config.encoding,
        }

    async def get_record_count(self) -> int | None:
        """Get approximate record count from all files."""
        if not self._files:
            await self.connect()

        total = 0
        for file_path in self._files:
            async with aiofiles.open(
                file_path,
                mode="r",
                encoding=self._file_config.encoding,
            ) as f:
                content = await f.read()
                # Count lines minus header
                total += max(0, content.count("\n"))

        return total


class CallLogCSVExtractor(CSVExtractor):
    """
    Specialized extractor for call log CSV files.
    Handles specific format from sales team phone reports.
    """

    async def _extract_file(
        self,
        file_path: Path,
        batch_size: int,
    ) -> AsyncIterator[list[DataRecord]]:
        """Extract and normalize call log records."""
        async for batch in super()._extract_file(file_path, batch_size):
            normalized_batch = []
            for record in batch:
                # Normalize call log fields
                data = record.data
                normalized = {
                    "phone_number": self._normalize_phone(data.get("phone") or data.get("number")),
                    "call_type": data.get("type") or data.get("call_type"),
                    "duration_seconds": self._parse_duration(data.get("duration")),
                    "timestamp": self._parse_timestamp(data.get("date") or data.get("timestamp")),
                    "salesperson": self._extract_salesperson(file_path),
                    "answered": self._is_answered(data),
                    "raw_data": data,
                }
                normalized_batch.append(self._create_record(normalized, record.raw_data))
            yield normalized_batch

    def _normalize_phone(self, phone: str | None) -> str | None:
        """Normalize phone number to standard format."""
        if not phone:
            return None
        # Remove non-digit characters
        digits = "".join(c for c in phone if c.isdigit())
        # Add country code if missing
        if digits.startswith("0"):
            digits = "98" + digits[1:]
        elif not digits.startswith("98"):
            digits = "98" + digits
        return digits

    def _parse_duration(self, duration: str | None) -> int:
        """Parse duration string to seconds."""
        if not duration:
            return 0
        try:
            # Handle HH:MM:SS format
            if ":" in duration:
                parts = duration.split(":")
                if len(parts) == 3:
                    h, m, s = map(int, parts)
                    return h * 3600 + m * 60 + s
                elif len(parts) == 2:
                    m, s = map(int, parts)
                    return m * 60 + s
            return int(duration)
        except ValueError:
            return 0

    def _parse_timestamp(self, timestamp: str | None) -> datetime | None:
        """Parse timestamp string to datetime."""
        if not timestamp:
            return None
        # Try common formats
        formats = [
            "%Y-%m-%d %H:%M:%S",
            "%Y/%m/%d %H:%M:%S",
            "%d/%m/%Y %H:%M:%S",
            "%Y-%m-%d",
        ]
        for fmt in formats:
            try:
                return datetime.strptime(timestamp, fmt)
            except ValueError:
                continue
        return None

    def _extract_salesperson(self, file_path: Path) -> str | None:
        """Extract salesperson name from filename."""
        # Example: report_All_01_Mar-16_Feb - asadollahi.csv
        name = file_path.stem
        if " - " in name:
            return name.split(" - ")[-1].strip()
        return None

    def _is_answered(self, data: dict[str, Any]) -> bool:
        """Determine if call was answered (1.5+ minutes = successful)."""
        duration = self._parse_duration(data.get("duration"))
        return duration >= 90  # 1.5 minutes in seconds

