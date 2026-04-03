"""Quick test to check product seeding."""
import asyncio
import sys
from pathlib import Path
from uuid import UUID

sys.path.insert(0, str(Path(__file__).parent.parent))

TENANT_ID = UUID("00000000-0000-0000-0000-000000000001")

async def check():
    from src.infrastructure.database.session import get_session_factory
    from src.infrastructure.database.models.sales import ProductModel
    from sqlalchemy import select, func

    factory = get_session_factory()
    async with factory() as session:
        count = (await session.execute(
            select(func.count(ProductModel.id)).where(ProductModel.tenant_id == TENANT_ID)
        )).scalar()
        print(f"Products in DB: {count}")

        # List categories
        cats = (await session.execute(
            select(ProductModel.category, func.count(ProductModel.id))
            .where(ProductModel.tenant_id == TENANT_ID)
            .group_by(ProductModel.category)
        )).fetchall()
        for cat, cnt in cats:
            print(f"  {cat}: {cnt}")

if __name__ == "__main__":
    asyncio.run(check())

