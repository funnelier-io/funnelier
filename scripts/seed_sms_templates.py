"""
Seed SMS templates for common campaign types.
Usage: python scripts/seed_sms_templates.py
"""

import asyncio
import sys
from pathlib import Path
from uuid import UUID, uuid4

sys.path.insert(0, str(Path(__file__).parent.parent))

TENANT_ID = UUID("00000000-0000-0000-0000-000000000001")

TEMPLATES = [
    {
        "name": "خوش‌آمدگویی",
        "content": "سلام {name} عزیز! 🎉\nاز آشنایی با شما خوشحالیم.\nبرای مشاوره رایگان با ما تماس بگیرید:\n{phone}",
        "description": "پیام خوش‌آمدگویی به سرنخ‌های جدید",
        "category": "welcome",
        "target_segments": ["new_customers", "promising"],
    },
    {
        "name": "پیگیری تماس",
        "content": "سلام {name} عزیز\nمتأسفانه تماس قبلی ما بی‌پاسخ ماند.\nآیا زمان مناسب‌تری برای تماس وجود دارد؟\nپاسخ: بله / خیر",
        "description": "پیام پیگیری برای تماس‌های بی‌پاسخ",
        "category": "follow_up",
        "target_segments": ["need_attention"],
    },
    {
        "name": "تخفیف ویژه",
        "content": "{name} عزیز\n🔥 فرصت استثنایی!\n{discount}% تخفیف ویژه فقط تا {deadline}\nبرای اطلاعات بیشتر تماس بگیرید:\n{phone}",
        "description": "پیام تخفیف ویژه برای مشتریان در خطر ریزش",
        "category": "discount",
        "target_segments": ["at_risk", "hibernating"],
    },
    {
        "name": "یادآوری خرید",
        "content": "سلام {name}\nمدتی است از شما بی‌خبریم! 😊\nمحصولات جدید ما را ببینید:\n{link}\nمنتظر تماس شما هستیم",
        "description": "یادآوری برای مشتریان غیرفعال",
        "category": "reminder",
        "target_segments": ["hibernating", "lost"],
    },
    {
        "name": "تشکر از خرید",
        "content": "سلام {name} عزیز\nاز خرید شما سپاسگزاریم! 🙏\nدر صورت هرگونه سؤال با ما تماس بگیرید:\n{phone}",
        "description": "پیام تشکر پس از خرید",
        "category": "thank_you",
        "target_segments": ["champions", "loyal"],
    },
    {
        "name": "معرفی محصول جدید",
        "content": "{name} عزیز\n✨ محصول جدید ما رسید!\n{product_name}\n📞 برای سفارش تماس بگیرید: {phone}",
        "description": "اطلاع‌رسانی محصول جدید",
        "category": "product_launch",
        "target_segments": ["champions", "loyal", "promising"],
    },
    {
        "name": "نظرسنجی رضایت",
        "content": "سلام {name}\nنظر شما برای ما مهم است! 📝\nلطفاً با پاسخ به این پیام، رضایت خود را از 1 تا 5 اعلام کنید.",
        "description": "نظرسنجی رضایت مشتری",
        "category": "survey",
        "target_segments": ["champions", "loyal", "at_risk"],
    },
    {
        "name": "دعوت به رویداد",
        "content": "{name} عزیز\n🎪 دعوت ویژه!\n{event_name}\n📅 {event_date}\n📍 {event_location}\nبرای ثبت‌نام: {link}",
        "description": "دعوت به نمایشگاه یا رویداد",
        "category": "event",
        "target_segments": ["champions", "loyal", "promising"],
    },
]


async def seed_templates():
    from src.infrastructure.database.session import get_session_factory
    from src.infrastructure.database.models.communications import SMSTemplateModel
    from sqlalchemy import select

    session_factory = get_session_factory()

    async with session_factory() as session:
        # Check existing
        result = await session.execute(
            select(SMSTemplateModel).where(SMSTemplateModel.tenant_id == TENANT_ID)
        )
        existing = result.scalars().all()
        existing_names = {t.name for t in existing}

        added = 0
        for tmpl in TEMPLATES:
            if tmpl["name"] in existing_names:
                print(f"   ⏭ Skipping '{tmpl['name']}' (exists)")
                continue

            model = SMSTemplateModel(
                id=uuid4(),
                tenant_id=TENANT_ID,
                name=tmpl["name"],
                content=tmpl["content"],
                description=tmpl["description"],
                category=tmpl["category"],
                target_segments=tmpl["target_segments"],
                is_active=True,
            )
            session.add(model)
            added += 1
            print(f"   ✅ Added '{tmpl['name']}'")

        await session.commit()
        print(f"\n📬 Seeded {added} new SMS templates (total: {len(existing) + added})")


async def main():
    print("=" * 60)
    print("📬 Funnelier — Seed SMS Templates")
    print("=" * 60)
    await seed_templates()
    print("\n✅ Done!")


if __name__ == "__main__":
    asyncio.run(main())

