"""
Fix and reimport call logs with correct timestamps + link to salespeople.

Usage:
    python scripts/fix_reimport_calls.py
"""

import asyncio
import sys
from pathlib import Path
from uuid import UUID, uuid4
from datetime import datetime, timezone
import re
import json

sys.path.insert(0, str(Path(__file__).parent.parent))

TENANT_ID = UUID("00000000-0000-0000-0000-000000000001")
CALL_LOGS_DIR = Path(__file__).parent.parent / "call logs"

# Map CSV filename salesperson names → Persian names in salespersons table
SALESPERSON_MAP = {
    "asadollahi": "اسدالهی",
    "nakhost": "نخست",
    "bordbar": "بردبار",
    "kashi": "کاشی",
    "rezae": "رضایی",
}


def parse_duration(raw: str) -> int:
    if not raw:
        return 0
    text = str(raw).strip().lower()
    m = re.match(r"(\d+)\s*sec", text)
    if m:
        return int(m.group(1))
    m = re.match(r"(\d+)\s*min(?:\s+(\d+)\s*sec)?", text)
    if m:
        return int(m.group(1)) * 60 + int(m.group(2) or 0)
    try:
        return int(float(text.replace(",", "")))
    except (ValueError, TypeError):
        return 0


def normalize_phone(raw: str) -> str | None:
    if not raw:
        return None
    text = str(raw).strip().replace("+", "").replace(" ", "").replace("-", "")
    phone = "".join(c for c in text if c.isdigit())
    if phone.startswith("98") and len(phone) == 12:
        phone = phone[2:]
    elif phone.startswith("0") and len(phone) == 11:
        phone = phone[1:]
    if len(phone) == 10 and phone.startswith("9"):
        return phone
    return None


