"""
Data Import Script

Imports leads from Excel files and call logs from CSV files
into the Funnelier database. Handles the actual file formats:

Lead files: AddDate, Birthdate, Fullname, Email, Number
Call logs: Sr. No, Name:, Number, Type, SIM, Date, Time, Duration, Tags:, Notes:, UniqueID
"""

import asyncio
import sys
import re
from datetime import datetime
from pathlib import Path
from uuid import UUID, uuid4

import pandas as pd

# Project root
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

DEFAULT_TENANT_ID = UUID("00000000-0000-0000-0000-000000000001")


def normalize_phone(raw) -> str | None:
    """Normalize Iranian phone number to 10-digit format (9XXXXXXXXX)."""
    if pd.isna(raw):
        return None
    phone = "".join(c for c in str(raw).split(".")[0] if c.isdigit())
    if phone.startswith("98") and len(phone) == 12:
        phone = phone[2:]
    elif phone.startswith("0") and len(phone) == 11:
        phone = phone[1:]
    if len(phone) == 10 and phone.startswith("9"):
        return phone
    return None


def parse_duration(raw) -> int:
    """Parse duration from text like '366 sec' to integer seconds."""
    if pd.isna(raw):
        return 0
    text = str(raw).strip().lower()
    # "366 sec" or "2 min 30 sec" or just "120"
    match = re.match(r"(\d+)\s*sec", text)
    if match:
        return int(match.group(1))
    match = re.match(r"(\d+)\s*min(?:\s+(\d+)\s*sec)?", text)
    if match:
        minutes = int(match.group(1))
        seconds = int(match.group(2) or 0)
        return minutes * 60 + seconds
    try:
        return int(float(text))
    except (ValueError, TypeError):
        return 0


def extract_category(filename: str) -> str:
    """Extract lead category from filename."""
    name = Path(filename).stem
    # Remove common wrapping characters
    name = name.strip("«»")
    return name.strip()


def extract_salesperson(filename: str) -> str:
    """Extract salesperson name from call log filename."""
    name = Path(filename).stem
    if " - " in name:
        return name.split(" - ")[-1].strip()
    return name.strip()


async def import_leads(folder: Path, tenant_id: UUID = DEFAULT_TENANT_ID):
    """Import all lead Excel files from a folder."""
    from src.infrastructure.database.session import get_session_factory, init_database
    from src.infrastructure.database.models.leads import ContactModel
    from sqlalchemy import select

    await init_database()
    session_factory = get_session_factory()

    xlsx_files = sorted(f for f in folder.glob("*.xlsx") if not f.name.startswith("."))
    print(f"\n📋 Found {len(xlsx_files)} lead files in {folder}")

    # Pre-load existing phone numbers to avoid per-row DB lookups
    existing_phones: set[str] = set()
    async with session_factory() as session:
        stmt = select(ContactModel.phone_number).where(
            ContactModel.tenant_id == tenant_id)
        result = await session.execute(stmt)
        for row in result.fetchall():
            existing_phones.add(row[0])
    print(f"   Existing contacts in DB: {len(existing_phones):,}")

    grand_total = 0
    grand_imported = 0
    grand_dupes = 0
    grand_errors = 0

    for xlsx in xlsx_files:
        try:
            df = pd.read_excel(xlsx)
        except Exception as e:
            print(f"  ❌ {xlsx.name}: Cannot read ({e})")
            grand_errors += 1
            continue

        if "Number" not in df.columns:
            print(f"  ⚠️  {xlsx.name}: No 'Number' column, skipping")
            grand_errors += 1
            continue

        category = extract_category(xlsx.name)
        imported = 0
        dupes = 0
        errors = 0
        batch = []

        for _, row in df.iterrows():
            phone = normalize_phone(row.get("Number"))
            if not phone:
                errors += 1
                continue

            if phone in existing_phones:
                dupes += 1
                continue

            existing_phones.add(phone)

            name = ""
            if pd.notna(row.get("Fullname")):
                name = str(row["Fullname"]).strip()

            batch.append(ContactModel(
                id=uuid4(),
                tenant_id=tenant_id,
                phone_number=phone,
                name=name,
                source_name=f"excel:{xlsx.name}",
                category_name=category,
                tags=[category] if category else [],
                current_stage="lead_acquired",
            ))
            imported += 1

        # Batch insert
        if batch:
            async with session_factory() as session:
                session.add_all(batch)
                await session.commit()

        status = "✅" if errors == 0 else "⚠️ "
        print(f"  {status} {xlsx.name}: {len(df)} total, "
              f"{imported} imported, {dupes} dupes, {errors} errors")

        grand_total += len(df)
        grand_imported += imported
        grand_dupes += dupes
        grand_errors += errors

    print(f"\n📊 Lead Import Summary:")
    print(f"   Files: {len(xlsx_files)}")
    print(f"   Total records: {grand_total:,}")
    print(f"   Imported: {grand_imported:,}")
    print(f"   Duplicates: {grand_dupes:,}")
    print(f"   Errors: {grand_errors:,}")

    return {
        "files": len(xlsx_files),
        "total": grand_total,
        "imported": grand_imported,
        "duplicates": grand_dupes,
        "errors": grand_errors,
    }


