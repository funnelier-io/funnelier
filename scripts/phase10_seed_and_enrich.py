"""
Phase 10: Seed alert rules, SMS templates, backfill funnel snapshots,
          generate synthetic invoices/payments, and re-run RFM.

This script makes every dashboard page show meaningful data.

Usage:
    cd /Users/univers/projects/funnelier
    python scripts/phase10_seed_and_enrich.py
"""

import asyncio
import random
import sys
from datetime import datetime, timedelta, timezone, date
from pathlib import Path
from uuid import UUID, uuid4

sys.path.insert(0, str(Path(__file__).parent.parent))

TENANT_ID = UUID("00000000-0000-0000-0000-000000000001")


def _utcnow():
    return datetime.now(timezone.utc)


# ──────────────────────────────────────────────────────────────
# 1. Seed Alert Rules
# ──────────────────────────────────────────────────────────────

ALERT_RULES = [
    {
        "name": "کاهش نرخ تبدیل",
        "description": "نرخ تبدیل کلی زیر آستانه مشخص افت کرده است",
        "metric_name": "conversion_rate",
        "condition": "lt",
        "threshold_value": 0.02,
        "severity": "critical",
        "channels": ["dashboard", "sms"],
    },
    {
        "name": "کاهش نرخ پاسخ تماس",
        "description": "نرخ پاسخ‌گویی به تماس‌ها به کمتر از ۳۰٪ رسیده است",
        "metric_name": "call_answer_rate",
        "condition": "lt",
        "threshold_value": 0.30,
        "severity": "warning",
        "channels": ["dashboard"],
    },
    {
        "name": "عدم واردسازی روزانه",
        "description": "هیچ سرنخ جدیدی در ۲۴ ساعت گذشته وارد نشده است",
        "metric_name": "daily_leads",
        "condition": "eq",
        "threshold_value": 0,
        "severity": "warning",
        "channels": ["dashboard"],
    },
    {
        "name": "افزایش سرنخ‌های خواب",
        "description": "بیش از ۵۰٪ مخاطبین در بخش خواب (hibernating) هستند",
        "metric_name": "hibernating_percentage",
        "condition": "gt",
        "threshold_value": 0.50,
        "severity": "info",
        "channels": ["dashboard"],
    },
    {
        "name": "هدف درآمد ماهانه",
        "description": "درآمد ماهانه به هدف تعیین‌شده نرسیده است",
        "metric_name": "monthly_revenue",
        "condition": "lt",
        "threshold_value": 5_000_000_000,  # 5B rial
        "severity": "warning",
        "channels": ["dashboard", "sms"],
    },
]


async def seed_alert_rules():
    from sqlalchemy import select
    from src.infrastructure.database.session import get_session_factory
    from src.infrastructure.database.models.analytics import AlertRuleModel

    factory = get_session_factory()
    print("🔔 Step 1: Seeding alert rules...")

    async with factory() as session:
        existing = (await session.execute(
            select(AlertRuleModel.name).where(AlertRuleModel.tenant_id == TENANT_ID)
        )).scalars().all()
        existing_names = set(existing)

        added = 0
        for rule in ALERT_RULES:
            if rule["name"] in existing_names:
                print(f"   ⏭ {rule['name']} (exists)")
                continue

            model = AlertRuleModel(
                id=uuid4(),
                tenant_id=TENANT_ID,
                name=rule["name"],
                description=rule["description"],
                metric_name=rule["metric_name"],
                condition=rule["condition"],
                threshold_value=rule["threshold_value"],
                severity=rule["severity"],
                notification_channels=rule["channels"],
                is_active=True,
            )
            session.add(model)
            added += 1
            print(f"   ✅ {rule['name']}")

        await session.commit()
    print(f"   → {added} alert rules created\n")


# ──────────────────────────────────────────────────────────────
# 2. Seed SMS Templates
# ──────────────────────────────────────────────────────────────

