"""
ETL Connectors - Excel File Connector
For importing leads from Excel files
"""

from datetime import datetime
from pathlib import Path
from typing import Any, AsyncIterator

import pandas as pd

from src.core.interfaces import (
    DataRecord,
    FileSourceConfig,
    IFileConnector,
)


class ExcelFileConnector(IFileConnector):
    """
    Connector for Excel file data sources.
    Handles .xlsx and .xls files for lead imports.
    """

    def __init__(self, config: FileSourceConfig):
        self._config = config
        self._sheet_name = config.metadata.get("sheet_name", 0)

    @property
    def source_type(self) -> str:
        return "excel_file"

    @property
    def config(self) -> FileSourceConfig:
        return self._config

    async def connect(self) -> bool:
        """Excel files don't need connection, just verify file exists."""
        if self._config.file_path:
            return Path(self._config.file_path).exists()
        return True

    async def disconnect(self) -> None:
        """Nothing to disconnect for file sources."""
        pass

    async def test_connection(self) -> tuple[bool, str]:
        """Test if Excel file is readable."""
        if not self._config.file_path:
            return False, "No file path specified"

        path = Path(self._config.file_path)
        if not path.exists():
            return False, f"File not found: {path}"

        try:
            # Try to read first few rows
            df = pd.read_excel(path, sheet_name=self._sheet_name, nrows=5)
            columns = list(df.columns)
            return True, f"File readable. Columns: {', '.join(str(c) for c in columns)}"
        except Exception as e:
            return False, f"Error reading file: {str(e)}"

    async def extract(
        self,
        batch_size: int = 1000,
        **kwargs: Any,
    ) -> AsyncIterator[list[DataRecord]]:
        """
        Extract data from Excel file in batches.
        """
        if not self._config.file_path:
            return

        path = Path(self._config.file_path)

        try:
            df = pd.read_excel(path, sheet_name=self._sheet_name)

            # Process in batches
            for start in range(0, len(df), batch_size):
                end = min(start + batch_size, len(df))
                batch_df = df.iloc[start:end]

                records = []
                for _, row in batch_df.iterrows():
                    # Convert row to dict, handling NaN values
                    data = {}
                    for col, value in row.items():
                        if pd.notna(value):
                            data[col] = value
                        else:
                            data[col] = None

                    record = DataRecord(
                        data=data,
                        source_name=self._config.name,
                        source_type=self.source_type,
                        extracted_at=datetime.utcnow(),
                    )
                    records.append(record)

                yield records

        except Exception as e:
            raise RuntimeError(f"Error extracting from Excel: {str(e)}")

    async def read_file(self, file_path: Path | str) -> list[DataRecord]:
        """Read all records from a single Excel file."""
        path = Path(file_path)
        records = []

        try:
            df = pd.read_excel(path, sheet_name=self._sheet_name)

            for _, row in df.iterrows():
                data = {}
                for col, value in row.items():
                    if pd.notna(value):
                        data[col] = value
                    else:
                        data[col] = None

                record = DataRecord(
                    data=data,
                    source_name=self._config.name,
                    source_type=self.source_type,
                    extracted_at=datetime.utcnow(),
                )
                records.append(record)

        except Exception as e:
            raise RuntimeError(f"Error reading Excel file {path}: {str(e)}")

        return records

    async def read_files(
        self,
        file_paths: list[Path | str],
    ) -> AsyncIterator[list[DataRecord]]:
        """Read records from multiple Excel files."""
        for file_path in file_paths:
            records = await self.read_file(file_path)
            if records:
                yield records

    async def get_schema(self) -> dict[str, Any]:
        """Get column names and types from Excel file."""
        if not self._config.file_path:
            return {}

        path = Path(self._config.file_path)

        try:
            df = pd.read_excel(
                path,
                sheet_name=self._sheet_name,
                nrows=100,
            )

            # Get sheet names
            xls = pd.ExcelFile(path)
            sheet_names = xls.sheet_names

            schema = {
                "sheets": sheet_names,
                "current_sheet": self._sheet_name,
                "columns": list(df.columns),
                "dtypes": {str(col): str(dtype) for col, dtype in df.dtypes.items()},
                "sample_values": {
                    str(col): df[col].dropna().head(3).tolist()
                    for col in df.columns
                },
            }
            return schema

        except Exception as e:
            return {"error": str(e)}

    async def get_record_count(self) -> int | None:
        """Get total number of records in Excel file."""
        if not self._config.file_path:
            return None

        path = Path(self._config.file_path)

        try:
            df = pd.read_excel(path, sheet_name=self._sheet_name)
            return len(df)
        except Exception:
            return None


