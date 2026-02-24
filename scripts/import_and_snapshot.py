"""
Phase 8: Import call logs, update contact stages, and create funnel snapshot.

Usage:
    python scripts/import_and_snapshot.py
"""

import asyncio
import sys
from pathlib import Path
from uuid import UUID, uuid4
from datetime import datetime, timezone
import re

sys.path.insert(0, str(Path(__file__).parent.parent))

TENANT_ID = UUID("00000000-0000-0000-0000-000000000001")
CALL_LOGS_DIR = Path(__file__).parent.parent / "call logs"


def _utcnow():
    return datetime.now(timezone.utc)


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


def parse_datetime(date_str: str, time_str: str) -> datetime:
    combined = f"{date_str.strip()} {time_str.strip()}"
    for fmt in ["%d %b %Y %I:%M %p", "%d %b %Y %I:%M:%S %p"]:
        try:
            return datetime.strptime(combined, fmt)
        except ValueError:
            continue
    return _utcnow()


def extract_salesperson(filename: str) -> str:
    name = Path(filename).stem
    if " - " in name:
        return name.split(" - ")[-1].strip()
    return name.strip()


async def import_call_logs():
    import pandas as pd
    from src.infrastructure.database.session import get_session_factory
    from src.modules.communications.infrastructure.repositories import CallLogRepository
    from src.modules.communications.domain.entities import CallLog
    from src.core.domain import CallType, CallSource

    if not CALL_LOGS_DIR.exists():
        print(f"❌ Call logs directory not found: {CALL_LOGS_DIR}")
        return

    csv_files = sorted(CALL_LOGS_DIR.glob("*.csv"))
    print(f"📂 Found {len(csv_files)} call log files\n")

    session_factory = get_session_factory()
    grand_total = 0
    grand_errors = 0

    for csv_file in csv_files:
        salesperson = extract_salesperson(csv_file.name)
        print(f"📄 {csv_file.name}")
        print(f"   Salesperson: {salesperson}")

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

        print(f"   Rows: {len(df)}, Columns: {list(df.columns)}")

        # Map columns
        number_col = next((c for c in df.columns if "number" in str(c).lower()), None)
        type_col = next((c for c in df.columns if "type" in str(c).lower()), None)
        duration_col = next((c for c in df.columns if "duration" in str(c).lower()), None)
        date_col = next((c for c in df.columns if "date" in str(c).lower()), None)
        time_col = next((c for c in df.columns
                         if "time" in str(c).lower() and "date" not in str(c).lower()), None)
        name_col = next((c for c in df.columns if "name" in str(c).lower()), None)

        if not number_col:
            print(f"   ❌ No phone column found")
            continue

        imported = 0
        errors = 0

        async with session_factory() as session:
            repo = CallLogRepository(session, TENANT_ID)

            for _, row in df.iterrows():
                try:
                    phone = normalize_phone(str(row[number_col]))
                    if not phone:
                        errors += 1
                        continue

                    duration = parse_duration(str(row[duration_col])) if duration_col else 0

                    raw_type = str(row[type_col]).strip().lower() if type_col else ""
                    if raw_type in ("outgoing",):
                        ct = CallType.OUTGOING
                    elif raw_type in ("incomming", "incoming"):
                        ct = CallType.INCOMING
                    elif raw_type in ("missed",):
                        ct = CallType.MISSED
                    else:
                        ct = CallType.OUTGOING

                    call_time = _utcnow()
                    if date_col and time_col:
                        try:
                            call_time = parse_datetime(str(row[date_col]), str(row[time_col]))
                        except Exception:
                            pass

                    contact_name = None
                    if name_col and pd.notna(row.get(name_col)):
                        contact_name = str(row[name_col]).strip()
                        if contact_name.lower() in ("nan", ""):
                            contact_name = None

                    is_successful = raw_type not in ("missed",) and duration >= 90

                    call_log = CallLog(
                        id=uuid4(),
                        tenant_id=TENANT_ID,
                        phone_number=phone,
                        call_type=ct,
                        source=CallSource.MOBILE,
                        duration_seconds=duration,
                        call_time=call_time,
                        salesperson_name=salesperson,
                        contact_name=contact_name,
                        is_successful=is_successful,
                        metadata={"source_file": csv_file.name},
                    )
                    await repo.add(call_log)
                    imported += 1
                except Exception as e:
                    errors += 1
                    if errors <= 3:
                        print(f"   ⚠️  Error: {str(e)[:120]}")

            await session.commit()

        print(f"   ✅ Imported: {imported}, Errors: {errors}")
        grand_total += imported
        grand_errors += errors

    print(f"\n{'='*60}")
    print(f"📞 Total call logs imported: {grand_total}, Errors: {grand_errors}")