async def seed_sms_templates():
    """Run the existing seed script inline."""
    from sqlalchemy import select
    from src.infrastructure.database.session import get_session_factory
    from src.infrastructure.database.models.communications import SMSTemplateModel

    TEMPLATES = [
        {"name": "خوش‌آمدگویی", "content": "سلام {name} عزیز! 🎉\nاز آشنایی با شما خوشحالیم.\nبرای مشاوره رایگان با ما تماس بگیرید:\n{phone}", "category": "welcome", "target_segments": ["new_customers", "promising"]},
        {"name": "پیگیری تماس", "content": "سلام {name} عزیز\nمتأسفانه تماس قبلی ما بی‌پاسخ ماند.\nآیا زمان مناسب‌تری برای تماس وجود دارد؟\nپاسخ: بله / خیر", "category": "follow_up", "target_segments": ["need_attention"]},
        {"name": "تخفیف ویژه", "content": "{name} عزیز\n🔥 فرصت استثنایی!\n{discount}% تخفیف ویژه فقط تا {deadline}\nبرای اطلاعات بیشتر تماس بگیرید:\n{phone}", "category": "discount", "target_segments": ["at_risk", "hibernating"]},
        {"name": "یادآوری خرید", "content": "سلام {name}\nمدتی است از شما بی‌خبریم! 😊\nمحصولات جدید ما را ببینید:\n{link}\nمنتظر تماس شما هستیم", "category": "reminder", "target_segments": ["hibernating", "lost"]},
        {"name": "تشکر از خرید", "content": "سلام {name} عزیز\nاز خرید شما سپاسگزاریم! 🙏\nدر صورت هرگونه سؤال با ما تماس بگیرید:\n{phone}", "category": "thank_you", "target_segments": ["champions", "loyal"]},
        {"name": "معرفی محصول جدید", "content": "{name} عزیز\n✨ محصول جدید ما رسید!\n{product_name}\n📞 برای سفارش تماس بگیرید: {phone}", "category": "product_launch", "target_segments": ["champions", "loyal", "promising"]},
        {"name": "نظرسنجی رضایت", "content": "سلام {name}\nنظر شما برای ما مهم است! 📝\nلطفاً با پاسخ به این پیام، رضایت خود را از 1 تا 5 اعلام کنید.", "category": "survey", "target_segments": ["champions", "loyal", "at_risk"]},
        {"name": "دعوت به رویداد", "content": "{name} عزیز\n🎪 دعوت ویژه!\n{event_name}\n📅 {event_date}\n📍 {event_location}\nبرای ثبت‌نام: {link}", "category": "event", "target_segments": ["champions", "loyal", "promising"]},
    ]

    factory = get_session_factory()
    print("📬 Step 2: Seeding SMS templates...")

    async with factory() as session:
        existing = (await session.execute(
            select(SMSTemplateModel.name).where(SMSTemplateModel.tenant_id == TENANT_ID)
        )).scalars().all()
        existing_names = set(existing)

        added = 0
        for t in TEMPLATES:
            if t["name"] in existing_names:
                continue
            session.add(SMSTemplateModel(
                id=uuid4(), tenant_id=TENANT_ID,
                name=t["name"], content=t["content"],
                category=t["category"], target_segments=t["target_segments"],
                is_active=True,
            ))
            added += 1
            print(f"   ✅ {t['name']}")

        await session.commit()
    print(f"   → {added} templates created\n")


# ──────────────────────────────────────────────────────────────
# 3. Backfill Funnel Snapshots (last 30 days)
# ──────────────────────────────────────────────────────────────

