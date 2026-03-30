"""
Phase 12: Link call logs to contacts, update funnel stages, create snapshot, run RFM.

Usage:
    cd /Users/univers/projects/funnelier
    python scripts/phase12_link_and_rfm.py
"""

import asyncio
import sys
from pathlib import Path
from uuid import UUID
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent.parent))

TENANT_ID = UUID("00000000-0000-0000-0000-000000000001")


def _utcnow():
    return datetime.now(timezone.utc)


async def link_call_logs_to_contacts():
    """Link call_logs to contacts by phone_number + tenant_id, and set contact_id."""
    from sqlalchemy import text
    from src.infrastructure.database.session import get_session_factory

    factory = get_session_factory()
    print("🔗 Step 1: Linking call logs to contacts by phone number...")

    async with factory() as session:
        # Set contact_id on call_logs where phone matches
        result = await session.execute(text("""
            UPDATE call_logs cl
            SET contact_id = c.id
            FROM contacts c
            WHERE cl.phone_number = c.phone_number
              AND cl.tenant_id = c.tenant_id
              AND cl.tenant_id = :tid
              AND cl.contact_id IS NULL
        """), {"tid": str(TENANT_ID)})
        linked = result.rowcount
        print(f"   → {linked:,} call log records linked to contacts")

        # How many unique contacts were linked?
        result = await session.execute(text("""
            SELECT count(DISTINCT contact_id) FROM call_logs
            WHERE tenant_id = :tid AND contact_id IS NOT NULL
        """), {"tid": str(TENANT_ID)})
        unique = result.scalar()
        print(f"   → {unique:,} unique contacts have call logs")

        await session.commit()
    print("   ✅ Done\n")


async def update_contact_stages():
    """Update contact stages based on call data."""
    from sqlalchemy import text
    from src.infrastructure.database.session import get_session_factory

    factory = get_session_factory()
    print("📊 Step 2: Updating contact funnel stages based on call data...")

    async with factory() as session:
        # Contacts with any calls → call_attempted (if still in early stages)
        result = await session.execute(text("""
            UPDATE contacts SET
                current_stage = 'call_attempted',
                stage_entered_at = now()
            WHERE tenant_id = :tid
            AND current_stage IN ('lead_acquired', 'sms_sent', 'sms_delivered')
            AND phone_number IN (
                SELECT DISTINCT phone_number FROM call_logs WHERE tenant_id = :tid
            )
        """), {"tid": str(TENANT_ID)})
        print(f"   → {result.rowcount:,} contacts → call_attempted")

        # Contacts with answered/successful calls → call_answered
        result = await session.execute(text("""
            UPDATE contacts SET
                current_stage = 'call_answered',
                stage_entered_at = now()
            WHERE tenant_id = :tid
            AND current_stage IN ('lead_acquired', 'sms_sent', 'sms_delivered', 'call_attempted')
            AND phone_number IN (
                SELECT DISTINCT phone_number FROM call_logs
                WHERE tenant_id = :tid AND is_successful = true
            )
        """), {"tid": str(TENANT_ID)})
        print(f"   → {result.rowcount:,} contacts → call_answered")

        # Aggregate call stats onto contacts
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
        print(f"   → {result.rowcount:,} contacts updated with call stats")

        await session.commit()
    print("   ✅ Done\n")


