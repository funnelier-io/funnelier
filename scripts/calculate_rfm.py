"""
Phase 10: Calculate RFM scores for all contacts and persist to database.

Since there are no purchase/payment records yet, all contacts will get
baseline RFM scores. Once invoice/payment data is imported, re-run this
script to recalculate with real purchase data.

Usage:
    python scripts/calculate_rfm.py
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


async def calculate_rfm():
    from sqlalchemy import select, func, update as sa_update
    from src.infrastructure.database.session import get_session_factory
    from src.infrastructure.database.models.leads import ContactModel
    from src.modules.segmentation.domain.entities import RFMConfig
    from src.modules.segmentation.domain.services import RFMCalculationService
    from src.core.domain import RFMSegment

    session_factory = get_session_factory()
    config = RFMConfig(tenant_id=TENANT_ID)
    rfm_service = RFMCalculationService(config)
    now = _utcnow()

    async with session_factory() as session:
        # Get total count
        count_result = await session.execute(
            select(func.count())
            .select_from(ContactModel)
            .where(ContactModel.tenant_id == TENANT_ID)
        )
        total = count_result.scalar_one()
        print(f"📊 Total contacts: {total:,}")

        # Process in batches
        batch_size = 500
        offset = 0
        scored = 0
        segment_counts = {}

        while offset < total:
            stmt = (
                select(ContactModel)
                .where(ContactModel.tenant_id == TENANT_ID)
                .order_by(ContactModel.id)
                .offset(offset)
                .limit(batch_size)
            )
            result = await session.execute(stmt)
            contacts = result.scalars().all()

            if not contacts:
                break

            for contact in contacts:
                # Calculate RFM based on available data
                days_since = None
                if contact.last_purchase_at:
                    days_since = (now - contact.last_purchase_at).days

                purchase_count = contact.total_paid_invoices or 0
                total_spend = float(contact.total_revenue or 0)

                # Calculate RFM score
                rfm_score = rfm_service.calculate_score(
                    days_since_last_purchase=days_since,
                    purchase_count=purchase_count,
                    total_spend=total_spend,
                )

                # Determine segment
                segment = RFMSegment.from_rfm_score(
                    rfm_score.recency,
                    rfm_score.frequency,
                    rfm_score.monetary,
                )

                # Enhance segmentation with engagement data (calls, SMS)
                # Contacts with call engagement but no purchases get a better segment
                if purchase_count == 0 and contact.total_answered_calls and contact.total_answered_calls > 0:
                    # Contacted and engaged — treat as "promising"
                    segment = RFMSegment.PROMISING
                elif purchase_count == 0 and contact.total_calls and contact.total_calls > 0:
                    # Called but not answered long enough — "need_attention"
                    segment = RFMSegment.NEED_ATTENTION
                elif purchase_count == 0 and contact.total_sms_sent and contact.total_sms_sent > 0:
                    # SMS sent but no call — "new_customers" (early funnel)
                    segment = RFMSegment.NEW_CUSTOMERS

                rfm_string = f"{rfm_score.recency}{rfm_score.frequency}{rfm_score.monetary}"

                # Update contact
                contact.rfm_segment = segment.value
                contact.rfm_score = rfm_string
                contact.recency_score = rfm_score.recency
                contact.frequency_score = rfm_score.frequency
                contact.monetary_score = rfm_score.monetary
                contact.last_rfm_update = now

                seg_name = segment.value
                segment_counts[seg_name] = segment_counts.get(seg_name, 0) + 1
                scored += 1

            await session.flush()
            offset += batch_size
            print(f"   Processed {min(offset, total):,}/{total:,}")

        await session.commit()

        # Print summary
        print(f"\n✅ Scored {scored:,} contacts")
        print("\n📊 RFM Segment Distribution:")
        print(f"   {'Segment':<25s} {'Count':>8s} {'%':>7s}")
        print("   " + "-" * 42)

        for seg_name, count in sorted(segment_counts.items(), key=lambda x: x[1], reverse=True):
            pct = count / scored * 100 if scored > 0 else 0
            bar = "█" * int(pct / 2)
            print(f"   {seg_name:<25s} {count:>8,} {pct:>6.1f}% {bar}")

        print(f"   {'TOTAL':<25s} {scored:>8,}")


async def main():
    print("=" * 60)
    print("🚀 Funnelier — Calculate RFM Scores")
    print("=" * 60)
    await calculate_rfm()
    print("\n✅ Done!")


if __name__ == "__main__":
    asyncio.run(main())

