"""
Call Log Loader

Specialized loader for call log data with funnel stage updates.
"""

from datetime import datetime
from typing import Any

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo import UpdateOne

from src.core.interfaces import DataRecord

from .base import BaseLoader, LoaderRegistry, LoadResult


@LoaderRegistry.register("call_log")
class CallLogLoader(BaseLoader):
    """
    Loader for call log data.
    Stores call records and updates contact funnel stages.
    """

    # Minimum duration for successful call (1.5 minutes)
    SUCCESSFUL_CALL_THRESHOLD = 90

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
        """Load call logs and update contact stages."""
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

        call_log_collection = self._db[target]
        contacts_collection = self._db["contacts"]

        call_operations = []
        contact_updates = []

        for record in records:
            try:
                data = self._prepare_call_record(record)
                phone = data.get("phone_number")

                if not phone:
                    result.error_count += 1
                    result.errors.append("Record missing phone number")
                    continue

                # Create unique ID for call
                call_id = data.get("call_id") or f"{phone}_{data.get('timestamp', '')}"

                # Add call log
                if upsert:
                    call_operations.append(
                        UpdateOne(
                            {"call_id": call_id},
                            {"$set": data},
                            upsert=True,
                        )
                    )
                else:
                    call_operations.append(
                        UpdateOne(
                            {"call_id": call_id},
                            {"$setOnInsert": data},
                            upsert=True,
                        )
                    )

                # Update contact stage based on call outcome
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

        # Execute call log operations
        if call_operations:
            try:
                bulk_result = await call_log_collection.bulk_write(
                    call_operations, ordered=False
                )
                result.success_count = bulk_result.modified_count + bulk_result.upserted_count
                result.created_count = bulk_result.upserted_count
                result.updated_count = bulk_result.modified_count
            except Exception as e:
                result.error_count += len(call_operations)
                result.errors.append(f"Call log bulk write error: {str(e)}")

        # Execute contact updates
        if contact_updates:
            try:
                await contacts_collection.bulk_write(contact_updates, ordered=False)
            except Exception as e:
                result.errors.append(f"Contact update error: {str(e)}")

        result.complete()
        return result

    def _prepare_call_record(self, record: DataRecord) -> dict[str, Any]:
        """Prepare call record for loading."""
        data = dict(record.data)

        call = {
            "call_id": data.get("call_id"),
            "phone_number": data.get("phone_number"),
            "direction": data.get("direction", "unknown"),
            "duration_seconds": data.get("duration_seconds", 0),
            "answered": data.get("answered", False),
            "successful": data.get("successful", False),
            "timestamp": data.get("timestamp"),
            "date": data.get("date"),
            "salesperson": data.get("salesperson"),
            "disposition": data.get("disposition"),
            "extension": data.get("extension"),
            "_source_name": record.source_name,
            "_source_type": record.source_type,
            "_extracted_at": record.extracted_at.isoformat(),
            "_loaded_at": datetime.utcnow().isoformat(),
        }

        if self._tenant_id:
            call["tenant_id"] = self._tenant_id

        return call

    def _build_contact_update(self, call_data: dict[str, Any]) -> dict[str, Any]:
        """Build contact update based on call outcome."""
        now = datetime.utcnow()
        phone = call_data["phone_number"]

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
                "call_metrics.total_calls": 1,
            },
        }

        if self._tenant_id:
            update["$set"]["tenant_id"] = self._tenant_id

        # Update based on call outcome
        if call_data.get("answered"):
            update["$inc"]["call_metrics.answered_calls"] = 1

            if call_data.get("successful"):
                # Successful call (1.5+ minutes)
                update["$inc"]["call_metrics.successful_calls"] = 1
                update["$set"]["current_stage"] = "called"
                update["$set"]["stage_history.called"] = now
                update["$set"]["last_successful_call"] = call_data.get("timestamp")
            else:
                update["$set"]["last_answered_call"] = call_data.get("timestamp")
        else:
            update["$inc"]["call_metrics.missed_calls"] = 1

        # Track last call
        update["$set"]["last_call"] = call_data.get("timestamp")
        update["$set"]["last_call_salesperson"] = call_data.get("salesperson")

        return update

    async def get_call_stats_by_phone(self, phone_number: str) -> dict[str, Any]:
        """Get call statistics for a phone number."""
        if not self._connected:
            await self.connect()

        if not self._db:
            return {}

        collection = self._db["call_logs"]

        pipeline = [
            {"$match": {"phone_number": phone_number}},
            {
                "$group": {
                    "_id": "$phone_number",
                    "total_calls": {"$sum": 1},
                    "answered_calls": {
                        "$sum": {"$cond": [{"$eq": ["$answered", True]}, 1, 0]}
                    },
                    "successful_calls": {
                        "$sum": {"$cond": [{"$eq": ["$successful", True]}, 1, 0]}
                    },
                    "total_duration": {"$sum": "$duration_seconds"},
                    "avg_duration": {"$avg": "$duration_seconds"},
                    "first_call": {"$min": "$timestamp"},
                    "last_call": {"$max": "$timestamp"},
                }
            },
        ]

        result = await collection.aggregate(pipeline).to_list(1)
        return result[0] if result else {}

    async def get_salesperson_stats(
        self,
        salesperson: str,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> dict[str, Any]:
        """Get call statistics for a salesperson."""
        if not self._connected:
            await self.connect()

        if not self._db:
            return {}

        collection = self._db["call_logs"]

        match_query: dict[str, Any] = {"salesperson": salesperson}
        if start_date or end_date:
            match_query["timestamp"] = {}
            if start_date:
                match_query["timestamp"]["$gte"] = start_date.isoformat()
            if end_date:
                match_query["timestamp"]["$lte"] = end_date.isoformat()

        pipeline = [
            {"$match": match_query},
            {
                "$group": {
                    "_id": "$salesperson",
                    "total_calls": {"$sum": 1},
                    "answered_calls": {
                        "$sum": {"$cond": [{"$eq": ["$answered", True]}, 1, 0]}
                    },
                    "successful_calls": {
                        "$sum": {"$cond": [{"$eq": ["$successful", True]}, 1, 0]}
                    },
                    "unique_contacts": {"$addToSet": "$phone_number"},
                    "total_duration": {"$sum": "$duration_seconds"},
                }
            },
            {
                "$project": {
                    "_id": 0,
                    "salesperson": "$_id",
                    "total_calls": 1,
                    "answered_calls": 1,
                    "successful_calls": 1,
                    "unique_contacts": {"$size": "$unique_contacts"},
                    "total_duration": 1,
                    "answer_rate": {
                        "$multiply": [
                            {"$divide": ["$answered_calls", "$total_calls"]},
                            100,
                        ]
                    },
                    "success_rate": {
                        "$multiply": [
                            {"$divide": ["$successful_calls", "$total_calls"]},
                            100,
                        ]
                    },
                }
            },
        ]

        result = await collection.aggregate(pipeline).to_list(1)
        return result[0] if result else {}

