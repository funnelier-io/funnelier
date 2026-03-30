"""
Phase 13: Create salespeople, link call logs, team performance analytics.

Usage:
    cd /Users/univers/projects/funnelier
    python scripts/phase13_team_setup.py
"""

import asyncio
import sys
from pathlib import Path
from uuid import UUID, uuid4
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent.parent))

TENANT_ID = UUID("00000000-0000-0000-0000-000000000001")

# Known salespeople from call log CSV filenames
SALESPEOPLE = [
    {"name": "اسدالهی", "slug": "asadollahi", "region": "تهران", "phone": ""},
    {"name": "نخست", "slug": "nakhost", "region": "تهران", "phone": ""},
    {"name": "بردبار", "slug": "bordbar", "region": "شیراز", "phone": ""},
    {"name": "کاشی", "slug": "kashi", "region": "فارس", "phone": ""},
    {"name": "رضایی", "slug": "rezae", "region": "شیراز", "phone": ""},
]


async def create_salespeople():
    """Create salesperson records in the database."""
    from sqlalchemy import select, text
    from src.infrastructure.database.session import get_session_factory
    from src.infrastructure.database.models.tenants import SalespersonModel

    factory = get_session_factory()
    print("👥 Step 1: Creating salesperson records...")

    created_ids = {}
    async with factory() as session:
        for sp in SALESPEOPLE:
            # Check if exists by name match
            stmt = select(SalespersonModel).where(
                SalespersonModel.tenant_id == TENANT_ID,
                SalespersonModel.name == sp["name"],
            )
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()

            if existing:
                created_ids[sp["slug"]] = existing.id
                print(f"   ✓ {sp['name']} already exists ({existing.id})")
            else:
                new_id = uuid4()
                model = SalespersonModel(
                    id=new_id,
                    tenant_id=TENANT_ID,
                    name=sp["name"],
                    phone=sp["phone"] or None,
                    email=f"{sp['slug']}@funnelier.ir",
                    region=sp["region"],
                    is_active=True,
                )
                session.add(model)
                created_ids[sp["slug"]] = new_id
                print(f"   + Created {sp['name']} → {new_id}")

        await session.commit()

    print(f"   ✅ {len(created_ids)} salespeople ready\n")
    return created_ids


async def link_call_logs_to_salespeople(sp_ids: dict):
    """Link call_logs to salesperson records by salesperson_name."""
    from sqlalchemy import text
    from src.infrastructure.database.session import get_session_factory

    factory = get_session_factory()
    print("🔗 Step 2: Linking call logs to salesperson records...")

    async with factory() as session:
        total_linked = 0
        for slug, sp_id in sp_ids.items():
            result = await session.execute(text("""
                UPDATE call_logs
                SET salesperson_id = :sp_id
                WHERE tenant_id = :tid
                  AND salesperson_name = :sp_name
                  AND salesperson_id IS NULL
            """), {"sp_id": str(sp_id), "tid": str(TENANT_ID), "sp_name": slug})
            count = result.rowcount
            total_linked += count
            name = next((s["name"] for s in SALESPEOPLE if s["slug"] == slug), slug)
            print(f"   → {name} ({slug}): {count:,} calls linked")

        await session.commit()

    print(f"   ✅ Total: {total_linked:,} calls linked to salespeople\n")


async def assign_contacts_to_salespeople(sp_ids: dict):
    """Assign contacts to salespeople based on who called them most."""
    from sqlalchemy import text
    from src.infrastructure.database.session import get_session_factory

    factory = get_session_factory()
    print("📋 Step 3: Assigning contacts to salespeople (by most calls)...")

    async with factory() as session:
        # For each contact with calls, find the salesperson with most calls
        result = await session.execute(text("""
            WITH ranked AS (
                SELECT
                    cl.contact_id,
                    cl.salesperson_id,
                    COUNT(*) as call_count,
                    ROW_NUMBER() OVER (PARTITION BY cl.contact_id ORDER BY COUNT(*) DESC) as rn
                FROM call_logs cl
                WHERE cl.tenant_id = :tid
                  AND cl.contact_id IS NOT NULL
                  AND cl.salesperson_id IS NOT NULL
                GROUP BY cl.contact_id, cl.salesperson_id
            )
            UPDATE contacts c
            SET assigned_to = r.salesperson_id,
                assigned_at = now()
            FROM ranked r
            WHERE r.contact_id = c.id
              AND r.rn = 1
              AND c.tenant_id = :tid
              AND c.assigned_to IS NULL
        """), {"tid": str(TENANT_ID)})
        print(f"   → {result.rowcount:,} contacts assigned to salespeople")
        await session.commit()

    print("   ✅ Done\n")


async def show_team_summary(sp_ids: dict):
    """Show team performance summary."""
    from sqlalchemy import text
    from src.infrastructure.database.session import get_session_factory

    factory = get_session_factory()
    print("📊 Team Performance Summary:")

    async with factory() as session:
        result = await session.execute(text("""
            SELECT
                s.name,
                COUNT(cl.id) as total_calls,
                COUNT(cl.id) FILTER (WHERE cl.is_successful = true) as successful,
                COALESCE(SUM(cl.duration_seconds), 0) as total_duration,
                COUNT(DISTINCT cl.phone_number) as unique_contacts,
                COUNT(DISTINCT cl.contact_id) FILTER (WHERE cl.contact_id IS NOT NULL) as linked_contacts,
                (SELECT count(*) FROM contacts c WHERE c.assigned_to = s.id AND c.tenant_id = :tid) as assigned_leads
            FROM salespersons s
            LEFT JOIN call_logs cl ON cl.salesperson_id = s.id AND cl.tenant_id = :tid
            WHERE s.tenant_id = :tid
            GROUP BY s.id, s.name
            ORDER BY total_calls DESC
        """), {"tid": str(TENANT_ID)})

        print(f"   {'Name':15s} {'Calls':>7s} {'Success':>8s} {'Rate':>6s} {'Duration':>10s} {'Contacts':>9s} {'Assigned':>9s}")
        print(f"   {'-'*15} {'-'*7} {'-'*8} {'-'*6} {'-'*10} {'-'*9} {'-'*9}")
        for row in result.all():
            name, total, success, dur, uniq, linked, assigned = row
            rate = f"{success/total*100:.0f}%" if total > 0 else "—"
            hours = dur // 3600
            mins = (dur % 3600) // 60
            print(f"   {name:15s} {total:>7,} {success:>8,} {rate:>6s} {hours:>3}h {mins:>2}m    {linked:>9,} {assigned:>9,}")

    print()


async def main():
    from src.infrastructure.database import init_database

    print("=" * 60)
    print("🚀 Funnelier — Phase 13: Team Setup & Performance")
    print("=" * 60 + "\n")

    await init_database()

    sp_ids = await create_salespeople()
    await link_call_logs_to_salespeople(sp_ids)
    await assign_contacts_to_salespeople(sp_ids)
    await show_team_summary(sp_ids)

    print("=" * 60)
    print("✅ Phase 13 Complete!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())

