"""
Database Loader

Generic database loader supporting MongoDB and PostgreSQL.
"""

from datetime import datetime
from typing import Any

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo import UpdateOne

from src.core.interfaces import DataRecord

from .base import BaseLoader, LoaderRegistry, LoadResult


@LoaderRegistry.register("mongodb")
class DatabaseLoader(BaseLoader):
    """
    Generic MongoDB loader for ETL operations.
    Supports upsert operations with configurable key fields.
    """

    def __init__(
        self,
        connection_string: str,
        database_name: str,
        tenant_id: str | None = None,
        key_fields: list[str] | None = None,
    ):
        super().__init__(tenant_id)
        self._connection_string = connection_string
        self._database_name = database_name
        self._key_fields = key_fields or ["_id"]
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
        """Close MongoDB connection."""
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
        """Load records into MongoDB collection."""
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

        if upsert:
            # Prepare bulk upsert operations
            operations = []
            for record in records:
                try:
                    data = self._prepare_record(record)
                    filter_doc = self._create_filter(data)
                    operations.append(
                        UpdateOne(
                            filter_doc,
                            {"$set": data},
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
                    result.skipped_count = bulk_result.matched_count - bulk_result.modified_count
                except Exception as e:
                    result.error_count += len(operations)
                    result.errors.append(f"Bulk write error: {str(e)}")
        else:
            # Simple insert
            docs = []
            for record in records:
                try:
                    docs.append(self._prepare_record(record))
                except Exception as e:
                    result.error_count += 1
                    result.errors.append(f"Prepare error: {str(e)}")

            if docs:
                try:
                    insert_result = await collection.insert_many(docs, ordered=False)
                    result.success_count = len(insert_result.inserted_ids)
                    result.created_count = result.success_count
                except Exception as e:
                    result.error_count += len(docs)
                    result.errors.append(f"Insert error: {str(e)}")

        result.complete()
        return result

    def _create_filter(self, data: dict[str, Any]) -> dict[str, Any]:
        """Create filter document for upsert."""
        filter_doc = {}
        for field in self._key_fields:
            if field in data:
                filter_doc[field] = data[field]

        # If no key fields found, use phone_number as default
        if not filter_doc and "phone_number" in data:
            filter_doc["phone_number"] = data["phone_number"]

        return filter_doc


@LoaderRegistry.register("postgresql")
class PostgreSQLLoader(BaseLoader):
    """
    PostgreSQL loader for ETL operations.
    Uses asyncpg for async database access.
    """

    def __init__(
        self,
        connection_string: str,
        tenant_id: str | None = None,
        key_fields: list[str] | None = None,
    ):
        super().__init__(tenant_id)
        self._connection_string = connection_string
        self._key_fields = key_fields or ["id"]
        self._pool = None

    async def connect(self) -> bool:
        """Connect to PostgreSQL."""
        try:
            import asyncpg

            self._pool = await asyncpg.create_pool(self._connection_string)
            self._connected = True
            return True
        except Exception:
            self._connected = False
            return False

    async def disconnect(self) -> None:
        """Close PostgreSQL connection."""
        if self._pool:
            await self._pool.close()
        self._pool = None
        self._connected = False

    async def load_with_result(
        self,
        records: list[DataRecord],
        target: str,
        upsert: bool = True,
    ) -> LoadResult:
        """Load records into PostgreSQL table."""
        result = LoadResult(
            success_count=0,
            error_count=0,
            errors=[],
            started_at=datetime.utcnow(),
        )

        if not self._connected:
            await self.connect()

        if not self._pool:
            result.errors.append("Database connection not established")
            result.complete()
            return result

        async with self._pool.acquire() as conn:
            for record in records:
                try:
                    data = self._prepare_record(record)
                    columns = list(data.keys())
                    values = list(data.values())

                    if upsert:
                        # Build upsert query
                        conflict_cols = self._key_fields
                        update_cols = [c for c in columns if c not in conflict_cols]

                        placeholders = [f"${i+1}" for i in range(len(values))]
                        update_set = ", ".join(
                            f"{col} = EXCLUDED.{col}" for col in update_cols
                        )

                        query = f"""
                            INSERT INTO {target} ({', '.join(columns)})
                            VALUES ({', '.join(placeholders)})
                            ON CONFLICT ({', '.join(conflict_cols)})
                            DO UPDATE SET {update_set}
                        """
                    else:
                        placeholders = [f"${i+1}" for i in range(len(values))]
                        query = f"""
                            INSERT INTO {target} ({', '.join(columns)})
                            VALUES ({', '.join(placeholders)})
                        """

                    await conn.execute(query, *values)
                    result.success_count += 1

                except Exception as e:
                    result.error_count += 1
                    result.errors.append(f"Load error: {str(e)}")

        result.complete()
        return result

