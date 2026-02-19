#!/usr/bin/env python3
"""
Script to import call logs from CSV files.
Scans the call logs folder and imports all CSV files.
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime
import re

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.infrastructure.connectors import CSVFileConnector, CallLogCSVTransformer
from src.core.interfaces import FileSourceConfig


def extract_salesperson_from_filename(filename: str) -> tuple[str | None, str | None]:
    """
    Extract salesperson name from filename.
    Format: report_All_XX_XXX-XX_XXX - salesperson_name.csv
    """
    # Try to match pattern with salesperson name after " - "
    match = re.search(r' - ([^.]+)\.csv$', filename, re.IGNORECASE)
    if match:
        name = match.group(1).strip()
        return name, None  # name, id (we don't have ID yet)
    return None, None


async def import_call_log_file(
    file_path: Path,
    transformer: CallLogCSVTransformer,
) -> dict:
    """Import a single call log file."""
    print(f"\nProcessing: {file_path.name}")

    # Extract salesperson from filename
    salesperson_name, salesperson_id = extract_salesperson_from_filename(file_path.name)
    print(f"  Salesperson: {salesperson_name or 'Unknown'}")

    # Create connector with UTF-8 encoding
    config = FileSourceConfig(
        name=file_path.stem,
        source_type="csv_file",
        file_path=str(file_path),
        encoding="utf-8",
    )
    connector = CSVFileConnector(config)

    # Test connection
    success, message = await connector.test_connection()
    if not success:
        print(f"  Error: {message}")
        return {"file": file_path.name, "success": 0, "errors": [message]}

    # Get schema
    schema = await connector.get_schema()
    print(f"  Columns: {schema.get('columns', [])}")

    # Extract records
    records = await connector.read_file(file_path)
    print(f"  Raw records: {len(records)}")

    # Transform records
    transformed = []
    errors = []

    for record in records:
        try:
            call = transformer.transform_call_log_record(
                record.data,
                salesperson_id=salesperson_id,
                salesperson_name=salesperson_name,
            )

            # Validate phone number
            phone = call.get("phone_number")
            if phone and len(phone) >= 10:
                transformed.append(call)
            else:
                errors.append(f"Invalid phone: {phone}")
        except Exception as e:
            errors.append(str(e))

    # Calculate stats
    call_types = {}
    total_duration = 0
    successful_calls = 0

    for call in transformed:
        call_type = call.get("call_type", "unknown")
        call_types[call_type] = call_types.get(call_type, 0) + 1

        duration = call.get("duration_seconds", 0)
        total_duration += duration

        if duration >= 90:  # Successful call threshold
            successful_calls += 1

    print(f"  Valid calls: {len(transformed)}")
    print(f"  Call types: {call_types}")
    print(f"  Successful calls (≥90s): {successful_calls}")
    print(f"  Total duration: {total_duration // 60} minutes")
    print(f"  Errors: {len(errors)}")

    return {
        "file": file_path.name,
        "salesperson": salesperson_name,
        "total": len(records),
        "success": len(transformed),
        "errors": len(errors),
        "call_types": call_types,
        "successful_calls": successful_calls,
        "total_duration_seconds": total_duration,
        "calls": transformed,
    }


async def main():
    """Main import function."""
    # Default path relative to project root
    project_root = Path(__file__).parent.parent
    call_logs_folder = project_root / "call logs"

    # Override from command line if provided
    if len(sys.argv) > 1:
        call_logs_folder = Path(sys.argv[1])

    print(f"Importing call logs from: {call_logs_folder}")
    print("=" * 60)

    # Scan for files
    if not call_logs_folder.exists():
        print(f"Folder not found: {call_logs_folder}")
        return

    csv_files = list(call_logs_folder.glob("*.csv"))
    print(f"Found {len(csv_files)} CSV files")

    if not csv_files:
        print("No files to import")
        return

    # Create transformer
    transformer = CallLogCSVTransformer()

    # Import each file
    results = []
    total_calls = 0
    total_successful = 0
    total_duration = 0

    for file_path in csv_files:
        result = await import_call_log_file(file_path, transformer)
        results.append(result)
        total_calls += result.get("success", 0)
        total_successful += result.get("successful_calls", 0)
        total_duration += result.get("total_duration_seconds", 0)

    # Summary
    print("\n" + "=" * 60)
    print("IMPORT SUMMARY")
    print("=" * 60)
    print(f"Files processed: {len(results)}")
    print(f"Total valid calls: {total_calls}")
    print(f"Successful calls (≥90s): {total_successful}")
    print(f"Total duration: {total_duration // 3600} hours {(total_duration % 3600) // 60} minutes")

    if total_calls > 0:
        print(f"Success rate: {total_successful / total_calls * 100:.1f}%")

    # By salesperson
    print("\nCalls by salesperson:")
    for result in sorted(results, key=lambda x: x.get("success", 0), reverse=True):
        name = result.get("salesperson", "Unknown")
        calls = result.get("success", 0)
        successful = result.get("successful_calls", 0)
        print(f"  {name}: {calls} calls, {successful} successful")


if __name__ == "__main__":
    asyncio.run(main())