async def backfill_funnel_snapshots():
    from sqlalchemy import text, select
    from src.infrastructure.database.session import get_session_factory
    from src.infrastructure.database.models.analytics import FunnelSnapshotModel

    factory = get_session_factory()
    print("📸 Step 3: Backfilling funnel snapshots (30 days)...")

    async with factory() as session:
        # Get current stage counts as baseline
        result = await session.execute(text("""
            SELECT current_stage, count(*) FROM contacts
            WHERE tenant_id = :tid GROUP BY current_stage
        """), {"tid": str(TENANT_ID)})
        current_counts = {row[0]: row[1] for row in result.fetchall()}
        total = sum(current_counts.values())

        # Check existing snapshots
        existing = (await session.execute(
            select(FunnelSnapshotModel.snapshot_date)
            .where(FunnelSnapshotModel.tenant_id == TENANT_ID)
        )).scalars().all()
        existing_dates = set(existing)

        today = date.today()
        added = 0

        for days_ago in range(30, -1, -1):
            snap_date = today - timedelta(days=days_ago)
            if snap_date in existing_dates:
                continue

            # Simulate gradual growth: earlier dates have fewer contacts
            growth_factor = 1.0 - (days_ago * 0.008)  # ~24% less 30 days ago
            noise = random.uniform(0.97, 1.03)  # ±3% daily noise

            stage_counts = {}
            for stage, count in current_counts.items():
                stage_counts[stage] = max(1, int(count * growth_factor * noise))

            snap_total = sum(stage_counts.values())
            conversion_rate = stage_counts.get("payment_received", 0) / max(snap_total, 1)

            # Simulated daily new leads (50-150/day)
            daily_leads = random.randint(50, 150)
            daily_calls = random.randint(20, 80)
            daily_answered = int(daily_calls * random.uniform(0.3, 0.6))

            model = FunnelSnapshotModel(
                id=uuid4(),
                tenant_id=TENANT_ID,
                snapshot_date=snap_date,
                stage_counts=stage_counts,
                conversion_rates={},
                overall_conversion_rate=round(conversion_rate, 6),
                new_leads=daily_leads,
                new_conversions=random.randint(0, 5),
                daily_revenue=random.randint(0, 500_000_000),
                new_sms_sent=random.randint(10, 60),
                new_sms_delivered=random.randint(8, 55),
                new_calls=daily_calls,
                new_answered_calls=daily_answered,
                new_successful_calls=daily_answered,
                new_invoices=random.randint(0, 8),
                new_payments=random.randint(0, 5),
            )
            session.add(model)
            added += 1

        await session.commit()
    print(f"   → {added} snapshots created (total: {added + len(existing_dates)})\n")


# ──────────────────────────────────────────────────────────────
# 4. Generate Invoices & Payments for contacts with call_answered
# ──────────────────────────────────────────────────────────────

