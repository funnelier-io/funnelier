"""
Abstract ERP/CRM Connector Interface

Pluggable adapter pattern for ERP and CRM integrations.
Implement this interface to sync invoices, payments, and customer data
from any external system (MongoDB CRM, Odoo, SAP, Salesforce, etc.).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class SyncDirection(str, Enum):
    """Direction of data sync."""
    PULL = "pull"      # From ERP → Funnelier
    PUSH = "push"      # From Funnelier → ERP
    BIDIRECTIONAL = "bidirectional"


@dataclass
class SyncResult:
    """Result of a sync operation."""
    success: bool
    records_synced: int = 0
    records_created: int = 0
    records_updated: int = 0
    records_failed: int = 0
    errors: list[str] = field(default_factory=list)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def duration_seconds(self) -> float | None:
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None


@dataclass
class ERPInvoice:
    """Normalized invoice representation from any ERP."""
    external_id: str
    invoice_number: str
    customer_name: str | None = None
    customer_phone: str | None = None
    total_amount: float = 0.0
    amount_paid: float = 0.0
    status: str = "draft"
    issued_at: datetime | None = None
    due_date: datetime | None = None
    line_items: list[dict[str, Any]] = field(default_factory=list)
    raw_data: dict[str, Any] = field(default_factory=dict)


@dataclass
class ERPPayment:
    """Normalized payment representation from any ERP."""
    external_id: str
    invoice_external_id: str
    amount: float
    payment_method: str | None = None
    reference_number: str | None = None
    payment_date: datetime | None = None
    notes: str | None = None
    raw_data: dict[str, Any] = field(default_factory=dict)


@dataclass
class ERPCustomer:
    """Normalized customer representation from any ERP."""
    external_id: str
    name: str
    phone: str | None = None
    email: str | None = None
    company: str | None = None
    tags: list[str] = field(default_factory=list)
    raw_data: dict[str, Any] = field(default_factory=dict)


@dataclass
class ConnectorInfo:
    """Metadata about an ERP/CRM connector."""
    name: str
    display_name: str
    supports_invoices: bool = True
    supports_payments: bool = True
    supports_customers: bool = False
    supports_products: bool = False
    sync_direction: SyncDirection = SyncDirection.PULL
    metadata: dict[str, Any] = field(default_factory=dict)


class IERPConnector(ABC):
    """
    Abstract interface for ERP/CRM data connectors.

    Implementations:
    - MongoDBERPAdapter: Existing MongoDB-based custom CRM
    - MockERPAdapter: Development/test adapter with sample data
    - (Future) OdooAdapter, SalesforceAdapter, SAPAdapter, etc.

    Usage:
        connector = ERPConnectorRegistry.get()
        await connector.connect()
        invoices = await connector.sync_invoices(since=last_sync)
    """

    @abstractmethod
    async def connect(self) -> bool:
        """
        Establish connection to the ERP/CRM.

        Returns:
            True if connection successful
        """
        ...

    @abstractmethod
    async def disconnect(self) -> None:
        """Close connection to the ERP/CRM."""
        ...

    @abstractmethod
    async def test_connection(self) -> tuple[bool, str]:
        """
        Test connectivity to the ERP/CRM.

        Returns:
            (success, message) tuple
        """
        ...

    @abstractmethod
    async def sync_invoices(
        self,
        since: datetime | None = None,
        batch_size: int = 500,
    ) -> list[ERPInvoice]:
        """
        Pull invoices from the ERP.

        Args:
            since: Only return invoices created/modified after this date
            batch_size: Maximum number of records to return

        Returns:
            List of normalized ERPInvoice objects
        """
        ...

    @abstractmethod
    async def sync_payments(
        self,
        since: datetime | None = None,
        batch_size: int = 500,
    ) -> list[ERPPayment]:
        """
        Pull payments from the ERP.

        Args:
            since: Only return payments created/modified after this date
            batch_size: Maximum number of records to return

        Returns:
            List of normalized ERPPayment objects
        """
        ...

    @abstractmethod
    async def sync_customers(
        self,
        since: datetime | None = None,
        batch_size: int = 500,
    ) -> list[ERPCustomer]:
        """
        Pull customer records from the ERP.

        Args:
            since: Only return customers created/modified after this date
            batch_size: Maximum number of records to return

        Returns:
            List of normalized ERPCustomer objects
        """
        ...

    @abstractmethod
    def get_info(self) -> ConnectorInfo:
        """Get metadata about this connector."""
        ...

