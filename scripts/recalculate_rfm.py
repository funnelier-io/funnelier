"""
Recalculate RFM segments for all contacts.

Usage:
    PYTHONPATH=. python scripts/recalculate_rfm.py
"""

import asyncio
import sys
from pathlib import Path
from uuid import UUID
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent.parent))

TENANT_ID = UUID("00000000-0000-0000-0000-000000000001")


async def recalculate_rfm():
    from sqlalchemy import select, func, update as sa_update
    from src.infrastructure.database.session import get_session_factory
    from src.infrastructure.database.models.leads import ContactModel
    from src.infrastructure.database.models.sales import PaymentModel
    from src.infrastructure.database.models.communications import CallLogModel
    from src.modules.segmentation.domain.services import RFMCalculationService
    from src.core.domain import RFMSegment

    factory = get_session_factory()
    now = datetime.now(timezone.utc)
    rfm_service = RFMCalculationService()

    print("=" * 60)
    print("🎯 Funnelier — RFM Recalculation")
    print("=" * 60)

    # Get payment data grouped by phone
    async with factory() as session:
        payments_stmt = (
            select(
                PaymentModel.phone_number,
                func.count(PaymentModel.id).label("frequency"),
                func.sum(PaymentModel.amount).label("monetary"),
                func.max(PaymentModel.paid_at).label("last_payment"),
            )
            .where(PaymentModel.tenant_id == TENANT_ID)
            .group_by(PaymentModel.phone_number)
        )
        payments_result = await session.execute(payments_stmt)
        payment_data = {
            row.phone_number: {
                "frequency": row.frequency,
                "monetary": float(row.monetary or 0),
                "last_payment": row.last_payment,
            }
            for row in payments_result.fetchall()
        }
        print(f"📊 Found payment data for {len(payment_data)} phone numbers")

        # Get call data grouped by phone (use as engagement signal)
        calls_stmt = (
            select(
                CallLogModel.phone_number,
                func.count(CallLogModel.id).label("call_count"),
                func.count(CallLogModel.id).filter(
                    CallLogModel.is_successful == True
                ).label("successful_calls"),
                func.max(CallLogModel.call_start).label("last_call"),
            )
            .where(CallLogModel.tenant_id == TENANT_ID)
            .group_by(CallLogModel.phone_number)
        )
        calls_result = await session.execute(calls_stmt)
        call_data = {
            row.phone_number: {
                "call_count": row.call_count,
                "successful_calls": row.successful_calls,
                "last_call": row.last_call,
            }
            for row in calls_result.fetchall()
        }
        print(f"📞 Found call data for {len(call_data)} phone numbers")

    # Process contacts in batches
    segment_counts = {}
    total_processed = 0
    batch_size = 500

    async with factory() as session:
        # Count total contacts
        total_count = (await session.execute(
            select(func.count(ContactModel.id))
            .where(ContactModel.tenant_id == TENANT_ID)
        )).scalar() or 0
        print(f"👥 Total contacts to process: {total_count:,}\n")

        offset = 0
        while offset < total_count:
            contacts_stmt = (
                select(ContactModel)
                .where(ContactModel.tenant_id == TENANT_ID)
                .offset(offset)
                .limit(batch_size)
            )
            contacts_result = await session.execute(contacts_stmt)
            contacts = contacts_result.scalars().all()

            if not contacts:
                break

            for contact in contacts:
                pdata = payment_data.get(contact.phone_number, {})
                cdata = call_data.get(contact.phone_number, {})

                frequency = pdata.get("frequency", 0)
                monetary = pdata.get("monetary", 0)
                last_payment = pdata.get("last_payment")

                # For contacts without payment data, use call engagement
                # as a proxy for frequency (scaled down)
                if frequency == 0 and cdata:
                    successful_calls = cdata.get("successful_calls", 0)
                    frequency = min(successful_calls, 3)  # Cap at 3

                recency_days = 999
                if last_payment:
                    if hasattr(last_payment, 'replace') and last_payment.tzinfo is None:
                        last_payment = last_payment.replace(tzinfo=timezone.utc)
                    recency_days = (now - last_payment).days
                elif cdata.get("last_call"):
                    last_call = cdata["last_call"]
                    if hasattr(last_call, 'replace') and last_call.tzinfo is None:
                        last_call = last_call.replace(tzinfo=timezone.utc)
                    recency_days = (now - last_call).days

                rfm_score = rfm_service.calculate_score(
                    days_since_last_purchase=recency_days,
                    purchase_count=frequency,
                    total_spend=monetary,
                )

                segment = RFMSegment.from_rfm_score(
                    rfm_score.recency, rfm_score.frequency, rfm_score.monetary
                )

                segment_name = segment.value
                segment_counts[segment_name] = segment_counts.get(segment_name, 0) + 1

                # Update contact RFM data
                stmt = (
                    sa_update(ContactModel)
                    .where(ContactModel.id == contact.id)
                    .values(
                        rfm_segment=segment_name,
                        rfm_score=f"{rfm_score.recency}{rfm_score.frequency}{rfm_score.monetary}",
                        recency_score=rfm_score.recency,
                        frequency_score=rfm_score.frequency,
                        monetary_score=rfm_score.monetary,
                        last_rfm_update=now,
                    )
                )
                await session.execute(stmt)

            total_processed += len(contacts)
            print(f"   ⏳ Processed {total_processed:,} / {total_count:,} contacts...")
            offset += batch_size

        await session.commit()

    print(f"\n📊 RFM Segment Distribution:")
    print(f"   {'Segment':25s} {'Count':>8s} {'Percent':>8s}")
    print(f"   {'-'*25} {'-'*8} {'-'*8}")
    for segment, count in sorted(segment_counts.items(), key=lambda x: -x[1]):
        pct = count / total_processed * 100 if total_processed > 0 else 0
        bar = "█" * max(int(pct / 2), 1)
        print(f"   {segment:25s} {count:>8,} {pct:>6.1f}% {bar}")
    print(f"   {'-'*25} {'-'*8}")
    print(f"   {'TOTAL':25s} {total_processed:>8,}")

    print(f"\n✅ RFM recalculation complete!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(recalculate_rfm())