def parse_datetime_safe(date_str: str, time_str: str) -> datetime | None:
    """Parse date and time strings from CSV. Returns None if unparseable."""
    combined = f"{date_str.strip()} {time_str.strip()}"
    for fmt in ["%d %b %Y %I:%M %p", "%d %b %Y %I:%M:%S %p"]:
        try:
            return datetime.strptime(combined, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def extract_salesperson(filename: str) -> str:
    name = Path(filename).stem
    if " - " in name:
        return name.split(" - ")[-1].strip()
    return name.strip()


async def main():
    import pandas as pd
    from sqlalchemy import text
    from src.infrastructure.database.session import get_session_factory
    from src.infrastructure.database.models.communications import CallLogModel

    session_factory = get_session_factory()

    print("=" * 60)
    print("🔧 Fix & Reimport Call Logs with Correct Timestamps")
    print("=" * 60)

    # Step 1: Load salesperson ID mapping
    print("\n📋 Loading salesperson IDs...")
    sp_id_map: dict[str, UUID] = {}
    async with session_factory() as session:
        result = await session.execute(text(
            "SELECT id, name FROM salespersons WHERE tenant_id = :tid"
        ), {"tid": str(TENANT_ID)})
        for row in result.all():
            sp_id_map[row.name] = row.id
            print(f"   {row.name} → {row.id}")

    # Step 2: Truncate existing call logs
    print("\n🗑️  Truncating old call_logs...")
    async with session_factory() as session:
        result = await session.execute(text(
            "DELETE FROM call_logs WHERE tenant_id = :tid"
        ), {"tid": str(TENANT_ID)})
        print(f"   Deleted {result.rowcount} rows")
        await session.commit()

    # Step 3: Reimport with correct dates using ORM models
    csv_files = sorted(CALL_LOGS_DIR.glob("*.csv"))
    print(f"\n📂 Found {len(csv_files)} call log files\n")

    grand_total = 0
    grand_errors = 0
    grand_skipped_date = 0

    for csv_file in csv_files:
        salesperson_en = extract_salesperson(csv_file.name)
        salesperson_fa = SALESPERSON_MAP.get(salesperson_en, salesperson_en)
        salesperson_id = sp_id_map.get(salesperson_fa)

        print(f"📄 {csv_file.name}")
        print(f"   Salesperson: {salesperson_en} → {salesperson_fa} (id={salesperson_id})")

        df = None
        for enc in ["utf-8-sig", "utf-8", "cp1256", "latin1"]:
            try:
                df = pd.read_csv(csv_file, encoding=enc)
                break
            except Exception:
                continue
        if df is None:
            print(f"   ❌ Cannot read file")
            continue

        # Map columns
        number_col = next((c for c in df.columns if "number" in str(c).lower()), None)
        type_col = next((c for c in df.columns if "type" in str(c).lower()), None)
        duration_col = next((c for c in df.columns if "duration" in str(c).lower()), None)
        date_col = next((c for c in df.columns if "date" in str(c).lower()), None)
        time_col = next((c for c in df.columns
                         if "time" in str(c).lower() and "date" not in str(c).lower()), None)
        name_col = next((c for c in df.columns if "name" in str(c).lower()), None)
        uid_col = next((c for c in df.columns if "unique" in str(c).lower()), None)

        if not number_col:
            print(f"   ❌ No phone column found")
            continue

        imported = 0
        errors = 0
        skipped_date = 0

        async with session_factory() as session:
            batch_models = []

            for _, row in df.iterrows():
                try:
                    phone = normalize_phone(str(row[number_col]))
                    if not phone:
                        errors += 1
                        continue

                    duration = parse_duration(str(row[duration_col])) if duration_col else 0

                    raw_type = str(row[type_col]).strip().lower() if type_col else ""
                    if raw_type in ("outgoing",):
                        call_type = "outbound"
                    elif raw_type in ("incomming", "incoming"):
                        call_type = "inbound"
                    elif raw_type in ("missed",):
                        call_type = "outbound"
                    else:
                        call_type = "outbound"

                    # Parse actual date from CSV
                    call_time = None
                    if date_col and time_col:
                        call_time = parse_datetime_safe(str(row[date_col]), str(row[time_col]))
                    if call_time is None:
                        skipped_date += 1
                        errors += 1
                        continue

                    contact_name = None
                    if name_col and pd.notna(row.get(name_col)):
                        contact_name = str(row[name_col]).strip()
                        if contact_name.lower() in ("nan", ""):
                            contact_name = None

                    is_successful = raw_type not in ("missed",) and duration >= 90

                    # Determine status
                    if raw_type == "missed":
                        status = "no_answer"
                    elif duration == 0:
                        status = "no_answer"
                    elif is_successful:
                        status = "answered"
                    else:
                        status = "attempted"

                    uid = str(row[uid_col]) if uid_col and pd.notna(row.get(uid_col)) else None

                    model = CallLogModel(
                        id=uuid4(),
                        tenant_id=TENANT_ID,
                        phone_number=phone,
                        call_type=call_type,
                        source_type="mobile",
                        salesperson_id=salesperson_id,
                        salesperson_name=salesperson_fa,
                        call_start=call_time,
                        duration_seconds=duration,
                        status=status,
                        is_successful=is_successful,
                        notes=contact_name,
                        voip_call_id=uid,
                        metadata_={"source_file": csv_file.name, "salesperson_en": salesperson_en},
                    )
                    session.add(model)
                    imported += 1

                    # Flush every 1000 rows to avoid memory issues
                    if imported % 1000 == 0:
                        await session.flush()

                except Exception as e:
                    errors += 1
                    if errors <= 3:
                        print(f"   ⚠️  Error row: {str(e)[:120]}")

            await session.commit()

        print(f"   ✅ Imported: {imported}, Errors: {errors}, Date-skip: {skipped_date}")
        grand_total += imported
        grand_errors += errors
        grand_skipped_date += skipped_date

    print(f"\n{'='*60}")
    print(f"📞 Total imported: {grand_total}, Errors: {grand_errors}, Date-skipped: {grand_skipped_date}")

    # Step 4: Update contact stages
    print("\n🔄 Updating contact funnel stages...")
    async with session_factory() as session:
        # Reset stages
        await session.execute(text("""
            UPDATE contacts SET current_stage = 'lead_acquired'
            WHERE tenant_id = :tid AND current_stage IN ('call_attempted', 'call_answered')
        """), {"tid": str(TENANT_ID)})

        result = await session.execute(text("""
            UPDATE contacts SET current_stage = 'call_attempted'
            WHERE tenant_id = :tid
            AND current_stage = 'lead_acquired'
            AND phone_number IN (
                SELECT DISTINCT phone_number FROM call_logs WHERE tenant_id = :tid
            )
        """), {"tid": str(TENANT_ID)})
        print(f"   → {result.rowcount} contacts → call_attempted")

        result = await session.execute(text("""
            UPDATE contacts SET current_stage = 'call_answered'
            WHERE tenant_id = :tid
            AND current_stage IN ('lead_acquired', 'call_attempted')
            AND phone_number IN (
                SELECT DISTINCT phone_number FROM call_logs
                WHERE tenant_id = :tid AND is_successful = true
            )
        """), {"tid": str(TENANT_ID)})
        print(f"   → {result.rowcount} contacts → call_answered")

        result = await session.execute(text("""
            UPDATE contacts c SET
                total_calls = sub.total_calls,
                total_answered_calls = sub.answered_calls,
                total_call_duration = sub.total_duration
            FROM (
                SELECT phone_number,
                       COUNT(*) as total_calls,
                       COUNT(*) FILTER (WHERE is_successful = true) as answered_calls,
                       COALESCE(SUM(duration_seconds), 0) as total_duration
                FROM call_logs WHERE tenant_id = :tid GROUP BY phone_number
            ) sub
            WHERE c.phone_number = sub.phone_number AND c.tenant_id = :tid
        """), {"tid": str(TENANT_ID)})
        print(f"   → {result.rowcount} contacts updated with call stats")

        await session.commit()

    # Step 5: Verify
    print("\n📅 Verifying date range in call_logs...")
    async with session_factory() as session:
        result = await session.execute(text("""
            SELECT salesperson_name, COUNT(*) as cnt,
                   MIN(call_start)::text as min_date,
                   MAX(call_start)::text as max_date
            FROM call_logs WHERE tenant_id = :tid
            GROUP BY salesperson_name ORDER BY cnt DESC
        """), {"tid": str(TENANT_ID)})
        for row in result.all():
            print(f"   {row.salesperson_name:10s}: {row.cnt:>6,} calls  ({row.min_date[:10]} to {row.max_date[:10]})")

    print(f"\n{'='*60}")
    print("✅ Complete! Call logs reimported with correct timestamps.")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())

