"""
Seed product catalog with building materials products.

Usage:
    PYTHONPATH=. python scripts/seed_products.py
"""

import asyncio
import sys
from pathlib import Path
from uuid import UUID, uuid4

sys.path.insert(0, str(Path(__file__).parent.parent))

TENANT_ID = UUID("00000000-0000-0000-0000-000000000001")

PRODUCTS = [
    {"name": "سیمان تیپ ۲ (پاکتی)", "category": "سیمان", "unit": "تن", "current_price": 85_000_000},
    {"name": "سیمان تیپ ۲ (فله)", "category": "سیمان", "unit": "تن", "current_price": 78_000_000},
    {"name": "سیمان تیپ ۵ (ضدسولفات)", "category": "سیمان", "unit": "تن", "current_price": 95_000_000},
    {"name": "سیمان سفید", "category": "سیمان", "unit": "تن", "current_price": 180_000_000},
    {"name": "سیمان پوزولانی", "category": "سیمان", "unit": "تن", "current_price": 82_000_000},
    {"name": "بتن آماده C25", "category": "بتن", "unit": "مترمکعب", "current_price": 12_500_000},
    {"name": "بتن آماده C30", "category": "بتن", "unit": "مترمکعب", "current_price": 14_000_000},
    {"name": "بتن آماده C35", "category": "بتن", "unit": "مترمکعب", "current_price": 15_500_000},
    {"name": "بتن آماده C40", "category": "بتن", "unit": "مترمکعب", "current_price": 17_000_000},
    {"name": "پوکه صنعتی", "category": "بتن", "unit": "مترمکعب", "current_price": 4_500_000},
    {"name": "کاشی دیواری ۲۵×۴۰", "category": "کاشی و سرامیک", "unit": "مترمربع", "current_price": 3_500_000},
    {"name": "سرامیک کف ۶۰×۶۰", "category": "کاشی و سرامیک", "unit": "مترمربع", "current_price": 5_200_000},
    {"name": "گرانیت پرسلان ۸۰×۸۰", "category": "کاشی و سرامیک", "unit": "مترمربع", "current_price": 8_500_000},
    {"name": "موزاییک حیاطی", "category": "کاشی و سرامیک", "unit": "مترمربع", "current_price": 2_800_000},
    {"name": "میلگرد A3 سایز ۱۲", "category": "آهن‌آلات", "unit": "کیلوگرم", "current_price": 450_000},
    {"name": "میلگرد A3 سایز ۱۶", "category": "آهن‌آلات", "unit": "کیلوگرم", "current_price": 440_000},
    {"name": "تیرآهن IPE 14", "category": "آهن‌آلات", "unit": "شاخه", "current_price": 52_000_000},
    {"name": "ورق سیاه ۱۰ میل", "category": "آهن‌آلات", "unit": "کیلوگرم", "current_price": 380_000},
    {"name": "لوله مانیسمان ۲ اینچ", "category": "آهن‌آلات", "unit": "شاخه", "current_price": 18_000_000},
    {"name": "ایزوگام شرق", "category": "عایق", "unit": "مترمربع", "current_price": 850_000},
    {"name": "پشم سنگ ۵ سانت", "category": "عایق", "unit": "مترمربع", "current_price": 1_200_000},
    {"name": "فوم پلی‌استایرن ۵ سانت", "category": "عایق", "unit": "مترمربع", "current_price": 650_000},
    {"name": "آجر سفال ۱۰ سانت", "category": "آجر و بلوک", "unit": "عدد", "current_price": 35_000},
    {"name": "بلوک سبک AAC", "category": "آجر و بلوک", "unit": "مترمکعب", "current_price": 9_500_000},
    {"name": "بلوک سیمانی توخالی", "category": "آجر و بلوک", "unit": "عدد", "current_price": 45_000},
    {"name": "گچ ساتن", "category": "گچ و ملات", "unit": "تن", "current_price": 15_000_000},
    {"name": "شن و ماسه شسته", "category": "شن و ماسه", "unit": "مترمکعب", "current_price": 3_200_000},
    {"name": "ماسه بادی", "category": "شن و ماسه", "unit": "مترمکعب", "current_price": 2_500_000},
]


async def main():
    from src.infrastructure.database.session import get_session_factory
    from src.infrastructure.database.models.sales import ProductModel
    from sqlalchemy import select

    factory = get_session_factory()

    print("=" * 60)
    print("Funnelier - Seed Building Materials Product Catalog")
    print("=" * 60)

    created = 0
    skipped = 0

    async with factory() as session:
        for p in PRODUCTS:
            stmt = select(ProductModel).where(
                ProductModel.tenant_id == TENANT_ID,
                ProductModel.name == p["name"],
            )
            existing = (await session.execute(stmt)).scalar_one_or_none()
            if existing:
                skipped += 1
                continue

            product = ProductModel(
                id=uuid4(),
                tenant_id=TENANT_ID,
                name=p["name"],
                category=p["category"],
                unit=p.get("unit", "unit"),
                current_price=p["current_price"],
                is_active=True,
            )
            session.add(product)
            created += 1
            print(f"  + {p['category']:20s} | {p['name']}")

        await session.commit()

    print(f"\nCreated: {created}, Skipped: {skipped}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())