class LeadExcelTransformer:
    """
    Transformer for lead Excel files.
    Handles the specific format of lead data files.
    """

    # Column mappings for lead files
    COLUMN_MAPPINGS = {
        # Standard format
        "Number": "phone_number",
        "Fullname": "name",
        "Email": "email",
        "AddDate": "add_date",
        "Birthdate": "birthdate",
        # Alternative names
        "Phone": "phone_number",
        "Mobile": "phone_number",
        "Name": "name",
        "شماره": "phone_number",
        "نام": "name",
        "تلفن": "phone_number",
        "موبایل": "phone_number",
    }

    def transform_lead_record(
        self,
        data: dict[str, Any],
        source_name: str | None = None,
        category_name: str | None = None,
    ) -> dict[str, Any]:
        """
        Transform a raw lead record into standardized format.
        """
        transformed = {
            "source_name": source_name,
            "category_name": category_name,
        }

        # Map columns
        for raw_col, standard_col in self.COLUMN_MAPPINGS.items():
            if raw_col in data and data[raw_col] is not None:
                transformed[standard_col] = data[raw_col]

        # Also check for columns with similar patterns
        for col, value in data.items():
            col_lower = str(col).lower()
            if value is None:
                continue

            if "phone" in col_lower or "number" in col_lower or "mobile" in col_lower:
                if "phone_number" not in transformed:
                    transformed["phone_number"] = value
            elif "name" in col_lower or "نام" in str(col):
                if "name" not in transformed:
                    transformed["name"] = value
            elif "email" in col_lower:
                if "email" not in transformed:
                    transformed["email"] = value

        # Clean and normalize phone number
        phone = transformed.get("phone_number")
        if phone is not None:
            phone_str = str(phone)
            # Remove any non-digit characters
            phone_clean = "".join(filter(str.isdigit, phone_str))

            # Handle various formats
            if phone_clean.startswith("98") and len(phone_clean) == 12:
                phone_clean = phone_clean[2:]
            elif phone_clean.startswith("0") and len(phone_clean) == 11:
                phone_clean = phone_clean[1:]
            elif len(phone_clean) == 10:
                pass  # Already in correct format
            elif len(phone_clean) == 9:
                # Might be missing leading 9
                phone_clean = "9" + phone_clean

            transformed["phone_number"] = phone_clean

        # Clean name
        name = transformed.get("name")
        if name is not None:
            name_str = str(name).strip()
            if name_str.lower() in ["nan", "none", ""]:
                transformed["name"] = None
            else:
                transformed["name"] = name_str

        return transformed

    def extract_category_from_filename(self, filename: str) -> str | None:
        """
        Extract category name from filename.
        Many lead files are named by category.
        """
        # Remove file extension
        name = Path(filename).stem

        # Clean up common patterns
        name = name.strip()

        # Remove common prefixes/suffixes
        prefixes_to_remove = ["لید ", "لیدهای ", "سرنخ ", "report_", "leads_"]
        for prefix in prefixes_to_remove:
            if name.startswith(prefix):
                name = name[len(prefix):]

        suffixes_to_remove = [".xlsx", ".xls", ".csv"]
        for suffix in suffixes_to_remove:
            if name.endswith(suffix):
                name = name[:-len(suffix)]

        return name if name else None