async def generate_invoices_and_payments():
    from sqlalchemy import text, select
    from src.infrastructure.database.session import get_session_factory
    from src.infrastructure.database.models.sales import InvoiceModel, InvoiceLineItemModel, PaymentModel, ProductModel

    factory = get_session_factory()
    print("🧾 Step 4: Generating invoices & payments...")

    async with factory() as session:
        # Check if invoices already exist
        inv_count = (await session.execute(
            text("SELECT count(*) FROM invoices WHERE tenant_id = :tid"),
            {"tid": str(TENANT_ID)}
        )).scalar()

        if inv_count > 10:
            print(f"   ⏭ Already have {inv_count} invoices, skipping\n")
            return

        # Get products for line items
        products = (await session.execute(
            select(ProductModel).where(ProductModel.tenant_id == TENANT_ID)
        )).scalars().all()

        if not products:
            print("   ⚠️ No products found, run seed_products.py first")
            return

        # Get contacts with successful calls (these are warm leads)
        result = await session.execute(text("""
            SELECT id, phone_number, name, assigned_to
            FROM contacts
            WHERE tenant_id = :tid
              AND current_stage = 'call_answered'
            ORDER BY random()
            LIMIT 300
        """), {"tid": str(TENANT_ID)})
        warm_contacts = result.fetchall()
        print(f"   → {len(warm_contacts)} warm contacts (call_answered) to process")

        # ~40% get invoices, ~70% of those get payments
        invoice_contacts = warm_contacts[:int(len(warm_contacts) * 0.40)]
        now = _utcnow()
        invoices_created = 0
        payments_created = 0
        total_revenue = 0

        for contact in invoice_contacts:
            contact_id, phone, name, salesperson_id = contact

            # Create invoice with 1-3 random products
            num_items = random.randint(1, 3)
            selected_products = random.sample(products, min(num_items, len(products)))

            items = []
            subtotal = 0
            for prod in selected_products:
                # Keep quantities small enough that total stays under int32 max (~2.1B)
                if prod.current_price > 50_000_000:
                    qty = random.randint(1, 3)      # expensive items (cement per ton, etc.)
                elif prod.current_price > 5_000_000:
                    qty = random.randint(1, 8)      # mid-range
                else:
                    qty = random.randint(2, 20)     # cheap items (bricks, etc.)
                line_total = int(prod.current_price * qty)
                items.append({
                    "product_id": str(prod.id),
                    "product_name": prod.name,
                    "quantity": qty,
                    "unit_price": int(prod.current_price),
                    "total_price": line_total,
                })
                subtotal += line_total

            # Hard cap: total_amount = (subtotal - discount) * 1.09
            # int32 max ≈ 2.1B, so keep subtotal under 1.8B
            MAX_SUBTOTAL = 1_800_000_000
            if subtotal > MAX_SUBTOTAL:
                # Scale down all items proportionally
                scale = MAX_SUBTOTAL / subtotal
                subtotal = 0
                for item in items:
                    item["total_price"] = int(item["total_price"] * scale)
                    item["quantity"] = max(1, int(item["quantity"] * scale))
                    subtotal += item["total_price"]

            # Random discount 0-15%
            discount_pct = random.choice([0, 0, 0, 5, 5, 10, 10, 15])
            discount_amount = int(subtotal * discount_pct / 100)
            total_amount = subtotal - discount_amount

            # Invoice date: random in last 60 days
            invoice_date = now - timedelta(days=random.randint(1, 60))

            # Status: 60% paid, 20% issued, 10% overdue, 10% draft
            status_roll = random.random()
            if status_roll < 0.60:
                status = "paid"
            elif status_roll < 0.80:
                status = "issued"
            elif status_roll < 0.90:
                status = "overdue"
            else:
                status = "draft"

            invoice = InvoiceModel(
                id=uuid4(),
                tenant_id=TENANT_ID,
                contact_id=contact_id,
                phone_number=phone,
                salesperson_id=salesperson_id,
                invoice_number=f"INV-{invoices_created + 1001}",
                invoice_type="invoice",
                status=status,
                subtotal=subtotal,
                discount_amount=discount_amount,
                tax_amount=int(total_amount * 0.09),  # 9% VAT
                total_amount=total_amount + int(total_amount * 0.09),
                issued_at=invoice_date,
                due_date=invoice_date + timedelta(days=30),
            )
            session.add(invoice)
            await session.flush()  # get invoice.id for line items

            # Create line items
            for item in items:
                line = InvoiceLineItemModel(
                    id=uuid4(),
                    invoice_id=invoice.id,
                    product_id=UUID(item["product_id"]),
                    product_name=item["product_name"],
                    quantity=item["quantity"],
                    unit_price=item["unit_price"],
                    total=item["total_price"],
                )
                session.add(line)

            invoices_created += 1

            # Create payment if paid
            if status == "paid":
                payment_date = invoice_date + timedelta(days=random.randint(1, 20))
                payment = PaymentModel(
                    id=uuid4(),
                    tenant_id=TENANT_ID,
                    invoice_id=invoice.id,
                    contact_id=contact_id,
                    phone_number=phone,
                    amount=invoice.total_amount,
                    payment_method=random.choice(["bank_transfer", "cash", "check", "card"]),
                    reference_number=f"PAY-{random.randint(100000, 999999)}",
                    paid_at=payment_date,
                    status="confirmed",
                )
                session.add(payment)
                payments_created += 1
                total_revenue += invoice.total_amount

        await session.commit()

    print(f"   → {invoices_created} invoices, {payments_created} payments")
    print(f"   → Total revenue: {total_revenue:,.0f} rial ({total_revenue/10_000_000:.1f}M toman)\n")


# ──────────────────────────────────────────────────────────────
# 5. Update contact stages for invoice/payment contacts
# ──────────────────────────────────────────────────────────────

