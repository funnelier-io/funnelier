"""
Contact Loader

Specialized loader for contact/lead data with deduplication
and merge logic.
"""

from datetime import datetime
from typing import Any

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo import UpdateOne

from src.core.interfaces import DataRecord

from .base import BaseLoader, LoaderRegistry, LoadResult


@LoaderRegistry.register("contact")
class ContactLoader(BaseLoader):
    """
    Loader for contact/lead data.
    Handles deduplication by phone number and merges data from multiple sources.
    """

    def __init__(
        self,
        connection_string: str,
        database_name: str,
        tenant_id: str | None = None,
    ):
        super().__init__(tenant_id)
        self._connection_string = connection_string
        self._database_name = database_name
        self._client: AsyncIOMotorClient | None = None
        self._db: AsyncIOMotorDatabase | None = None

    async def connect(self) -> bool:
        """Connect to MongoDB."""
        try:
            self._client = AsyncIOMotorClient(self._connection_string)
            await self._client.admin.command("ping")
            self._db = self._client[self._database_name]
            self._connected = True
            return True
        except Exception:
            self._connected = False
            return False

    async def disconnect(self) -> None:
        """Close connection."""
        if self._client:
            self._client.close()
        self._client = None
        self._db = None
        self._connected = False

    async def load_with_result(
        self,
        records: list[DataRecord],
        target: str,
        upsert: bool = True,
    ) -> LoadResult:
        """Load contacts with deduplication and merge logic."""
        result = LoadResult(
            success_count=0,
            error_count=0,
            errors=[],
            started_at=datetime.utcnow(),
        )

        if not self._connected:
            await self.connect()

        if not self._db:
            result.errors.append("Database connection not established")
            result.complete()
            return result

        collection = self._db[target]

        operations = []
        for record in records:
            try:
                data = self._prepare_contact_record(record)
                phone = data.get("phone_number")

                if not phone:
                    result.error_count += 1
                    result.errors.append("Record missing phone number")
                    continue

                # Build update operation with merge logic
                update_doc = self._build_merge_update(data)

                operations.append(
                    UpdateOne(
                        {"phone_number": phone},
                        update_doc,
                        upsert=True,
                    )
                )
            except Exception as e:
                result.error_count += 1
                result.errors.append(f"Prepare error: {str(e)}")

        if operations:
            try:
                bulk_result = await collection.bulk_write(operations, ordered=False)
                result.success_count = bulk_result.modified_count + bulk_result.upserted_count
                result.created_count = bulk_result.upserted_count
                result.updated_count = bulk_result.modified_count
            except Exception as e:
                result.error_count += len(operations)
                result.errors.append(f"Bulk write error: {str(e)}")

        result.complete()
        return result

    def _prepare_contact_record(self, record: DataRecord) -> dict[str, Any]:
        """Prepare contact record for loading."""
        data = dict(record.data)

        # Core fields
        contact = {
            "phone_number": data.get("phone_number"),
            "phone_valid": data.get("phone_valid", False),
            "phone_carrier": data.get("phone_carrier"),
            "is_mobile": data.get("is_mobile", False),
        }

        # Optional fields - only include if present
        if data.get("name"):
            contact["name"] = data["name"]
        if data.get("company"):
            contact["company"] = data["company"]
        if data.get("city"):
            contact["city"] = data["city"]
        if data.get("region"):
            contact["region"] = data["region"]
        if data.get("email"):
            contact["email"] = data["email"]

        # Source tracking
        contact["sources"] = [{
            "file": data.get("source_file"),
            "sheet": data.get("source_sheet"),
            "category": data.get("category"),
            "imported_at": datetime.utcnow(),
        }]

        # Categories
        if data.get("category"):
            contact["categories"] = [data["category"]]

        # Quality score
        if data.get("quality_score"):
            contact["quality_score"] = data["quality_score"]

        # Tenant ID
        if self._tenant_id:
            contact["tenant_id"] = self._tenant_id

        return contact

    def _build_merge_update(self, data: dict[str, Any]) -> dict[str, Any]:
        """Build update document with merge logic."""
        now = datetime.utcnow()

        # Fields to set only on insert
        set_on_insert = {
            "created_at": now,
            "phone_number": data["phone_number"],
        }

        # Fields to always update
        set_fields = {
            "updated_at": now,
            "phone_valid": data.get("phone_valid", False),
            "phone_carrier": data.get("phone_carrier"),
            "is_mobile": data.get("is_mobile", False),
        }

        # Conditional updates - only update if value exists and is not empty
        for field in ["name", "company", "city", "region", "email"]:
            if data.get(field):
                set_fields[field] = data[field]

        # Update quality score if higher
        if data.get("quality_score"):
            set_fields["quality_score"] = data["quality_score"]

        # Add tenant ID
        if self._tenant_id:
            set_fields["tenant_id"] = self._tenant_id

        update_doc: dict[str, Any] = {
            "$setOnInsert": set_on_insert,
            "$set": set_fields,
        }

        # Add to sources array (track import history)
        if data.get("sources"):
            update_doc["$push"] = {
                "sources": {"$each": data["sources"], "$slice": -10}  # Keep last 10 sources
            }

        # Add to categories set
        if data.get("categories"):
            update_doc["$addToSet"] = {
                "categories": {"$each": data["categories"]}
            }

        return update_doc

    async def merge_contacts(self, phone_numbers: list[str]) -> dict[str, Any]:
        """
        Merge duplicate contacts by phone number.
        Returns merge statistics.
        """
        if not self._connected:
            await self.connect()

        if not self._db:
            return {"error": "Database connection not established"}

        # This would implement contact merge logic
        # For now, just return a placeholder
        return {
            "merged_count": 0,
            "total_count": len(phone_numbers),
        }

    async def get_contact_by_phone(self, phone_number: str) -> dict[str, Any] | None:
        """Get contact by phone number."""
        if not self._connected:
            await self.connect()

        if not self._db:
            return None

        collection = self._db["contacts"]
        return await collection.find_one({"phone_number": phone_number})

    async def update_contact_stage(
        self,
        phone_number: str,
        stage: str,
        stage_data: dict[str, Any] | None = None,
    ) -> bool:
        """Update contact's funnel stage."""
        if not self._connected:
            await self.connect()

        if not self._db:
            return False

        collection = self._db["contacts"]
        now = datetime.utcnow()

        update_doc = {
            "$set": {
                "current_stage": stage,
                f"stage_history.{stage}": now,
                "updated_at": now,
            },
        }

        if stage_data:
            update_doc["$set"][f"stage_data.{stage}"] = stage_data

        result = await collection.update_one(
            {"phone_number": phone_number},
            update_doc,
        )

        return result.modified_count > 0

