"""
Invoice Loader

Specialized loader for invoice and payment data with funnel stage updates.
"""

from datetime import datetime
from typing import Any

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo import UpdateOne

from src.core.interfaces import DataRecord

from .base import BaseLoader, LoaderRegistry, LoadResult


@LoaderRegistry.register("invoice")
class InvoiceLoader(BaseLoader):
    """
    Loader for invoice/pre-invoice data.
    Stores invoice records and updates contact funnel stages.
    """

    # High value threshold (1B Rials)
    HIGH_VALUE_THRESHOLD = 1_000_000_000

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
        """Load invoices and update contact stages."""
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

        invoice_collection = self._db[target]
        contacts_collection = self._db["contacts"]

        invoice_operations = []
        contact_updates = []

        for record in records:
            try:
                data = self._prepare_invoice_record(record)
                phone = data.get("phone_number")
                invoice_id = data.get("invoice_id")

                if not invoice_id:
                    result.error_count += 1
                    result.errors.append("Record missing invoice ID")
                    continue

                # Add invoice
                if upsert:
                    invoice_operations.append(
                        UpdateOne(
                            {"invoice_id": invoice_id},
                            {"$set": data},
                            upsert=True,
                        )
                    )
                else:
                    invoice_operations.append(
                        UpdateOne(
                            {"invoice_id": invoice_id},
                            {"$setOnInsert": data},
                            upsert=True,
                        )
                    )

                # Update contact stage if phone is available
                if phone:
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

        # Execute invoice operations
        if invoice_operations:
            try:
                bulk_result = await invoice_collection.bulk_write(
                    invoice_operations, ordered=False
                )
                result.success_count = bulk_result.modified_count + bulk_result.upserted_count
                result.created_count = bulk_result.upserted_count
                result.updated_count = bulk_result.modified_count
            except Exception as e:
                result.error_count += len(invoice_operations)
                result.errors.append(f"Invoice bulk write error: {str(e)}")

        # Execute contact updates
        if contact_updates:
            try:
                await contacts_collection.bulk_write(contact_updates, ordered=False)
            except Exception as e:
                result.errors.append(f"Contact update error: {str(e)}")

        result.complete()
        return result

    def _prepare_invoice_record(self, record: DataRecord) -> dict[str, Any]:
        """Prepare invoice record for loading."""
        data = dict(record.data)

        invoice = {
            "invoice_id": data.get("invoice_id"),
            "phone_number": data.get("phone_number"),
            "customer_name": data.get("customer_name"),
            "total_amount": data.get("total_amount", 0),
            "amount_formatted": data.get("amount_formatted"),
            "is_high_value": data.get("is_high_value", False),
            "status": data.get("status", "draft"),
            "item_count": data.get("item_count", 0),
            "product_categories": data.get("product_categories", []),
            "salesperson": data.get("salesperson"),
            "created_at": data.get("created_at"),
            "date": data.get("date"),
            "_source_name": record.source_name,
            "_source_type": record.source_type,
            "_extracted_at": record.extracted_at.isoformat(),
            "_loaded_at": datetime.utcnow().isoformat(),
        }

        if self._tenant_id:
            invoice["tenant_id"] = self._tenant_id

        return invoice

    def _build_contact_update(self, invoice_data: dict[str, Any]) -> dict[str, Any]:
        """Build contact update based on invoice."""
        now = datetime.utcnow()
        phone = invoice_data["phone_number"]
        status = invoice_data.get("status", "draft")
        amount = invoice_data.get("total_amount", 0)

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
                "invoice_metrics.total_invoices": 1,
            },
        }

        if self._tenant_id:
            update["$set"]["tenant_id"] = self._tenant_id

        # Update stage based on invoice status
        if status == "paid":
            update["$set"]["current_stage"] = "converted"
            update["$set"]["stage_history.converted"] = now
            update["$set"]["is_customer"] = True
            update["$inc"]["invoice_metrics.paid_invoices"] = 1
            update["$inc"]["invoice_metrics.total_revenue"] = amount
        elif status in ("sent", "pending"):
            update["$set"]["current_stage"] = "invoice_sent"
            update["$set"]["stage_history.invoice_sent"] = now
            update["$inc"]["invoice_metrics.pending_invoices"] = 1
            update["$inc"]["invoice_metrics.pending_amount"] = amount

        # Track invoice value
        if amount >= self.HIGH_VALUE_THRESHOLD:
            update["$set"]["is_high_value"] = True

        # Track last invoice
        update["$set"]["last_invoice"] = invoice_data.get("created_at")
        update["$set"]["last_invoice_id"] = invoice_data.get("invoice_id")
        update["$set"]["last_invoice_amount"] = amount

        # Add to product categories
        categories = invoice_data.get("product_categories", [])
        if categories:
            update["$addToSet"] = {
                "interested_categories": {"$each": categories}
            }

        return update

    async def get_invoice_stats_by_phone(self, phone_number: str) -> dict[str, Any]:
        """Get invoice statistics for a phone number."""
        if not self._connected:
            await self.connect()

        if not self._db:
            return {}

        collection = self._db["invoices"]

        pipeline = [
            {"$match": {"phone_number": phone_number}},
            {
                "$group": {
                    "_id": "$phone_number",
                    "total_invoices": {"$sum": 1},
                    "paid_invoices": {
                        "$sum": {"$cond": [{"$eq": ["$status", "paid"]}, 1, 0]}
                    },
                    "pending_invoices": {
                        "$sum": {
                            "$cond": [
                                {"$in": ["$status", ["sent", "pending"]]},
                                1,
                                0,
                            ]
                        }
                    },
                    "total_amount": {"$sum": "$total_amount"},
                    "paid_amount": {
                        "$sum": {
                            "$cond": [
                                {"$eq": ["$status", "paid"]},
                                "$total_amount",
                                0,
                            ]
                        }
                    },
                    "first_invoice": {"$min": "$created_at"},
                    "last_invoice": {"$max": "$created_at"},
                    "product_categories": {"$addToSet": "$product_categories"},
                }
            },
            {
                "$project": {
                    "_id": 0,
                    "phone_number": "$_id",
                    "total_invoices": 1,
                    "paid_invoices": 1,
                    "pending_invoices": 1,
                    "total_amount": 1,
                    "paid_amount": 1,
                    "first_invoice": 1,
                    "last_invoice": 1,
                    "product_categories": {
                        "$reduce": {
                            "input": "$product_categories",
                            "initialValue": [],
                            "in": {"$setUnion": ["$$value", "$$this"]},
                        }
                    },
                    "conversion_rate": {
                        "$multiply": [
                            {"$divide": ["$paid_invoices", "$total_invoices"]},
                            100,
                        ]
                    },
                }
            },
        ]

        result = await collection.aggregate(pipeline).to_list(1)
        return result[0] if result else {}

    async def get_salesperson_revenue(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """Get revenue statistics grouped by salesperson."""
        if not self._connected:
            await self.connect()

        if not self._db:
            return []

        collection = self._db["invoices"]

        match_query: dict[str, Any] = {"status": "paid"}
        if start_date or end_date:
            match_query["created_at"] = {}
            if start_date:
                match_query["created_at"]["$gte"] = start_date.isoformat()
            if end_date:
                match_query["created_at"]["$lte"] = end_date.isoformat()

        pipeline = [
            {"$match": match_query},
            {
                "$group": {
                    "_id": "$salesperson",
                    "total_invoices": {"$sum": 1},
                    "total_revenue": {"$sum": "$total_amount"},
                    "avg_invoice_value": {"$avg": "$total_amount"},
                    "unique_customers": {"$addToSet": "$phone_number"},
                    "high_value_count": {
                        "$sum": {"$cond": [{"$eq": ["$is_high_value", True]}, 1, 0]}
                    },
                }
            },
            {
                "$project": {
                    "_id": 0,
                    "salesperson": "$_id",
                    "total_invoices": 1,
                    "total_revenue": 1,
                    "avg_invoice_value": 1,
                    "unique_customers": {"$size": "$unique_customers"},
                    "high_value_count": 1,
                }
            },
            {"$sort": {"total_revenue": -1}},
        ]

        return await collection.aggregate(pipeline).to_list(100)


@LoaderRegistry.register("payment")
class PaymentLoader(BaseLoader):
    """
    Loader for payment data.
    Stores payment records and updates contact/invoice status.
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
        """Load payments and update related records."""
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

        payment_collection = self._db[target]
        invoice_collection = self._db["invoices"]
        contacts_collection = self._db["contacts"]

        payment_operations = []
        invoice_updates = []
        contact_updates = []

        for record in records:
            try:
                data = self._prepare_payment_record(record)
                payment_id = data.get("payment_id")
                invoice_id = data.get("invoice_id")
                phone = data.get("phone_number")

                if not payment_id:
                    result.error_count += 1
                    result.errors.append("Record missing payment ID")
                    continue

                # Add payment
                payment_operations.append(
                    UpdateOne(
                        {"payment_id": payment_id},
                        {"$set": data},
                        upsert=True,
                    )
                )

                # Update invoice status if successful payment
                if invoice_id and data.get("is_successful"):
                    invoice_updates.append(
                        UpdateOne(
                            {"invoice_id": invoice_id},
                            {
                                "$set": {
                                    "status": "paid",
                                    "paid_at": data.get("paid_at"),
                                    "payment_id": payment_id,
                                    "updated_at": datetime.utcnow(),
                                }
                            },
                        )
                    )

                # Update contact
                if phone:
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

        # Execute payment operations
        if payment_operations:
            try:
                bulk_result = await payment_collection.bulk_write(
                    payment_operations, ordered=False
                )
                result.success_count = bulk_result.modified_count + bulk_result.upserted_count
                result.created_count = bulk_result.upserted_count
                result.updated_count = bulk_result.modified_count
            except Exception as e:
                result.error_count += len(payment_operations)
                result.errors.append(f"Payment bulk write error: {str(e)}")

        # Execute invoice updates
        if invoice_updates:
            try:
                await invoice_collection.bulk_write(invoice_updates, ordered=False)
            except Exception as e:
                result.errors.append(f"Invoice update error: {str(e)}")

        # Execute contact updates
        if contact_updates:
            try:
                await contacts_collection.bulk_write(contact_updates, ordered=False)
            except Exception as e:
                result.errors.append(f"Contact update error: {str(e)}")

        result.complete()
        return result

    def _prepare_payment_record(self, record: DataRecord) -> dict[str, Any]:
        """Prepare payment record for loading."""
        data = dict(record.data)

        payment = {
            "payment_id": data.get("payment_id"),
            "invoice_id": data.get("invoice_id"),
            "phone_number": data.get("phone_number"),
            "amount": data.get("amount", 0),
            "amount_formatted": data.get("amount_formatted"),
            "is_high_value": data.get("is_high_value", False),
            "payment_method": data.get("payment_method", "unknown"),
            "status": data.get("status", "unknown"),
            "is_successful": data.get("is_successful", False),
            "paid_at": data.get("paid_at"),
            "date": data.get("date"),
            "transaction_id": data.get("transaction_id"),
            "_source_name": record.source_name,
            "_source_type": record.source_type,
            "_extracted_at": record.extracted_at.isoformat(),
            "_loaded_at": datetime.utcnow().isoformat(),
        }

        if self._tenant_id:
            payment["tenant_id"] = self._tenant_id

        return payment

    def _build_contact_update(self, payment_data: dict[str, Any]) -> dict[str, Any]:
        """Build contact update based on payment."""
        now = datetime.utcnow()
        phone = payment_data["phone_number"]
        amount = payment_data.get("amount", 0)

        update: dict[str, Any] = {
            "$set": {
                "updated_at": now,
            },
            "$setOnInsert": {
                "phone_number": phone,
                "created_at": now,
            },
        }

        if self._tenant_id:
            update["$set"]["tenant_id"] = self._tenant_id

        if payment_data.get("is_successful"):
            update["$set"]["current_stage"] = "converted"
            update["$set"]["stage_history.converted"] = now
            update["$set"]["is_customer"] = True
            update["$set"]["last_payment"] = payment_data.get("paid_at")
            update["$set"]["last_payment_amount"] = amount
            update["$inc"] = {
                "payment_metrics.total_payments": 1,
                "payment_metrics.total_paid": amount,
            }

        return update