async def update_sales_stages():
    from sqlalchemy import text
    from src.infrastructure.database.session import get_session_factory

    factory = get_session_factory()
    print("📊 Step 5: Updating contact stages for invoiced/paid contacts...")

    async with factory() as session:
        # Contacts with invoices → invoice_issued
        result = await session.execute(text("""
            UPDATE contacts SET current_stage = 'invoice_issued', stage_entered_at = now()
            WHERE tenant_id = :tid
            AND id IN (SELECT DISTINCT contact_id FROM invoices WHERE tenant_id = :tid AND status != 'draft')
            AND current_stage NOT IN ('payment_received')
        """), {"tid": str(TENANT_ID)})
        print(f"   → {result.rowcount} contacts → invoice_issued")

        # Contacts with paid invoices → payment_received
        result = await session.execute(text("""
            UPDATE contacts SET current_stage = 'payment_received', stage_entered_at = now()
            WHERE tenant_id = :tid
            AND id IN (
                SELECT DISTINCT contact_id FROM invoices
                WHERE tenant_id = :tid AND status = 'paid'
            )
        """), {"tid": str(TENANT_ID)})
        print(f"   → {result.rowcount} contacts → payment_received")

        # Update purchase stats on contacts
        result = await session.execute(text("""
            UPDATE contacts c SET
                total_paid_invoices = sub.paid_count,
                total_revenue = sub.total_rev,
                last_purchase_at = sub.last_pay
            FROM (
                SELECT i.contact_id,
                       COUNT(*) FILTER (WHERE i.status = 'paid') as paid_count,
                       COALESCE(SUM(i.total_amount) FILTER (WHERE i.status = 'paid'), 0) as total_rev,
                       MAX(p.paid_at) as last_pay
                FROM invoices i
                LEFT JOIN payments p ON p.invoice_id = i.id
                WHERE i.tenant_id = :tid
                GROUP BY i.contact_id
            ) sub
            WHERE c.id = sub.contact_id AND c.tenant_id = :tid
        """), {"tid": str(TENANT_ID)})
        print(f"   → {result.rowcount} contacts updated with purchase stats")

        await session.commit()
    print("   ✅ Done\n")


# ──────────────────────────────────────────────────────────────
# 6. Re-run RFM with real purchase data
# ──────────────────────────────────────────────────────────────

async def recalculate_rfm():
    from sqlalchemy import text
    from src.infrastructure.database.session import get_session_factory

    factory = get_session_factory()
    print("🧮 Step 6: Recalculating RFM scores with purchase data...")

    now = _utcnow()

    async with factory() as session:
        # Fetch all contacts
        result = await session.execute(text("""
            SELECT id, phone_number, last_purchase_at,
                   COALESCE(total_paid_invoices, 0) as purchases,
                   COALESCE(total_revenue, 0) as revenue,
                   COALESCE(total_calls, 0) as calls,
                   COALESCE(total_answered_calls, 0) as answered
            FROM contacts
            WHERE tenant_id = :tid AND is_active = true
        """), {"tid": str(TENANT_ID)})
        rows = result.fetchall()
        print(f"   → Processing {len(rows):,} contacts...")

        segment_counts = {}
        batch_updates = []

        for row in rows:
            cid, phone, last_purchase, purchases, revenue, calls, answered = row

            # Determine segment based on purchase + engagement data
            if purchases > 0 and revenue > 1_000_000_000:
                segment = "champions"
                r, f, m = 5, 5, 5
            elif purchases > 0 and revenue > 500_000_000:
                segment = "loyal"
                r, f, m = 4, 4, 4
            elif purchases > 0:
                segment = "potential_loyalist"
                r, f, m = 3, 3, 3
            elif answered and answered > 2:
                segment = "promising"
                r, f, m = 3, 2, 1
            elif answered and answered > 0:
                segment = "potential_loyalist"
                r, f, m = 3, 2, 1
            elif calls and calls > 2:
                segment = "needs_attention"
                r, f, m = 2, 1, 1
            elif calls and calls > 0:
                segment = "new_customers"
                r, f, m = 2, 1, 1
            else:
                segment = "hibernating"
                r, f, m = 1, 1, 1

            # Adjust recency if we have purchase data
            if last_purchase:
                days = (now - last_purchase).days
                if days <= 14:
                    r = 5
                elif days <= 30:
                    r = 4
                elif days <= 60:
                    r = 3
                elif days <= 90:
                    r = 2
                else:
                    r = 1

            segment_counts[segment] = segment_counts.get(segment, 0) + 1
            batch_updates.append((str(cid), segment, f"{r}{f}{m}", r, f, m))

        # Batch update in chunks
        chunk_size = 1000
        for i in range(0, len(batch_updates), chunk_size):
            chunk = batch_updates[i:i + chunk_size]
            for cid, seg, score, r, f, m in chunk:
                await session.execute(text("""
                    UPDATE contacts SET
                        rfm_segment = :seg, rfm_score = :score,
                        recency_score = :r, frequency_score = :f, monetary_score = :m,
                        last_rfm_update = :now
                    WHERE id = :cid AND tenant_id = :tid
                """), {"seg": seg, "score": score, "r": r, "f": f, "m": m,
                       "now": now, "cid": cid, "tid": str(TENANT_ID)})
            await session.flush()
            pct = min((i + chunk_size) / len(batch_updates) * 100, 100)
            print(f"   → {pct:.0f}% done...")

        await session.commit()

    print(f"\n   RFM Distribution:")
    total = sum(segment_counts.values())
    for seg, cnt in sorted(segment_counts.items(), key=lambda x: -x[1]):
        pct = cnt / total * 100
        labels = {
            "champions": "🏆 قهرمانان",
            "loyal": "💎 وفادار",
            "potential_loyalist": "📈 بالقوه وفادار",
            "new_customers": "🆕 مشتریان جدید",
            "promising": "⭐ امیدوارکننده",
            "needs_attention": "⚠️ نیاز به توجه",
            "at_risk": "🔴 در خطر",
            "hibernating": "😴 خواب رفته",
            "lost": "❌ از دست رفته",
        }
        label = labels.get(seg, seg)
        bar = "█" * max(1, int(pct / 3))
        print(f"     {label:25s} {cnt:>8,} ({pct:5.1f}%) {bar}")
    print(f"     {'TOTAL':25s} {total:>8,}\n")


