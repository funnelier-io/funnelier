"""
MongoDB Extractor

Extracts data from MongoDB databases, supporting:
- Pre-invoices and payments
- Custom queries
- Aggregation pipelines
- Change streams for real-time updates
"""

from datetime import datetime
from typing import Any, AsyncIterator

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection

from src.core.utils import normalize_phone_strict

from src.core.interfaces import DataRecord, DatabaseSourceConfig

from .base import BaseExtractor, ExtractorRegistry


@ExtractorRegistry.register("mongodb")
class MongoDBExtractor(BaseExtractor):
    """
    Extractor for MongoDB databases.
    Primary use case: Extracting pre-invoices and payment data.
    """

    def __init__(self, config: DatabaseSourceConfig, tenant_id: str | None = None):
        super().__init__(config, tenant_id)
        self._db_config: DatabaseSourceConfig = config
        self._client: AsyncIOMotorClient | None = None
        self._collection: AsyncIOMotorCollection | None = None

    @property
    def source_type(self) -> str:
        return "mongodb"

    async def connect(self) -> bool:
        """Connect to MongoDB."""
        try:
            self._client = AsyncIOMotorClient(self._db_config.connection_string)
            # Verify connection
            await self._client.admin.command("ping")

            if self._db_config.database_name:
                db = self._client[self._db_config.database_name]
                if self._db_config.collection_or_table:
                    self._collection = db[self._db_config.collection_or_table]

            self._connected = True
            return True
        except Exception:
            self._connected = False
            return False

    async def disconnect(self) -> None:
        """Close MongoDB connection."""
        if self._client:
            self._client.close()
        self._client = None
        self._collection = None
        self._connected = False

    async def test_connection(self) -> tuple[bool, str]:
        """Test MongoDB connection."""
        try:
            if not self._client:
                success = await self.connect()
                if not success:
                    return False, "Failed to connect to MongoDB"

            # Test ping
            await self._client.admin.command("ping")

            # Verify database exists
            if self._db_config.database_name:
                db_list = await self._client.list_database_names()
                if self._db_config.database_name not in db_list:
                    return False, f"Database not found: {self._db_config.database_name}"

            return True, "Successfully connected to MongoDB"
        except Exception as e:
            return False, f"Connection error: {str(e)}"

    async def extract(
        self,
        batch_size: int = 1000,
        **kwargs: Any,
    ) -> AsyncIterator[list[DataRecord]]:
        """Extract records from MongoDB in batches."""
        if not self._connected:
            await self.connect()

        if not self._collection:
            return

        query = kwargs.get("query") or {}
        if self._db_config.query:
            # Parse query string as dict if provided
            import json

            try:
                query = json.loads(self._db_config.query)
            except json.JSONDecodeError:
                pass

        projection = kwargs.get("projection")
        sort = kwargs.get("sort")

        cursor = self._collection.find(query, projection)
        if sort:
            cursor = cursor.sort(sort)

        batch: list[DataRecord] = []
        async for doc in cursor:
            # Convert ObjectId to string
            if "_id" in doc:
                doc["_id"] = str(doc["_id"])

            record = self._create_record(
                data=self._serialize_doc(doc),
                raw_data=doc,
            )
            batch.append(record)

            if len(batch) >= batch_size:
                yield batch
                batch = []

        if batch:
            yield batch

    async def extract_with_pipeline(
        self,
        pipeline: list[dict[str, Any]],
        batch_size: int = 1000,
    ) -> AsyncIterator[list[DataRecord]]:
        """Extract records using aggregation pipeline."""
        if not self._connected:
            await self.connect()

        if not self._collection:
            return

        cursor = self._collection.aggregate(pipeline)

        batch: list[DataRecord] = []
        async for doc in cursor:
            if "_id" in doc:
                doc["_id"] = str(doc["_id"])

            record = self._create_record(
                data=self._serialize_doc(doc),
                raw_data=doc,
            )
            batch.append(record)

            if len(batch) >= batch_size:
                yield batch
                batch = []

        if batch:
            yield batch

    async def watch_changes(
        self,
        pipeline: list[dict[str, Any]] | None = None,
    ) -> AsyncIterator[DataRecord]:
        """
        Watch for real-time changes using change streams.
        Useful for real-time dashboard updates.
        """
        if not self._connected:
            await self.connect()

        if not self._collection:
            return

        async with self._collection.watch(pipeline) as stream:
            async for change in stream:
                # Normalize change event
                data = {
                    "operation_type": change.get("operationType"),
                    "document": self._serialize_doc(change.get("fullDocument", {})),
                    "document_key": str(change.get("documentKey", {}).get("_id")),
                    "timestamp": change.get("clusterTime"),
                    "update_description": change.get("updateDescription"),
                }
                yield self._create_record(data, raw_data=change)

    def _serialize_doc(self, doc: dict[str, Any]) -> dict[str, Any]:
        """Serialize MongoDB document to JSON-compatible format."""
        result = {}
        for key, value in doc.items():
            if isinstance(value, datetime):
                result[key] = value.isoformat()
            elif hasattr(value, "__str__") and not isinstance(
                value, (str, int, float, bool, list, dict, type(None))
            ):
                result[key] = str(value)
            elif isinstance(value, dict):
                result[key] = self._serialize_doc(value)
            elif isinstance(value, list):
                result[key] = [
                    self._serialize_doc(item) if isinstance(item, dict) else item
                    for item in value
                ]
            else:
                result[key] = value
        return result

    async def get_schema(self) -> dict[str, Any]:
        """Infer schema from sample documents."""
        if not self._connected:
            await self.connect()

        if not self._collection:
            return {}

        # Sample a few documents to infer schema
        sample_docs = await self._collection.find().limit(10).to_list(10)

        if not sample_docs:
            return {"fields": []}

        # Collect all unique fields
        fields = set()
        for doc in sample_docs:
            fields.update(doc.keys())

        # Get collection stats
        stats = await self._collection.estimated_document_count()

        return {
            "fields": list(fields),
            "sample_count": len(sample_docs),
            "estimated_total": stats,
            "database": self._db_config.database_name,
            "collection": self._db_config.collection_or_table,
        }

    async def get_record_count(self) -> int | None:
        """Get document count in collection."""
        if not self._connected:
            await self.connect()

        if not self._collection:
            return None

        return await self._collection.estimated_document_count()


