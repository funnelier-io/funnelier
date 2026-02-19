"""
ETL Connectors - MongoDB Connector
For connecting to tenant MongoDB databases (invoices, payments, etc.)
"""

from datetime import datetime
from typing import Any, AsyncIterator

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from src.core.interfaces import (
    DataRecord,
    DatabaseSourceConfig,
    IDatabaseConnector,
)


class MongoDBConnector(IDatabaseConnector):
    """
    Connector for MongoDB data sources.
    Used for pulling invoice and payment data from tenant systems.
    """

    def __init__(self, config: DatabaseSourceConfig):
        self._config = config
        self._client: AsyncIOMotorClient | None = None
        self._db: AsyncIOMotorDatabase | None = None

    @property
    def source_type(self) -> str:
        return "mongodb"

    @property
    def config(self) -> DatabaseSourceConfig:
        return self._config

    async def connect(self) -> bool:
        """Establish connection to MongoDB."""
        try:
            self._client = AsyncIOMotorClient(self._config.connection_string)

            # Use specified database or default
            db_name = self._config.database_name or "default"
            self._db = self._client[db_name]

            # Test connection
            await self._client.admin.command("ping")
            return True
        except Exception:
            return False

    async def disconnect(self) -> None:
        """Close MongoDB connection."""
        if self._client:
            self._client.close()
            self._client = None
            self._db = None

    async def test_connection(self) -> tuple[bool, str]:
        """Test MongoDB connection."""
        try:
            if not self._client:
                await self.connect()

            await self._client.admin.command("ping")

            # Get collection names
            collections = await self._db.list_collection_names()
            return True, f"Connected. Collections: {', '.join(collections[:10])}"
        except Exception as e:
            return False, f"Connection failed: {str(e)}"

    async def extract(
        self,
        batch_size: int = 1000,
        **kwargs: Any,
    ) -> AsyncIterator[list[DataRecord]]:
        """
        Extract data from MongoDB in batches.
        """
        if not self._db:
            await self.connect()

        collection_name = self._config.collection_or_table
        if not collection_name:
            raise ValueError("Collection name not specified")

        collection = self._db[collection_name]

        # Build query from config or kwargs
        query = kwargs.get("query", {})
        if self._config.query:
            # Parse query string as dict if provided
            import json
            query = json.loads(self._config.query)

        # Use cursor for batch processing
        cursor = collection.find(query).batch_size(batch_size)

        batch = []
        async for doc in cursor:
            # Convert ObjectId to string
            if "_id" in doc:
                doc["_id"] = str(doc["_id"])

            record = DataRecord(
                data=doc,
                source_name=self._config.name,
                source_type=self.source_type,
                extracted_at=datetime.utcnow(),
                raw_data=doc,
            )
            batch.append(record)

            if len(batch) >= batch_size:
                yield batch
                batch = []

        if batch:
            yield batch

    async def execute_query(
        self,
        query: str,
        params: dict[str, Any] | None = None,
    ) -> list[DataRecord]:
        """Execute a MongoDB query."""
        if not self._db:
            await self.connect()

        import json
        query_dict = json.loads(query)

        collection_name = self._config.collection_or_table
        if not collection_name:
            raise ValueError("Collection name not specified")

        collection = self._db[collection_name]

        records = []
        async for doc in collection.find(query_dict):
            if "_id" in doc:
                doc["_id"] = str(doc["_id"])

            record = DataRecord(
                data=doc,
                source_name=self._config.name,
                source_type=self.source_type,
                extracted_at=datetime.utcnow(),
            )
            records.append(record)

        return records

    async def get_tables(self) -> list[str]:
        """Get list of collections."""
        if not self._db:
            await self.connect()

        return await self._db.list_collection_names()

    async def get_schema(self) -> dict[str, Any]:
        """Infer schema from MongoDB collection."""
        if not self._db:
            await self.connect()

        collection_name = self._config.collection_or_table
        if not collection_name:
            return {"error": "Collection name not specified"}

        collection = self._db[collection_name]

        try:
            # Sample documents to infer schema
            sample = await collection.find().limit(100).to_list(100)

            if not sample:
                return {"fields": [], "sample_count": 0}

            # Collect all field names and types
            all_fields = set()
            field_types = {}
            field_samples = {}

            for doc in sample:
                for key, value in doc.items():
                    all_fields.add(key)

                    value_type = type(value).__name__
                    if key not in field_types:
                        field_types[key] = set()
                    field_types[key].add(value_type)

                    if key not in field_samples:
                        field_samples[key] = []
                    if len(field_samples[key]) < 3 and value is not None:
                        # Convert ObjectId to string for display
                        if hasattr(value, '__str__'):
                            field_samples[key].append(str(value)[:100])

            return {
                "collection": collection_name,
                "fields": list(all_fields),
                "field_types": {k: list(v) for k, v in field_types.items()},
                "sample_values": field_samples,
                "sample_count": len(sample),
            }

        except Exception as e:
            return {"error": str(e)}

    async def get_record_count(self) -> int | None:
        """Get total document count in collection."""
        if not self._db:
            await self.connect()

        collection_name = self._config.collection_or_table
        if not collection_name:
            return None

        try:
            return await self._db[collection_name].count_documents({})
        except Exception:
            return None


