"""Check RFM segment status in the database."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


async def check():
    from src.infrastructure.database.session import get_session_factory
    from src.infrastructure.database.models.leads import ContactModel
    from sqlalchemy import select, func

    factory = get_session_factory()
    async with factory() as session:
        total = (await session.execute(
            select(func.count(ContactModel.id))
        )).scalar()
        with_rfm = (await session.execute(
            select(func.count(ContactModel.id)).where(
                ContactModel.rfm_segment.isnot(None)
            )
        )).scalar()
        segments = (await session.execute(
            select(ContactModel.rfm_segment, func.count(ContactModel.id))
            .where(ContactModel.rfm_segment.isnot(None))
            .group_by(ContactModel.rfm_segment)
        )).fetchall()

        print(f"Total contacts: {total}")
        print(f"With RFM segment: {with_rfm}")
        print(f"Missing RFM: {total - with_rfm}")
        print("Segment distribution:")
        for seg, cnt in sorted(segments, key=lambda x: -x[1]):
            print(f"  {seg}: {cnt}")


if __name__ == "__main__":
    asyncio.run(check())