class InvoiceExtractor(MongoDBExtractor):
    """
    Specialized extractor for pre-invoice data.
    Normalizes invoice data to standard format.
    """

    async def extract(
        self,
        batch_size: int = 1000,
        **kwargs: Any,
    ) -> AsyncIterator[list[DataRecord]]:
        """Extract and normalize invoice records."""
        async for batch in super().extract(batch_size, **kwargs):
            normalized_batch = []
            for record in batch:
                normalized = self._normalize_invoice(record.data)
                normalized_batch.append(
                    self._create_record(normalized, record.raw_data)
                )
            yield normalized_batch

    def _normalize_invoice(self, data: dict[str, Any]) -> dict[str, Any]:
        """Normalize invoice record to standard format."""
        # Map common field variations
        return {
            "invoice_id": data.get("_id") or data.get("invoice_id"),
            "phone_number": self._normalize_phone(
                data.get("phone") or data.get("customer_phone") or data.get("mobile")
            ),
            "customer_name": data.get("customer_name") or data.get("name"),
            "total_amount": self._parse_amount(data.get("total") or data.get("amount")),
            "status": data.get("status"),
            "items": data.get("items", []),
            "created_at": data.get("created_at") or data.get("createdAt"),
            "updated_at": data.get("updated_at") or data.get("updatedAt"),
            "salesperson": data.get("salesperson") or data.get("sales_rep"),
            "raw_data": data,
        }

    def _normalize_phone(self, phone: str | None) -> str | None:
        """Normalize phone number."""
        if not phone:
            return None
        return normalize_phone_strict(str(phone))

    def _parse_amount(self, amount: Any) -> float:
        """Parse amount to float."""
        if amount is None:
            return 0.0
        if isinstance(amount, (int, float)):
            return float(amount)
        try:
            # Remove currency symbols and separators
            clean = "".join(c for c in str(amount) if c.isdigit() or c == ".")
            return float(clean) if clean else 0.0
        except ValueError:
            return 0.0


class PaymentExtractor(MongoDBExtractor):
    """
    Specialized extractor for payment data.
    Normalizes payment records to standard format.
    """

    async def extract(
        self,
        batch_size: int = 1000,
        **kwargs: Any,
    ) -> AsyncIterator[list[DataRecord]]:
        """Extract and normalize payment records."""
        async for batch in super().extract(batch_size, **kwargs):
            normalized_batch = []
            for record in batch:
                normalized = self._normalize_payment(record.data)
                normalized_batch.append(
                    self._create_record(normalized, record.raw_data)
                )
            yield normalized_batch

    def _normalize_payment(self, data: dict[str, Any]) -> dict[str, Any]:
        """Normalize payment record to standard format."""
        return {
            "payment_id": data.get("_id") or data.get("payment_id"),
            "invoice_id": data.get("invoice_id") or data.get("invoiceId"),
            "phone_number": self._normalize_phone(
                data.get("phone") or data.get("customer_phone")
            ),
            "amount": self._parse_amount(data.get("amount")),
            "payment_method": data.get("method") or data.get("payment_method"),
            "status": data.get("status"),
            "paid_at": data.get("paid_at") or data.get("paidAt"),
            "transaction_id": data.get("transaction_id") or data.get("ref"),
            "raw_data": data,
        }

    def _normalize_phone(self, phone: str | None) -> str | None:
        """Normalize phone number."""
        if not phone:
            return None
        return normalize_phone_strict(str(phone))

    def _parse_amount(self, amount: Any) -> float:
        """Parse amount to float."""
        if amount is None:
            return 0.0
        if isinstance(amount, (int, float)):
            return float(amount)
        try:
            clean = "".join(c for c in str(amount) if c.isdigit() or c == ".")
            return float(clean) if clean else 0.0
        except ValueError:
            return 0.0