async def import_call_logs(folder: Path, tenant_id: UUID = DEFAULT_TENANT_ID):
    """Import all call log CSV files from a folder."""
    from src.infrastructure.database.session import get_session_factory, init_database
    from src.infrastructure.database.models.communications import CallLogModel

    await init_database()
    session_factory = get_session_factory()

    csv_files = sorted(f for f in folder.glob("*.csv") if not f.name.startswith("."))
    print(f"\n📞 Found {len(csv_files)} call log files in {folder}")

    grand_total = 0
    grand_imported = 0
    grand_errors = 0

    for csv_file in csv_files:
        # Try multiple encodings
        df = None
        for enc in ["utf-8-sig", "utf-8", "cp1256", "latin1"]:
            try:
                df = pd.read_csv(csv_file, encoding=enc)
                break
            except Exception:
                continue

        if df is None:
            print(f"  ❌ {csv_file.name}: Cannot decode")
            grand_errors += 1
            continue

        salesperson = extract_salesperson(csv_file.name)
        imported = 0
        errors = 0

        async with session_factory() as session:
            for _, row in df.iterrows():
                phone = normalize_phone(row.get("Number"))
                if not phone:
                    errors += 1
                    continue

                duration = parse_duration(row.get("Duration"))
                call_type = str(row.get("Type", "")).strip().lower()

                # Map call type to direction
                if call_type in ("outgoing",):
                    direction = "outbound"
                elif call_type in ("incomming", "incoming", "missed", "rejected"):
                    direction = "inbound"
                else:
                    direction = "outbound"

                answered = call_type not in ("missed", "rejected") and duration > 0

                call = CallLogModel(
                    id=uuid4(),
                    tenant_id=tenant_id,
                    phone_number=phone,
                    salesperson_name=salesperson,
                    duration_seconds=duration,
                    call_type=direction,
                    is_successful=answered and duration >= 90,
                    call_start=datetime.utcnow(),
                    status="answered" if (answered and duration > 0) else ("no_answer" if call_type == "missed" else "attempted"),
                )
                session.add(call)
                imported += 1

            await session.commit()

        print(f"  ✅ {csv_file.name} ({salesperson}): "
              f"{len(df)} total, {imported} imported, {errors} errors")

        grand_total += len(df)
        grand_imported += imported
        grand_errors += errors

    print(f"\n📊 Call Log Import Summary:")
    print(f"   Files: {len(csv_files)}")
    print(f"   Total records: {grand_total:,}")
    print(f"   Imported: {grand_imported:,}")
    print(f"   Errors: {grand_errors:,}")

    return {
        "files": len(csv_files),
        "total": grand_total,
        "imported": grand_imported,
        "errors": grand_errors,
    }


async def show_stats(tenant_id: UUID = DEFAULT_TENANT_ID):
    """Show database statistics after import."""
    from src.infrastructure.database.session import get_session_factory
    from src.infrastructure.database.models.leads import ContactModel
    from src.infrastructure.database.models.communications import CallLogModel
    from sqlalchemy import select, func

    session_factory = get_session_factory()

    async with session_factory() as session:
        contacts = (await session.execute(
            select(func.count(ContactModel.id)).where(
                ContactModel.tenant_id == tenant_id)
        )).scalar() or 0

        calls = (await session.execute(
            select(func.count(CallLogModel.id)).where(
                CallLogModel.tenant_id == tenant_id)
        )).scalar() or 0

        answered_calls = (await session.execute(
            select(func.count(CallLogModel.id)).where(
                CallLogModel.tenant_id == tenant_id,
                CallLogModel.is_successful == True,
            )
        )).scalar() or 0

        categories = (await session.execute(
            select(ContactModel.category_name, func.count(ContactModel.id))
            .where(ContactModel.tenant_id == tenant_id)
            .group_by(ContactModel.category_name)
            .order_by(func.count(ContactModel.id).desc())
            .limit(10)
        )).fetchall()

        salespeople = (await session.execute(
            select(CallLogModel.salesperson_name, func.count(CallLogModel.id))
            .where(CallLogModel.tenant_id == tenant_id)
            .group_by(CallLogModel.salesperson_name)
        )).fetchall()

    print(f"\n{'='*60}")
    print(f"📊 Database Statistics")
    print(f"{'='*60}")
    print(f"  Contacts: {contacts:,}")
    print(f"  Call logs: {calls:,}")
    print(f"  Answered calls (≥90s): {answered_calls:,}")
    print(f"  Answer rate: {answered_calls/calls*100:.1f}%" if calls else "  Answer rate: N/A")
    print(f"\n  Top categories:")
    for cat, count in categories:
        print(f"    {cat}: {count:,}")
    print(f"\n  Salespeople:")
    for sp, count in salespeople:
        print(f"    {sp}: {count:,}")
    print(f"{'='*60}\n")


async def main():
    import argparse
    parser = argparse.ArgumentParser(description="Funnelier Data Import")
    parser.add_argument("--leads", action="store_true", help="Import lead files")
    parser.add_argument("--calls", action="store_true", help="Import call logs")
    parser.add_argument("--all", action="store_true", help="Import everything")
    parser.add_argument("--stats", action="store_true", help="Show DB stats")
    parser.add_argument("--leads-dir", default="leads-numbers", help="Leads folder path")
    parser.add_argument("--calls-dir", default="call logs", help="Call logs folder path")
    args = parser.parse_args()

    leads_dir = PROJECT_ROOT / args.leads_dir
    calls_dir = PROJECT_ROOT / args.calls_dir

    if args.all or args.leads:
        await import_leads(leads_dir)

    if args.all or args.calls:
        await import_call_logs(calls_dir)

    if args.stats or args.all or args.leads or args.calls:
        await show_stats()

    if not any([args.all, args.leads, args.calls, args.stats]):
        parser.print_help()


if __name__ == "__main__":
    asyncio.run(main())

