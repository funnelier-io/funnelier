"""
ETL Connectors - CSV File Connector
For importing call logs and SMS logs from CSV files
"""

import csv
from datetime import datetime
from pathlib import Path
from typing import Any, AsyncIterator

import pandas as pd

from src.core.interfaces import (
    DataRecord,
    ExtractionResult,
    FileSourceConfig,
    IFileConnector,
)


class CSVFileConnector(IFileConnector):
    """
    Connector for CSV file data sources.
    Handles various CSV formats including call logs.
    """

    def __init__(self, config: FileSourceConfig):
        self._config = config
        self._encoding = config.encoding or "utf-8"
        self._delimiter = config.delimiter or ","

    @property
    def source_type(self) -> str:
        return "csv_file"

    @property
    def config(self) -> FileSourceConfig:
        return self._config

    async def connect(self) -> bool:
        """CSV files don't need connection, just verify file exists."""
        if self._config.file_path:
            return Path(self._config.file_path).exists()
        return True

    async def disconnect(self) -> None:
        """Nothing to disconnect for file sources."""
        pass

    async def test_connection(self) -> tuple[bool, str]:
        """Test if file is readable."""
        if not self._config.file_path:
            return False, "No file path specified"

        path = Path(self._config.file_path)
        if not path.exists():
            return False, f"File not found: {path}"

        try:
            # Try to read first few lines
            with open(path, "r", encoding=self._encoding) as f:
                reader = csv.reader(f, delimiter=self._delimiter)
                headers = next(reader, None)
                if headers:
                    return True, f"File readable. Columns: {', '.join(headers)}"
                return False, "File is empty"
        except Exception as e:
            return False, f"Error reading file: {str(e)}"

    async def extract(
        self,
        batch_size: int = 1000,
        **kwargs: Any,
    ) -> AsyncIterator[list[DataRecord]]:
        """
        Extract data from CSV file in batches.
        """
        if not self._config.file_path:
            return

        path = Path(self._config.file_path)

        try:
            # Read CSV with pandas for better handling of various formats
            df = pd.read_csv(
                path,
                encoding=self._encoding,
                delimiter=self._delimiter,
                on_bad_lines="skip",
            )

            # Process in batches
            for start in range(0, len(df), batch_size):
                end = min(start + batch_size, len(df))
                batch_df = df.iloc[start:end]

                records = []
                for _, row in batch_df.iterrows():
                    record = DataRecord(
                        data=row.to_dict(),
                        source_name=self._config.name,
                        source_type=self.source_type,
                        extracted_at=datetime.utcnow(),
                    )
                    records.append(record)

                yield records

        except Exception as e:
            raise RuntimeError(f"Error extracting from CSV: {str(e)}")

    async def read_file(self, file_path: Path | str) -> list[DataRecord]:
        """Read all records from a single CSV file."""
        path = Path(file_path)
        records = []

        try:
            df = pd.read_csv(
                path,
                encoding=self._encoding,
                delimiter=self._delimiter,
                on_bad_lines="skip",
            )

            for _, row in df.iterrows():
                record = DataRecord(
                    data=row.to_dict(),
                    source_name=self._config.name,
                    source_type=self.source_type,
                    extracted_at=datetime.utcnow(),
                )
                records.append(record)

        except Exception as e:
            raise RuntimeError(f"Error reading CSV file {path}: {str(e)}")

        return records

    async def read_files(
        self,
        file_paths: list[Path | str],
    ) -> AsyncIterator[list[DataRecord]]:
        """Read records from multiple CSV files."""
        for file_path in file_paths:
            records = await self.read_file(file_path)
            if records:
                yield records

    async def get_schema(self) -> dict[str, Any]:
        """Get column names and inferred types from CSV."""
        if not self._config.file_path:
            return {}

        path = Path(self._config.file_path)

        try:
            df = pd.read_csv(
                path,
                encoding=self._encoding,
                delimiter=self._delimiter,
                nrows=100,  # Sample first 100 rows for schema
                on_bad_lines="skip",
            )

            schema = {
                "columns": list(df.columns),
                "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
                "sample_values": {
                    col: df[col].dropna().head(3).tolist()
                    for col in df.columns
                },
            }
            return schema

        except Exception as e:
            return {"error": str(e)}

    async def get_record_count(self) -> int | None:
        """Get total number of records in CSV."""
        if not self._config.file_path:
            return None

        path = Path(self._config.file_path)

        try:
            with open(path, "r", encoding=self._encoding) as f:
                return sum(1 for _ in f) - 1  # Subtract header
        except Exception:
            return None


class CallLogCSVTransformer:
    """
    Transformer for mobile call log CSV files.
    Handles the specific format from call log apps.
    """

    # Column mappings for common call log formats
    COLUMN_MAPPINGS = {
        # Standard format
        "Number": "phone_number",
        "Name:": "contact_name",
        "Type": "call_type",
        "Duration": "duration",
        "Date": "date",
        "Time": "time",
        "SIM": "sim",
        # Alternative names
        "Phone": "phone_number",
        "Call Type": "call_type",
        "Call Duration": "duration",
    }

    def transform_call_log_record(
        self,
        data: dict[str, Any],
        salesperson_id: str | None = None,
        salesperson_name: str | None = None,
    ) -> dict[str, Any]:
        """
        Transform a raw call log record into standardized format.
        """
        # Map columns
        transformed = {}
        for raw_col, standard_col in self.COLUMN_MAPPINGS.items():
            if raw_col in data:
                transformed[standard_col] = data[raw_col]

        # Parse phone number
        phone = transformed.get("phone_number", "")
        if phone:
            # Clean phone number
            phone = "".join(filter(str.isdigit, str(phone)))
            if phone.startswith("98") and len(phone) == 12:
                phone = phone[2:]
            elif phone.startswith("0") and len(phone) == 11:
                phone = phone[1:]
            transformed["phone_number"] = phone

        # Parse duration
        duration_str = transformed.get("duration", "0")
        if isinstance(duration_str, str):
            # Handle "X sec" format
            duration_str = duration_str.lower().replace("sec", "").strip()
            try:
                transformed["duration_seconds"] = int(duration_str)
            except ValueError:
                transformed["duration_seconds"] = 0
        else:
            transformed["duration_seconds"] = int(duration_str or 0)

        # Parse call type
        call_type = str(transformed.get("call_type", "")).lower()
        type_mapping = {
            "incoming": "incoming",
            "incomming": "incoming",  # Handle typo
            "outgoing": "outgoing",
            "missed": "missed",
        }
        transformed["call_type"] = type_mapping.get(call_type, "missed")

        # Parse date and time
        date_str = transformed.get("date", "")
        time_str = transformed.get("time", "")
        if date_str and time_str:
            try:
                # Handle various date formats
                datetime_str = f"{date_str.strip()} {time_str.strip()}"
                # Try common formats
                for fmt in [
                    "%d %b %Y %I:%M %p",
                    "%d %b %Y %H:%M",
                    "%Y-%m-%d %H:%M:%S",
                    "%Y-%m-%d %I:%M %p",
                ]:
                    try:
                        transformed["call_datetime"] = datetime.strptime(
                            datetime_str, fmt
                        )
                        break
                    except ValueError:
                        continue
            except Exception:
                transformed["call_datetime"] = None

        # Add salesperson info
        if salesperson_id:
            transformed["salesperson_id"] = salesperson_id
        if salesperson_name:
            transformed["salesperson_name"] = salesperson_name

        return transformed

