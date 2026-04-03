"""
Sync MongoDB CRM/ERP data into Funnelier.

Usage:
    python scripts/sync_mongodb_crm.py
    python scripts/sync_mongodb_crm.py --uri mongodb://mongo:mongo@localhost:27017 --db sivan_land_v2
"""

import asyncio
import sys
from pathlib import Path
from uuid import UUID

sys.path.insert(0, str(Path(__file__).parent.parent))

TENANT_ID = UUID("00000000-0000-0000-0000-000000000001")
DEFAULT_URI = "mongodb://mongo:mongo@localhost:27017"
DEFAULT_DB = "sivan_land_v2"


async def main():
    import argparse
    parser = argparse.ArgumentParser(description="Sync CRM MongoDB into Funnelier")
    parser.add_argument("--uri", default=DEFAULT_URI, help="MongoDB connection URI")
    parser.add_argument("--db", default=DEFAULT_DB, help="MongoDB database name")
    parser.add_argument("--overview", action="store_true", help="Show overview only (no sync)")
    args = parser.parse_args()

    from src.modules.sales.infrastructure.crm_connector import CRMSyncService
    from src.infrastructure.database.session import get_session_factory

    print("=" * 60)
    print("🔄 MongoDB CRM/ERP Sync")
    print(f"   URI: {args.uri}")
    print(f"   Database: {args.db}")
    print("=" * 60)

    if args.overview:
        svc = CRMSyncService(args.uri, args.db, None, TENANT_ID)
        overview = await svc.get_overview()
        await svc.disconnect()
        print("\n📋 CRM Data Overview:")
        for col_name, info in overview.items():
            print(f"   {col_name}: {info['count']} docs")
            print(f"      Fields: {', '.join(info['fields'][:8])}")
        return

    session_factory = get_session_factory()
    async with session_factory() as session:
        svc = CRMSyncService(args.uri, args.db, session, TENANT_ID)
        results = await svc.full_sync()
        await session.commit()

    print("\n📊 Sync Results:")
    for key, value in results.items():
        if isinstance(value, dict):
            print(f"\n   {key}:")
            for k, v in value.items():
                print(f"      {k}: {v}")
        else:
            print(f"   {key}: {value}")

    print(f"\n{'=' * 60}")
    print("✅ CRM sync complete!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())

