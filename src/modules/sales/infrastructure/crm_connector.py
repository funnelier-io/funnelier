"""
CRM/ERP MongoDB Sync Service

Connects to the Sivan Land MongoDB CRM and syncs products, categories,
and customers into Funnelier's PostgreSQL database.
"""

import logging
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.database.models.sales import ProductModel
from src.infrastructure.database.models.leads import ContactModel

logger = logging.getLogger(__name__)


class CRMSyncService:
    """
    Syncs data from a MongoDB CRM/ERP into Funnelier's PostgreSQL.
    Supports: products, categories, customers.
    """

    def __init__(
        self,
        mongo_uri: str,
        mongo_database: str,
        pg_session: AsyncSession,
        tenant_id: UUID,
    ):
        self._mongo_uri = mongo_uri
        self._mongo_db_name = mongo_database
        self._session = pg_session
        self._tenant_id = tenant_id
        self._client: AsyncIOMotorClient | None = None
        self._db: AsyncIOMotorDatabase | None = None

    async def connect(self) -> bool:
        """Connect to MongoDB."""
        try:
            self._client = AsyncIOMotorClient(self._mongo_uri)
            self._db = self._client[self._mongo_db_name]
            await self._client.admin.command("ping")
            logger.info(f"Connected to MongoDB: {self._mongo_db_name}")
            return True
        except Exception as e:
            logger.error(f"MongoDB connection failed: {e}")
            return False

    async def disconnect(self):
        """Close MongoDB connection."""
        if self._client:
            self._client.close()
            self._client = None
            self._db = None

    async def test_connection(self) -> tuple[bool, str]:
        """Test MongoDB connection and return collection info."""
        try:
            if self._db is None:
                await self.connect()
            collections = await self._db.list_collection_names()
            counts = {}
            for col_name in collections:
                counts[col_name] = await self._db[col_name].estimated_document_count()
            return True, f"Connected. Collections: {counts}"
        except Exception as e:
            return False, f"Connection failed: {str(e)}"

    async def get_overview(self) -> dict[str, Any]:
        """Get overview of CRM data."""
        if self._db is None:
            await self.connect()

        result = {}
        for col_name in await self._db.list_collection_names():
            col = self._db[col_name]
            count = await col.estimated_document_count()
            sample = await col.find_one()
            fields = list(sample.keys()) if sample else []
            result[col_name] = {"count": count, "fields": fields}
        return result

    # ─────────────── Category Cache ───────────────

    async def _load_categories(self) -> dict[str, str]:
        """Load categories from MongoDB and return {oid: name} mapping."""
        if self._db is None:
            await self.connect()

        categories = {}
        async for doc in self._db["categories"].find():
            oid = str(doc["_id"])
            categories[oid] = doc.get("name") or doc.get("title_fa") or "Unknown"
        return categories

    # ─────────────── Product Sync ───────────────

    async def sync_products(self) -> dict[str, int]:
        """
        Sync products from MongoDB `items` collection to PostgreSQL `products` table.
        Uses metadata.external_id for upsert logic.
        Returns {created, updated, skipped, errors}.
        """
        if self._db is None:
            await self.connect()

        categories = await self._load_categories()
        stats = {"created": 0, "updated": 0, "skipped": 0, "errors": 0}

        async for item in self._db["items"].find({"status": 1}):
            try:
                mongo_id = str(item["_id"])
                cat_id = str(item.get("category_id", ""))
                category_name = categories.get(cat_id, "سایر")

                # Check if product with this external_id already exists
                existing = await self._session.execute(
                    select(ProductModel).where(
                        ProductModel.tenant_id == self._tenant_id,
                        ProductModel.metadata_.op("->>")("external_id") == mongo_id,
                    )
                )
                existing_product = existing.scalar_one_or_none()

                if existing_product:
                    # Update price and inventory
                    existing_product.current_price = item.get("price", 0)
                    existing_product.name = item.get("name") or item.get("name_fa") or "Unknown"
                    existing_product.description = item.get("description")
                    existing_product.unit = item.get("unit", "عدد")
                    existing_product.category = category_name
                    existing_product.metadata_ = {
                        **existing_product.metadata_,
                        "external_id": mongo_id,
                        "source_system": "sivan_land_v2",
                        "inventory": item.get("inventory", 0),
                        "name_en": item.get("name_en", ""),
                        "last_synced": datetime.utcnow().isoformat(),
                    }
                    stats["updated"] += 1
                else:
                    # Create new product
                    new_product = ProductModel(
                        id=uuid4(),
                        tenant_id=self._tenant_id,
                        name=item.get("name") or item.get("name_fa") or "Unknown",
                        code=str(item.get("tracking_code", "")),
                        category=category_name,
                        description=item.get("description"),
                        unit=item.get("unit", "عدد"),
                        current_price=item.get("price", 0),
                        is_active=True,
                        target_segments=[],
                        metadata_={
                            "external_id": mongo_id,
                            "source_system": "sivan_land_v2",
                            "inventory": item.get("inventory", 0),
                            "name_en": item.get("name_en", ""),
                            "seller_id": str(item.get("seller_id", "")),
                            "last_synced": datetime.utcnow().isoformat(),
                        },
                    )
                    self._session.add(new_product)
                    stats["created"] += 1

            except Exception as e:
                logger.error(f"Error syncing product {item.get('_id')}: {e}")
                stats["errors"] += 1

        await self._session.flush()
        logger.info(f"Product sync complete: {stats}")
        return stats

    # ─────────────── Customer Sync ───────────────

    async def sync_customers(self) -> dict[str, int]:
        """
        Sync customers from MongoDB to PostgreSQL contacts table.
        Maps MongoDB users/customers to leads/contacts.
        """
        if self._db is None:
            await self.connect()

        stats = {"created": 0, "updated": 0, "skipped": 0, "errors": 0}

        # Sync from users collection (which has lead-related fields)
        async for user in self._db["users"].find({"status": 1}):
            try:
                mongo_id = str(user["_id"])
                mobile = user.get("mobile", "")
                if not mobile:
                    stats["skipped"] += 1
                    continue

                # Normalize phone
                phone = mobile.replace("+", "").replace(" ", "").replace("-", "")
                if phone.startswith("0") and len(phone) == 11:
                    phone = phone[1:]  # Remove leading 0
                elif phone.startswith("98") and len(phone) == 12:
                    phone = phone[2:]

                if not (len(phone) == 10 and phone.startswith("9")):
                    stats["skipped"] += 1
                    continue

                # Check if contact exists
                existing = await self._session.execute(
                    select(ContactModel).where(
                        ContactModel.tenant_id == self._tenant_id,
                        ContactModel.phone_number == phone,
                    )
                )
                existing_contact = existing.scalar_one_or_none()

                full_name = f"{user.get('name', '')} {user.get('family', '')}".strip()
                province = user.get("province", "")
                city = user.get("city", "")

                if existing_contact:
                    # Update contact info from CRM
                    if full_name and not existing_contact.name:
                        existing_contact.name = full_name
                    if not existing_contact.notes:
                        existing_contact.notes = f"Province: {province}, City: {city}" if province else None
                    existing_contact.custom_fields = {
                        **existing_contact.custom_fields,
                        "crm_id": mongo_id,
                        "crm_source": "sivan_land_v2",
                        "crm_tracking_code": user.get("tracking_code"),
                        "national_code": user.get("national_code"),
                        "province": province,
                        "city": city,
                        "last_crm_sync": datetime.utcnow().isoformat(),
                    }
                    stats["updated"] += 1
                else:
                    # Create new contact
                    new_contact = ContactModel(
                        id=uuid4(),
                        tenant_id=self._tenant_id,
                        phone_number=phone,
                        name=full_name or None,
                        source_name="crm_import",
                        current_stage="lead_acquired",
                        is_active=True,
                        total_calls=0,
                        total_answered_calls=0,
                        total_call_duration=0,
                        total_sms_sent=0,
                        total_sms_delivered=0,
                        total_invoices=0,
                        total_paid_invoices=0,
                        total_revenue=0,
                        tags=[],
                        custom_fields={
                            "crm_id": mongo_id,
                            "crm_source": "sivan_land_v2",
                            "crm_tracking_code": user.get("tracking_code"),
                            "national_code": user.get("national_code"),
                            "province": province,
                            "city": city,
                            "email": user.get("email", ""),
                        },
                    )
                    self._session.add(new_contact)
                    stats["created"] += 1

            except Exception as e:
                logger.error(f"Error syncing customer {user.get('_id')}: {e}")
                stats["errors"] += 1

        await self._session.flush()
        logger.info(f"Customer sync complete: {stats}")
        return stats

    # ─────────────── Full Sync ───────────────

    async def full_sync(self) -> dict[str, Any]:
        """Run full sync of all entities."""
        results = {}
        try:
            connected = await self.connect()
            if not connected:
                return {"error": "Cannot connect to MongoDB"}

            results["products"] = await self.sync_products()
            results["customers"] = await self.sync_customers()
            results["synced_at"] = datetime.utcnow().isoformat()
            results["status"] = "success"
        except Exception as e:
            results["error"] = str(e)
            results["status"] = "failed"
            logger.exception("Full sync failed")
        finally:
            await self.disconnect()

        return results