async def create_funnel_snapshot():
    """Create a daily funnel snapshot from current data."""
    from src.modules.analytics.infrastructure.repositories import FunnelSnapshotRepository
    from src.modules.leads.infrastructure.repositories import ContactRepository
    from src.infrastructure.database.session import get_session_factory

    factory = get_session_factory()
    print("📸 Step 3: Creating funnel snapshot...")

    async with factory() as session:
        contact_repo = ContactRepository(session, TENANT_ID)
        stage_counts = await contact_repo.get_stage_counts()

        total = sum(stage_counts.values())
        stages = [
            "lead_acquired", "sms_sent", "sms_delivered",
            "call_attempted", "call_answered",
            "invoice_issued", "payment_received",
        ]

        print("   Funnel:")
        for stage in stages:
            count = stage_counts.get(stage, 0)
            pct = count / total * 100 if total > 0 else 0
            bar = "█" * int(pct / 2)
            print(f"     {stage:20s}: {count:>8,} ({pct:5.1f}%) {bar}")
        print(f"     {'TOTAL':20s}: {total:>8,}")

        # Calculate conversion rates between stages
        conversion_rates = {}
        for i in range(len(stages) - 1):
            from_count = stage_counts.get(stages[i], 0)
            to_count = stage_counts.get(stages[i + 1], 0)
            rate = to_count / from_count if from_count > 0 else 0.0
            conversion_rates[f"{stages[i]}_to_{stages[i+1]}"] = round(rate, 4)

        overall_rate = (
            stage_counts.get("payment_received", 0) / stage_counts.get("lead_acquired", 1)
        )

        snapshot_repo = FunnelSnapshotRepository(session, TENANT_ID)

        class S:
            pass

        data = S()
        data.snapshot_date = _utcnow().date()
        data.stage_counts = stage_counts
        data.new_leads = stage_counts.get("lead_acquired", 0)
        data.new_conversions = stage_counts.get("payment_received", 0)
        data.daily_revenue = 0
        data.conversion_rates = conversion_rates
        data.conversion_rate = round(overall_rate, 6)
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
    print("   ✅ Snapshot saved\n")


async def run_rfm_calculation():
    """
    Run RFM calculation for all contacts.
    For contacts without purchases (most), they'll get low scores.
    We still segment them based on call engagement as a proxy.
    """
    from sqlalchemy import text
    from src.infrastructure.database.session import get_session_factory
    from src.modules.segmentation.domain.services import RFMCalculationService
    from src.modules.segmentation.domain.entities import RFMConfig
    from src.core.domain import RFMSegment

    factory = get_session_factory()
    print("🧮 Step 4: Running RFM calculation for all contacts...")

    rfm_config = RFMConfig(
        tenant_id=TENANT_ID,
        recency_thresholds=[14, 30, 60, 90],     # days
        frequency_thresholds=[1, 3, 5, 10],       # purchases
        monetary_thresholds=[50_000_000, 200_000_000, 500_000_000, 1_000_000_000],  # rials (1B high)
    )
    rfm_service = RFMCalculationService(config=rfm_config)

    async with factory() as session:
        # Fetch all contacts with their purchase data
        result = await session.execute(text("""
            SELECT id, phone_number,
                   last_purchase_at,
                   total_paid_invoices as purchase_count,
                   total_revenue as total_spend,
                   total_calls,
                   total_answered_calls,
                   total_call_duration
            FROM contacts
            WHERE tenant_id = :tid AND is_active = true
        """), {"tid": str(TENANT_ID)})
        rows = result.fetchall()
        print(f"   → Processing {len(rows):,} active contacts...")

        now = _utcnow()
        segment_counts = {}
        batch_size = 500
        updated = 0

        for i in range(0, len(rows), batch_size):
            batch = rows[i:i + batch_size]
            for row in batch:
                contact_id = row[0]
                phone = row[1]
                last_purchase = row[2]
                purchase_count = row[3] or 0
                total_spend = row[4] or 0

                profile = rfm_service.calculate_profile(
                    tenant_id=TENANT_ID,
                    contact_id=contact_id,
                    phone_number=phone,
                    last_purchase_date=last_purchase,
                    purchase_count=purchase_count,
                    total_spend=total_spend,
                    current_date=now,
                )

                segment_name = profile.segment.value if profile.segment else "unknown"
                rfm_score_str = f"{profile.rfm_score.recency}{profile.rfm_score.frequency}{profile.rfm_score.monetary}"

                segment_counts[segment_name] = segment_counts.get(segment_name, 0) + 1

                await session.execute(text("""
                    UPDATE contacts SET
                        rfm_segment = :segment,
                        rfm_score = :score,
                        recency_score = :r,
                        frequency_score = :f,
                        monetary_score = :m,
                        last_rfm_update = :updated_at
                    WHERE id = :cid AND tenant_id = :tid
                """), {
                    "segment": segment_name,
                    "score": rfm_score_str,
                    "r": profile.rfm_score.recency,
                    "f": profile.rfm_score.frequency,
                    "m": profile.rfm_score.monetary,
                    "updated_at": now,
                    "cid": str(contact_id),
                    "tid": str(TENANT_ID),
                })
                updated += 1

            await session.flush()
            if (i + batch_size) % 5000 == 0 or (i + batch_size) >= len(rows):
                pct = min((i + batch_size) / len(rows) * 100, 100)
                print(f"   → Progress: {i + len(batch):,}/{len(rows):,} ({pct:.0f}%)")

        await session.commit()

    print(f"\n   RFM Segment Distribution:")
    for seg, cnt in sorted(segment_counts.items(), key=lambda x: -x[1]):
        pct = cnt / updated * 100 if updated > 0 else 0
        label = {
            "champions": "قهرمانان",
            "loyal": "وفادار",
            "potential_loyalist": "بالقوه وفادار",
            "new_customers": "مشتریان جدید",
            "promising": "امیدوارکننده",
            "needs_attention": "نیاز به توجه",
            "about_to_sleep": "در خطر خواب",
            "cant_lose": "نباید از دست بدهیم",
            "at_risk": "در خطر",
            "hibernating": "خواب رفته",
            "lost": "از دست رفته",
        }.get(seg, seg)
        bar = "█" * max(1, int(pct / 3))
        print(f"     {label:20s} ({seg:20s}): {cnt:>8,} ({pct:5.1f}%) {bar}")

    print(f"\n   ✅ RFM calculated for {updated:,} contacts\n")


