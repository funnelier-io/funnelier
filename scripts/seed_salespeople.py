"""
Phase 10: Seed salespeople into the database and link call logs.

Creates the 9 known salespeople in the salespersons table,
then back-fills call_logs.salesperson_id by matching salesperson_name.

Usage:
    python scripts/seed_salespeople.py
"""

import asyncio
import sys
from pathlib import Path
from uuid import UUID, uuid4
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent.parent))

TENANT_ID = UUID("00000000-0000-0000-0000-000000000001")

# The 9 known salespeople from call log filenames and lead assignments
SALESPEOPLE = [
    {"name": "اسدالهی", "name_key": "asadollahi", "phone": "9121234567", "region": "تهران"},
    {"name": "بردبار", "name_key": "bordbar", "phone": "9121234568", "region": "شیراز"},
    {"name": "رضایی", "name_key": "rezae", "phone": "9121234569", "region": "تهران"},
    {"name": "کاشی", "name_key": "kashi", "phone": "9121234570", "region": "اصفهان"},
    {"name": "نخست", "name_key": "nakhost", "phone": "9121234571", "region": "گیلان"},
    {"name": "فدایی", "name_key": "fadaei", "phone": "9121234572", "region": "شیراز"},
    {"name": "شفیعی", "name_key": "shafiei", "phone": "9121234573", "region": "کرمانشاه"},
    {"name": "حیدری", "name_key": "heydari", "phone": "9121234574", "region": "بوشهر"},
    {"name": "آتشین", "name_key": "atashin", "phone": "9121234575", "region": "شیراز"},
]


async def seed_salespeople():
    from sqlalchemy import select, text
    from src.infrastructure.database.session import get_session_factory
    from src.infrastructure.database.models.tenants import SalespersonModel

    session_factory = get_session_factory()

    async with session_factory() as session:
        # Check existing salespeople
        result = await session.execute(
            select(SalespersonModel).where(SalespersonModel.tenant_id == TENANT_ID)
        )
        existing = result.scalars().all()
        existing_names = {sp.name for sp in existing}

        print(f"📋 Existing salespeople: {len(existing)}")
        for sp in existing:
            print(f"   • {sp.name} (id={sp.id})")

        created = 0
        sp_ids = {}  # name_key -> UUID

        for sp_data in SALESPEOPLE:
            if sp_data["name"] in existing_names:
                # Get existing ID
                for sp in existing:
                    if sp.name == sp_data["name"]:
                        sp_ids[sp_data["name_key"]] = sp.id
                        break
                print(f"   ⏭️  {sp_data['name']} already exists")
                continue

            sp_id = uuid4()
            sp_ids[sp_data["name_key"]] = sp_id

            model = SalespersonModel(
                id=sp_id,
                tenant_id=TENANT_ID,
                name=sp_data["name"],
                phone=sp_data["phone"],
                region=sp_data["region"],
                categories=[],
                is_active=True,
                total_leads_assigned=0,
                total_conversions=0,
                total_revenue=0,
                metadata_={
                    "name_key": sp_data["name_key"],
                },
            )
            session.add(model)
            created += 1
            print(f"   ✅ Created: {sp_data['name']} ({sp_data['region']}) → {sp_id}")

        await session.commit()
        print(f"\n👥 Created {created} new salespeople")

        # Now back-fill call_logs.salesperson_id
        print("\n🔗 Linking call logs to salespeople...")
        total_linked = 0

        for sp_data in SALESPEOPLE:
            sp_id = sp_ids.get(sp_data["name_key"])
            if not sp_id:
                continue

            # Match by salesperson_name (the key extracted from CSV filename)
            result = await session.execute(text("""
                UPDATE call_logs
                SET salesperson_id = :sp_id
                WHERE tenant_id = :tid
                AND salesperson_name = :sp_name
                AND salesperson_id IS NULL
            """), {
                "sp_id": str(sp_id),
                "tid": str(TENANT_ID),
                "sp_name": sp_data["name_key"],
            })
            count = result.rowcount
            if count > 0:
                print(f"   → {sp_data['name']} ({sp_data['name_key']}): {count:,} call logs linked")
                total_linked += count

        # Update salesperson lead counts from contacts
        print("\n📊 Updating salesperson lead counts...")
        for sp_data in SALESPEOPLE:
            sp_id = sp_ids.get(sp_data["name_key"])
            if not sp_id:
                continue

            result = await session.execute(text("""
                UPDATE salespersons SET total_leads_assigned = (
                    SELECT COUNT(*) FROM contacts
                    WHERE tenant_id = :tid AND assigned_to = :sp_id
                )
                WHERE id = :sp_id AND tenant_id = :tid
            """), {"sp_id": str(sp_id), "tid": str(TENANT_ID)})

        await session.commit()
        print(f"\n✅ Total call logs linked: {total_linked:,}")


async def print_summary():
    from sqlalchemy import select, func, text
    from src.infrastructure.database.session import get_session_factory
    from src.infrastructure.database.models.tenants import SalespersonModel
    from src.infrastructure.database.models.communications import CallLogModel

    session_factory = get_session_factory()

    async with session_factory() as session:
        print("\n" + "=" * 60)
        print("📊 Salesperson Summary")
        print("=" * 60)

        result = await session.execute(
            select(SalespersonModel).where(SalespersonModel.tenant_id == TENANT_ID)
        )
        salespeople = result.scalars().all()

        for sp in salespeople:
            # Count linked call logs
            call_count = await session.execute(
                select(func.count())
                .select_from(CallLogModel)
                .where(CallLogModel.tenant_id == TENANT_ID)
                .where(CallLogModel.salesperson_id == sp.id)
            )
            calls = call_count.scalar_one()

            # Count answered calls
            answered_count = await session.execute(
                select(func.count())
                .select_from(CallLogModel)
                .where(CallLogModel.tenant_id == TENANT_ID)
                .where(CallLogModel.salesperson_id == sp.id)
                .where(CallLogModel.status == "answered")
            )
            answered = answered_count.scalar_one()

            print(f"  {sp.name:10s} | {sp.region or '':10s} | "
                  f"Calls: {calls:>6,} | Answered: {answered:>5,} | "
                  f"Leads: {sp.total_leads_assigned:>5,}")


async def main():
    print("=" * 60)
    print("🚀 Funnelier — Seed Salespeople & Link Call Logs")
    print("=" * 60)
    await seed_salespeople()
    await print_summary()
    print("\n✅ Done!")


if __name__ == "__main__":
    asyncio.run(main())

