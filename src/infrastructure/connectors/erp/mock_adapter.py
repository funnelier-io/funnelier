"""
Mock ERP Adapter — returns sample data for development/testing.
"""

import logging
import uuid
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


class MockERPAdapter(IERPConnector):
    """Development/test ERP adapter that returns sample data."""

    def __init__(self) -> None:
        self._connected = False

    async def connect(self) -> bool:
        self._connected = True
        logger.info("[MockERP] Connected")
        return True

    async def disconnect(self) -> None:
        self._connected = False
        logger.info("[MockERP] Disconnected")

    async def test_connection(self) -> tuple[bool, str]:
        return True, "Mock ERP always available"

    async def sync_invoices(
        self,
        since: datetime | None = None,
        batch_size: int = 500,
    ) -> list[ERPInvoice]:
        logger.info("[MockERP] sync_invoices(since=%s, batch_size=%d)", since, batch_size)
        # Return empty — no mock data by default
        return []

    async def sync_payments(
        self,
        since: datetime | None = None,
        batch_size: int = 500,
    ) -> list[ERPPayment]:
        logger.info("[MockERP] sync_payments(since=%s, batch_size=%d)", since, batch_size)
        return []

    async def sync_customers(
        self,
        since: datetime | None = None,
        batch_size: int = 500,
    ) -> list[ERPCustomer]:
        logger.info("[MockERP] sync_customers(since=%s, batch_size=%d)", since, batch_size)
        return []

    def get_info(self) -> ConnectorInfo:
        return ConnectorInfo(
            name="mock",
            display_name="Mock ERP (Dev)",
            supports_invoices=True,
            supports_payments=True,
            supports_customers=True,
            supports_products=False,
            sync_direction=SyncDirection.PULL,
        )

