#!/usr/bin/env python3
"""
Script to import existing lead data from Excel files.
Scans the leads-numbers folder and imports all Excel files.
"""

import asyncio
import os
import sys
from pathlib import Path
from uuid import uuid4

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd

from src.infrastructure.connectors import ExcelFileConnector, LeadExcelTransformer
from src.core.interfaces import FileSourceConfig


async def scan_lead_files(folder_path: str) -> list[Path]:
    """Scan folder for Excel files."""
    folder = Path(folder_path)
    if not folder.exists():
        print(f"Folder not found: {folder}")
        return []

    excel_files = list(folder.glob("*.xlsx")) + list(folder.glob("*.xls"))
    print(f"Found {len(excel_files)} Excel files")
    return excel_files


async def import_lead_file(file_path: Path, transformer: LeadExcelTransformer) -> dict:
    """Import a single lead file."""
    print(f"\nProcessing: {file_path.name}")

    # Extract category from filename
    category = transformer.extract_category_from_filename(file_path.name)
    print(f"  Category: {category}")

    # Create connector
    config = FileSourceConfig(
        name=file_path.stem,
        source_type="excel_file",
        file_path=str(file_path),
    )
    connector = ExcelFileConnector(config)

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
            lead = transformer.transform_lead_record(
                record.data,
                source_name=file_path.stem,
                category_name=category,
            )

            # Validate phone number
            phone = lead.get("phone_number")
            if phone and len(phone) == 10 and phone.startswith("9"):
                transformed.append(lead)
            else:
                errors.append(f"Invalid phone: {phone}")
        except Exception as e:
            errors.append(str(e))

    print(f"  Valid leads: {len(transformed)}")
    print(f"  Errors: {len(errors)}")

    return {
        "file": file_path.name,
        "category": category,
        "total": len(records),
        "success": len(transformed),
        "errors": len(errors),
        "leads": transformed,
    }


async def main():
    """Main import function."""
    # Default path relative to project root
    project_root = Path(__file__).parent.parent
    leads_folder = project_root / "leads-numbers"

    # Override from command line if provided
    if len(sys.argv) > 1:
        leads_folder = Path(sys.argv[1])

    print(f"Importing leads from: {leads_folder}")
    print("=" * 60)

    # Scan for files
    files = await scan_lead_files(str(leads_folder))
    if not files:
        print("No files to import")
        return

    # Create transformer
    transformer = LeadExcelTransformer()

    # Import each file
    results = []
    total_leads = 0
    total_errors = 0

    for file_path in files:
        result = await import_lead_file(file_path, transformer)
        results.append(result)
        total_leads += result.get("success", 0)
        total_errors += result.get("errors", 0) if isinstance(result.get("errors"), int) else len(result.get("errors", []))

    # Summary
    print("\n" + "=" * 60)
    print("IMPORT SUMMARY")
    print("=" * 60)
    print(f"Files processed: {len(results)}")
    print(f"Total valid leads: {total_leads}")
    print(f"Total errors: {total_errors}")

    # Categories summary
    categories = {}
    for result in results:
        cat = result.get("category", "Unknown")
        if cat not in categories:
            categories[cat] = 0
        categories[cat] += result.get("success", 0)

    print("\nLeads by category:")
    for cat, count in sorted(categories.items(), key=lambda x: x[1], reverse=True):
        print(f"  {cat}: {count}")


if __name__ == "__main__":
    asyncio.run(main())