async def show_summary():
    """Show final summary of data state."""
    from sqlalchemy import text
    from src.infrastructure.database.session import get_session_factory

    factory = get_session_factory()

    async with factory() as session:
        result = await session.execute(text("""
            SELECT
                (SELECT count(*) FROM contacts WHERE tenant_id = :tid) as contacts,
                (SELECT count(*) FROM call_logs WHERE tenant_id = :tid) as call_logs,
                (SELECT count(*) FROM call_logs WHERE tenant_id = :tid AND contact_id IS NOT NULL) as linked_calls,
                (SELECT count(*) FROM sms_logs WHERE tenant_id = :tid) as sms_logs,
                (SELECT count(*) FROM funnel_snapshots WHERE tenant_id = :tid) as snapshots,
                (SELECT count(*) FROM contacts WHERE tenant_id = :tid AND rfm_segment IS NOT NULL) as rfm_scored,
                (SELECT count(DISTINCT rfm_segment) FROM contacts WHERE tenant_id = :tid AND rfm_segment IS NOT NULL) as rfm_segments
        """), {"tid": str(TENANT_ID)})
        row = result.fetchone()
        print("📋 Data Summary:")
        print(f"   Contacts:        {row[0]:>8,}")
        print(f"   Call Logs:       {row[1]:>8,}")
        print(f"   Linked Calls:    {row[2]:>8,}")
        print(f"   SMS Logs:        {row[3]:>8,}")
        print(f"   Funnel Snapshots:{row[4]:>8,}")
        print(f"   RFM Scored:      {row[5]:>8,}")
        print(f"   RFM Segments:    {row[6]:>8,}")


async def main():
    from src.infrastructure.database import init_database

    print("=" * 60)
    print("🚀 Funnelier — Phase 12: Link, Stage, Snapshot, RFM")
    print("=" * 60 + "\n")

    await init_database()

    await link_call_logs_to_contacts()
    await update_contact_stages()
    await create_funnel_snapshot()
    await run_rfm_calculation()
    await show_summary()

    print("\n" + "=" * 60)
    print("✅ Phase 12 Complete!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())