class InvoiceMongoTransformer:
    """
    Transformer for invoice data from MongoDB.
    """

    def transform_invoice(
        self,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        """Transform invoice document to standardized format."""
        transformed = {
            "external_id": data.get("_id"),
            "invoice_number": data.get("invoice_number") or data.get("number"),
            "phone_number": self._extract_phone(data),
            "customer_name": data.get("customer_name") or data.get("customer", {}).get("name"),
            "total_amount": self._extract_amount(data),
            "status": self._map_status(data.get("status")),
            "issued_at": self._parse_date(data.get("created_at") or data.get("date")),
            "paid_at": self._parse_date(data.get("paid_at") or data.get("payment_date")),
        }

        # Extract line items if present
        items = data.get("items") or data.get("line_items") or []
        transformed["line_items"] = [
            {
                "product_name": item.get("name") or item.get("product_name"),
                "quantity": item.get("quantity", 1),
                "unit_price": item.get("price") or item.get("unit_price", 0),
                "total_price": item.get("total") or item.get("total_price", 0),
            }
            for item in items
        ]

        return transformed

    def _extract_phone(self, data: dict) -> str | None:
        """Extract phone number from various locations."""
        # Try direct phone field
        phone = data.get("phone") or data.get("phone_number") or data.get("mobile")

        # Try nested customer object
        if not phone:
            customer = data.get("customer", {})
            if isinstance(customer, dict):
                phone = customer.get("phone") or customer.get("mobile")

        if phone:
            # Clean phone number
            phone_clean = "".join(filter(str.isdigit, str(phone)))
            if phone_clean.startswith("98") and len(phone_clean) == 12:
                phone_clean = phone_clean[2:]
            elif phone_clean.startswith("0") and len(phone_clean) == 11:
                phone_clean = phone_clean[1:]
            return phone_clean

        return None

    def _extract_amount(self, data: dict) -> int:
        """Extract total amount from various fields."""
        amount = (
            data.get("total_amount")
            or data.get("total")
            or data.get("amount")
            or data.get("grand_total")
            or 0
        )
        try:
            return int(amount)
        except (ValueError, TypeError):
            return 0

    def _map_status(self, status: Any) -> str:
        """Map invoice status to standardized values."""
        if status is None:
            return "draft"

        status_str = str(status).lower()
        mappings = {
            "paid": "paid",
            "پرداخت شده": "paid",
            "تسویه": "paid",
            "pending": "issued",
            "issued": "issued",
            "صادر شده": "issued",
            "draft": "draft",
            "پیش‌فاکتور": "draft",
            "cancelled": "cancelled",
            "canceled": "cancelled",
            "لغو": "cancelled",
            "partial": "partial_paid",
        }
        return mappings.get(status_str, "draft")

    def _parse_date(self, date_value: Any) -> datetime | None:
        """Parse date from various formats."""
        if date_value is None:
            return None

        if isinstance(date_value, datetime):
            return date_value

        if isinstance(date_value, str):
            for fmt in [
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%dT%H:%M:%SZ",
                "%Y-%m-%d",
                "%d/%m/%Y",
            ]:
                try:
                    return datetime.strptime(date_value, fmt)
                except ValueError:
                    continue

        return None

