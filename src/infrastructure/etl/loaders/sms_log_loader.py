"""
SMS Log Loader

Specialized loader for SMS delivery data with funnel stage updates.
"""

from datetime import datetime
from typing import Any

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo import UpdateOne

from src.core.interfaces import DataRecord

from .base import BaseLoader, LoaderRegistry, LoadResult


@LoaderRegistry.register("sms_log")
class SMSLogLoader(BaseLoader):
    """
    Loader for SMS delivery log data.
    Stores SMS records and updates contact funnel stages.
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
        """Load SMS logs and update contact stages."""
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

        sms_log_collection = self._db[target]
        contacts_collection = self._db["contacts"]

        sms_operations = []
        contact_updates = []

        for record in records:
            try:
                data = self._prepare_sms_record(record)
                phone = data.get("phone_number")
                message_id = data.get("message_id")

                if not phone:
                    result.error_count += 1
                    result.errors.append("Record missing phone number")
                    continue

                if not message_id:
                    result.error_count += 1
                    result.errors.append("Record missing message ID")
                    continue

                # Add SMS log
                if upsert:
                    sms_operations.append(
                        UpdateOne(
                            {"message_id": message_id},
                            {"$set": data},
                            upsert=True,
                        )
                    )
                else:
                    sms_operations.append(
                        UpdateOne(
                            {"message_id": message_id},
                            {"$setOnInsert": data},
                            upsert=True,
                        )
                    )

                # Update contact stage based on SMS outcome
                contact_update = self._build_contact_update(data)
                contact_updates.append(
                    UpdateOne(
                        {"phone_number": phone},
                        contact_update,
                        upsert=True,
                    )
                )

            except Exception as e:
                result.error_count += 1
                result.errors.append(f"Prepare error: {str(e)}")

        # Execute SMS log operations
        if sms_operations:
            try:
                bulk_result = await sms_log_collection.bulk_write(
                    sms_operations, ordered=False
                )
                result.success_count = bulk_result.modified_count + bulk_result.upserted_count
                result.created_count = bulk_result.upserted_count
                result.updated_count = bulk_result.modified_count
            except Exception as e:
                result.error_count += len(sms_operations)
                result.errors.append(f"SMS log bulk write error: {str(e)}")

        # Execute contact updates
        if contact_updates:
            try:
                await contacts_collection.bulk_write(contact_updates, ordered=False)
            except Exception as e:
                result.errors.append(f"Contact update error: {str(e)}")

        result.complete()
        return result

    def _prepare_sms_record(self, record: DataRecord) -> dict[str, Any]:
        """Prepare SMS record for loading."""
        data = dict(record.data)

        sms = {
            "message_id": data.get("message_id"),
            "phone_number": data.get("phone_number"),
            "sender": data.get("sender"),
            "message": data.get("message"),
            "message_length": data.get("message_length", 0),
            "status": data.get("status", "unknown"),
            "status_code": data.get("status_code"),
            "delivered": data.get("delivered", False),
            "cost": data.get("cost"),
            "timestamp": data.get("timestamp"),
            "date": data.get("date"),
            "provider": data.get("provider", "unknown"),
            "template_id": data.get("template_id"),
            "template_name": data.get("template_name"),
            "campaign_id": data.get("campaign_id"),
            "_source_name": record.source_name,
            "_source_type": record.source_type,
            "_extracted_at": record.extracted_at.isoformat(),
            "_loaded_at": datetime.utcnow().isoformat(),
        }

        if self._tenant_id:
            sms["tenant_id"] = self._tenant_id

        return sms

    def _build_contact_update(self, sms_data: dict[str, Any]) -> dict[str, Any]:
        """Build contact update based on SMS outcome."""
        now = datetime.utcnow()
        phone = sms_data["phone_number"]

        # Base update
        update: dict[str, Any] = {
            "$set": {
                "updated_at": now,
            },
            "$setOnInsert": {
                "phone_number": phone,
                "created_at": now,
            },
            "$inc": {
                "sms_metrics.total_sent": 1,
            },
        }

        if self._tenant_id:
            update["$set"]["tenant_id"] = self._tenant_id

        # Update based on SMS outcome
        if sms_data.get("delivered"):
            update["$inc"]["sms_metrics.delivered"] = 1
            update["$set"]["current_stage"] = "sms_sent"
            update["$set"]["stage_history.sms_sent"] = now
            update["$set"]["last_sms_delivered"] = sms_data.get("timestamp")
        else:
            status = sms_data.get("status", "")
            if status in ("failed", "rejected", "blocked"):
                update["$inc"]["sms_metrics.failed"] = 1
            elif status in ("pending", "queued", "sent"):
                update["$inc"]["sms_metrics.pending"] = 1

        # Track last SMS
        update["$set"]["last_sms"] = sms_data.get("timestamp")
        update["$set"]["last_sms_template"] = sms_data.get("template_id")

        return update

    async def get_sms_stats_by_phone(self, phone_number: str) -> dict[str, Any]:
        """Get SMS statistics for a phone number."""
        if not self._connected:
            await self.connect()

        if not self._db:
            return {}

        collection = self._db["sms_logs"]

        pipeline = [
            {"$match": {"phone_number": phone_number}},
            {
                "$group": {
                    "_id": "$phone_number",
                    "total_sent": {"$sum": 1},
                    "delivered": {
                        "$sum": {"$cond": [{"$eq": ["$delivered", True]}, 1, 0]}
                    },
                    "failed": {
                        "$sum": {
                            "$cond": [
                                {"$in": ["$status", ["failed", "rejected", "blocked"]]},
                                1,
                                0,
                            ]
                        }
                    },
                    "total_cost": {"$sum": "$cost"},
                    "first_sms": {"$min": "$timestamp"},
                    "last_sms": {"$max": "$timestamp"},
                    "templates_used": {"$addToSet": "$template_id"},
                }
            },
            {
                "$project": {
                    "_id": 0,
                    "phone_number": "$_id",
                    "total_sent": 1,
                    "delivered": 1,
                    "failed": 1,
                    "total_cost": 1,
                    "first_sms": 1,
                    "last_sms": 1,
                    "templates_used": 1,
                    "delivery_rate": {
                        "$multiply": [
                            {"$divide": ["$delivered", "$total_sent"]},
                            100,
                        ]
                    },
                }
            },
        ]

        result = await collection.aggregate(pipeline).to_list(1)
        return result[0] if result else {}

    async def get_campaign_stats(
        self,
        campaign_id: str,
    ) -> dict[str, Any]:
        """Get SMS statistics for a campaign."""
        if not self._connected:
            await self.connect()

        if not self._db:
            return {}

        collection = self._db["sms_logs"]

        pipeline = [
            {"$match": {"campaign_id": campaign_id}},
            {
                "$group": {
                    "_id": "$campaign_id",
                    "total_sent": {"$sum": 1},
                    "delivered": {
                        "$sum": {"$cond": [{"$eq": ["$delivered", True]}, 1, 0]}
                    },
                    "failed": {
                        "$sum": {
                            "$cond": [
                                {"$in": ["$status", ["failed", "rejected", "blocked"]]},
                                1,
                                0,
                            ]
                        }
                    },
                    "pending": {
                        "$sum": {
                            "$cond": [
                                {"$in": ["$status", ["pending", "queued", "sent"]]},
                                1,
                                0,
                            ]
                        }
                    },
                    "total_cost": {"$sum": "$cost"},
                    "unique_recipients": {"$addToSet": "$phone_number"},
                    "templates_used": {"$addToSet": "$template_id"},
                }
            },
            {
                "$project": {
                    "_id": 0,
                    "campaign_id": "$_id",
                    "total_sent": 1,
                    "delivered": 1,
                    "failed": 1,
                    "pending": 1,
                    "total_cost": 1,
                    "unique_recipients": {"$size": "$unique_recipients"},
                    "templates_used": 1,
                    "delivery_rate": {
                        "$multiply": [
                            {"$divide": ["$delivered", "$total_sent"]},
                            100,
                        ]
                    },
                }
            },
        ]

        result = await collection.aggregate(pipeline).to_list(1)
        return result[0] if result else {}

    async def get_template_stats(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """Get SMS statistics grouped by template."""
        if not self._connected:
            await self.connect()

        if not self._db:
            return []

        collection = self._db["sms_logs"]

        match_query: dict[str, Any] = {}
        if start_date or end_date:
            match_query["timestamp"] = {}
            if start_date:
                match_query["timestamp"]["$gte"] = start_date.isoformat()
            if end_date:
                match_query["timestamp"]["$lte"] = end_date.isoformat()

        pipeline = [
            {"$match": match_query} if match_query else {"$match": {}},
            {
                "$group": {
                    "_id": "$template_id",
                    "template_name": {"$first": "$template_name"},
                    "total_sent": {"$sum": 1},
                    "delivered": {
                        "$sum": {"$cond": [{"$eq": ["$delivered", True]}, 1, 0]}
                    },
                    "failed": {
                        "$sum": {
                            "$cond": [
                                {"$in": ["$status", ["failed", "rejected", "blocked"]]},
                                1,
                                0,
                            ]
                        }
                    },
                    "total_cost": {"$sum": "$cost"},
                }
            },
            {
                "$project": {
                    "_id": 0,
                    "template_id": "$_id",
                    "template_name": 1,
                    "total_sent": 1,
                    "delivered": 1,
                    "failed": 1,
                    "total_cost": 1,
                    "delivery_rate": {
                        "$multiply": [
                            {"$divide": ["$delivered", "$total_sent"]},
                            100,
                        ]
                    },
                }
            },
            {"$sort": {"total_sent": -1}},
        ]

        return await collection.aggregate(pipeline).to_list(100)