# ──────────────────────────────────────────────────────────────
# 7. Final Summary
# ──────────────────────────────────────────────────────────────

async def show_summary():
    from sqlalchemy import text
    from src.infrastructure.database.session import get_session_factory

    factory = get_session_factory()

    async with factory() as session:
        result = await session.execute(text("""
            SELECT
                (SELECT count(*) FROM contacts WHERE tenant_id = :tid) as contacts,
                (SELECT count(*) FROM call_logs WHERE tenant_id = :tid) as calls,
                (SELECT count(*) FROM sms_logs WHERE tenant_id = :tid) as sms,
                (SELECT count(*) FROM invoices WHERE tenant_id = :tid) as invoices,
                (SELECT count(*) FROM payments WHERE tenant_id = :tid) as payments,
                (SELECT count(*) FROM funnel_snapshots WHERE tenant_id = :tid) as snapshots,
                (SELECT count(*) FROM alert_rules WHERE tenant_id = :tid) as alert_rules,
                (SELECT count(*) FROM sms_templates WHERE tenant_id = :tid) as templates,
                (SELECT count(*) FROM products WHERE tenant_id = :tid) as products,
                (SELECT count(DISTINCT rfm_segment) FROM contacts WHERE tenant_id = :tid AND rfm_segment IS NOT NULL) as segments
        """), {"tid": str(TENANT_ID)})
        row = result.fetchone()

        result2 = await session.execute(text("""
            SELECT current_stage, count(*) FROM contacts
            WHERE tenant_id = :tid GROUP BY current_stage
            ORDER BY count(*) DESC
        """), {"tid": str(TENANT_ID)})
        stages = result2.fetchall()

    print("=" * 60)
    print("📋 Final Data Summary")
    print("=" * 60)
    labels = ["Contacts", "Call Logs", "SMS Logs", "Invoices", "Payments",
              "Snapshots", "Alert Rules", "Templates", "Products", "RFM Segments"]
    for label, val in zip(labels, row):
        print(f"   {label:20s}: {val:>8,}")

    print(f"\n   Funnel Distribution:")
    for stage, count in stages:
        print(f"     {stage:20s}: {count:>8,}")
    print("=" * 60)


# ──────────────────────────────────────────────────────────────

async def main():
    from src.infrastructure.database import init_database

    print("=" * 60)
    print("🚀 Funnelier — Phase 10: Seed, Enrich & Fully Hydrate")
    print("=" * 60 + "\n")

    await init_database()

    await seed_alert_rules()
    await seed_sms_templates()
    await backfill_funnel_snapshots()
    await generate_invoices_and_payments()
    await update_sales_stages()
    await recalculate_rfm()
    await show_summary()

    print("\n✅ Phase 10 Complete! All dashboard pages should now show data.")
    print("   Start the backend and frontend to verify:")
    print("   make dev-backend   # Terminal 1")
    print("   make dev-frontend  # Terminal 2")
    print("   Open http://funnelier.localhost")


if __name__ == "__main__":
    asyncio.run(main())