async def update_contact_stages():
    from sqlalchemy import text
    from src.infrastructure.database.session import get_session_factory

    session_factory = get_session_factory()
    print("\n🔄 Updating contact funnel stages based on call data...")

    async with session_factory() as session:
        # Move contacts with any calls to 'call_attempted'
        result = await session.execute(text("""
            UPDATE contacts SET current_stage = 'call_attempted'
            WHERE tenant_id = :tid
            AND current_stage = 'lead_acquired'
            AND phone_number IN (
                SELECT DISTINCT phone_number FROM call_logs WHERE tenant_id = :tid
            )
        """), {"tid": str(TENANT_ID)})
        print(f"   → {result.rowcount} contacts → call_attempted")

        # Move contacts with successful calls (≥90s) to 'call_answered'
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

        # Update call stats on contacts
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
    print("   ✅ Done")


async def create_funnel_snapshot():
    from src.modules.analytics.infrastructure.repositories import FunnelSnapshotRepository
    from src.modules.leads.infrastructure.repositories import ContactRepository
    from src.infrastructure.database.session import get_session_factory

    session_factory = get_session_factory()
    print("\n📊 Creating funnel snapshot...")

    async with session_factory() as session:
        contact_repo = ContactRepository(session, TENANT_ID)
        stage_counts = await contact_repo.get_stage_counts()

        total = sum(stage_counts.values())
        print("   Funnel:")
        for stage in ["lead_acquired", "sms_sent", "sms_delivered",
                       "call_attempted", "call_answered", "invoice_issued", "payment_received"]:
            count = stage_counts.get(stage, 0)
            pct = count / total * 100 if total > 0 else 0
            bar = "█" * int(pct / 2)
            print(f"     {stage:20s}: {count:>6,} ({pct:5.1f}%) {bar}")
        print(f"     {'TOTAL':20s}: {total:>6,}")

        snapshot_repo = FunnelSnapshotRepository(session, TENANT_ID)

        class S:
            pass

        data = S()
        data.snapshot_date = _utcnow().date()
        data.stage_counts = stage_counts
        data.new_leads = stage_counts.get("lead_acquired", 0)
        data.new_conversions = stage_counts.get("payment_received", 0)
        data.daily_revenue = 0
        data.conversion_rates = {}
        data.conversion_rate = 0.0
        data.stage_transitions = []
        data.new_sms_sent = stage_counts.get("sms_sent", 0)
        data.new_sms_delivered = stage_counts.get("sms_delivered", 0)
        data.new_calls = stage_counts.get("call_attempted", 0)
        data.new_answered_calls = stage_counts.get("call_answered", 0)
        data.new_successful_calls = stage_counts.get("call_answered", 0)
        data.new_invoices = stage_counts.get("invoice_issued", 0)
        data.new_payments = stage_counts.get("payment_received", 0)

        await snapshot_repo.save(data)
        await session.commit()
    print("   ✅ Snapshot saved")


async def main():
    print("=" * 60)
    print("🚀 Funnelier — Import Call Logs & Update Funnel")
    print("=" * 60)
    await import_call_logs()
    await update_contact_stages()
    await create_funnel_snapshot()
    print("\n" + "=" * 60)
    print("✅ Complete!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())

