"""
MongoDB ERP Adapter — wraps the existing MongoDB connector for invoice/payment sync.
"""

import logging
from datetime import datetime, timezone
from typing import Any

from src.core.interfaces.erp import (
    ConnectorInfo,
    ERPCustomer,
    ERPInvoice,
    ERPPayment,
    IERPConnector,
    SyncDirection,
)

logger = logging.getLogger(__name__)


class MongoDBERPAdapter(IERPConnector):
    """
    MongoDB-based CRM adapter.

    Connects to an existing MongoDB database and syncs invoices/payments.
    Requires MONGODB_URL and MONGODB_DATABASE env vars.
    """

    def __init__(self, url: str, database: str) -> None:
        self._url = url
        self._database = database
        self._client: Any = None
        self._db: Any = None

    async def connect(self) -> bool:
        try:
            from motor.motor_asyncio import AsyncIOMotorClient
            self._client = AsyncIOMotorClient(self._url)
            self._db = self._client[self._database]
            # Ping to verify
            await self._client.admin.command("ping")
            logger.info("Connected to MongoDB ERP at %s/%s", self._url, self._database)
            return True
        except Exception as exc:
            logger.error("MongoDB ERP connection failed: %s", exc)
            return False

    async def disconnect(self) -> None:
        if self._client:
            self._client.close()
            self._client = None
            self._db = None

    async def test_connection(self) -> tuple[bool, str]:
        try:
            if not self._client:
                connected = await self.connect()
                if not connected:
                    return False, "Could not connect to MongoDB"
            await self._client.admin.command("ping")
            return True, f"Connected to {self._database}"
        except Exception as exc:
            return False, str(exc)

    async def sync_invoices(
        self,
        since: datetime | None = None,
        batch_size: int = 500,
    ) -> list[ERPInvoice]:
        if not self._db:
            await self.connect()
        if not self._db:
            return []

        query: dict[str, Any] = {}
        if since:
            query["updated_at"] = {"$gte": since}

        cursor = self._db.invoices.find(query).limit(batch_size)
        invoices: list[ERPInvoice] = []

        async for doc in cursor:
            invoices.append(ERPInvoice(
                external_id=str(doc.get("_id", "")),
                invoice_number=doc.get("invoice_number", ""),
                customer_name=doc.get("customer_name"),
                customer_phone=doc.get("customer_phone") or doc.get("phone"),
                total_amount=float(doc.get("total_amount", 0)),
                amount_paid=float(doc.get("amount_paid", 0)),
                status=doc.get("status", "draft"),
                issued_at=doc.get("issued_at") or doc.get("created_at"),
                due_date=doc.get("due_date"),
                line_items=doc.get("line_items", []),
                raw_data={k: v for k, v in doc.items() if k != "_id"},
            ))

        logger.info("Synced %d invoices from MongoDB ERP", len(invoices))
        return invoices

    async def sync_payments(
        self,
        since: datetime | None = None,
        batch_size: int = 500,
    ) -> list[ERPPayment]:
        if not self._db:
            await self.connect()
        if not self._db:
            return []

        query: dict[str, Any] = {}
        if since:
            query["created_at"] = {"$gte": since}

        cursor = self._db.payments.find(query).limit(batch_size)
        payments: list[ERPPayment] = []

        async for doc in cursor:
            payments.append(ERPPayment(
                external_id=str(doc.get("_id", "")),
                invoice_external_id=str(doc.get("invoice_id", "")),
                amount=float(doc.get("amount", 0)),
                payment_method=doc.get("payment_method"),
                reference_number=doc.get("reference_number"),
                payment_date=doc.get("payment_date") or doc.get("created_at"),
                notes=doc.get("notes"),
                raw_data={k: v for k, v in doc.items() if k != "_id"},
            ))

        logger.info("Synced %d payments from MongoDB ERP", len(payments))
        return payments

    async def sync_customers(
        self,
        since: datetime | None = None,
        batch_size: int = 500,
    ) -> list[ERPCustomer]:
        if not self._db:
            await self.connect()
        if not self._db:
            return []

        query: dict[str, Any] = {}
        if since:
            query["updated_at"] = {"$gte": since}

        cursor = self._db.customers.find(query).limit(batch_size)
        customers: list[ERPCustomer] = []

        async for doc in cursor:
            customers.append(ERPCustomer(
                external_id=str(doc.get("_id", "")),
                name=doc.get("name", ""),
                phone=doc.get("phone"),
                email=doc.get("email"),
                company=doc.get("company"),
                tags=doc.get("tags", []),
                raw_data={k: v for k, v in doc.items() if k != "_id"},
            ))

        logger.info("Synced %d customers from MongoDB ERP", len(customers))
        return customers

    def get_info(self) -> ConnectorInfo:
        return ConnectorInfo(
            name="mongodb",
            display_name="MongoDB CRM",
            supports_invoices=True,
            supports_payments=True,
            supports_customers=True,
            supports_products=False,
            sync_direction=SyncDirection.PULL,
            metadata={"database": self._database},
        )

