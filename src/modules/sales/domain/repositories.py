"""
Sales Module - Domain Repository Interfaces
"""

from abc import abstractmethod
from datetime import datetime
from typing import Any
from uuid import UUID

from src.core.interfaces import IAggregateRepository, ITenantRepository

from .entities import Invoice, InvoiceLineItem, Payment, Product


class IProductRepository(ITenantRepository[Product, UUID]):
    """Repository interface for products."""

    @abstractmethod
    async def get_by_code(self, code: str) -> Product | None:
        """Get product by code."""
        pass

    @abstractmethod
    async def get_by_category(
        self,
        category: str,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Product]:
        """Get products by category."""
        pass

    @abstractmethod
    async def get_active_products(self) -> list[Product]:
        """Get all active products."""
        pass

    @abstractmethod
    async def get_for_segment(
        self,
        segment: str,
    ) -> list[Product]:
        """Get products recommended for an RFM segment."""
        pass

    @abstractmethod
    async def update_price(
        self,
        product_id: UUID,
        new_price: int,
    ) -> None:
        """Update product price."""
        pass

    @abstractmethod
    async def bulk_update_prices(
        self,
        price_updates: list[tuple[UUID, int]],
    ) -> int:
        """Bulk update product prices."""
        pass


class IInvoiceRepository(IAggregateRepository[Invoice, UUID]):
    """Repository interface for invoices."""

    @abstractmethod
    async def get_by_number(self, invoice_number: str) -> Invoice | None:
        """Get invoice by invoice number."""
        pass

    @abstractmethod
    async def get_by_phone(
        self,
        phone_number: str,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Invoice]:
        """Get invoices by phone number."""
        pass

    @abstractmethod
    async def get_by_contact(
        self,
        contact_id: UUID,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Invoice]:
        """Get invoices by contact ID."""
        pass

    @abstractmethod
    async def get_by_salesperson(
        self,
        salesperson_id: UUID,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Invoice]:
        """Get invoices by salesperson."""
        pass

    @abstractmethod
    async def get_by_status(
        self,
        status: str,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Invoice]:
        """Get invoices by status."""
        pass

    @abstractmethod
    async def get_by_date_range(
        self,
        start_date: datetime,
        end_date: datetime,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Invoice]:
        """Get invoices within date range."""
        pass

    @abstractmethod
    async def get_overdue_invoices(self) -> list[Invoice]:
        """Get all overdue invoices."""
        pass

    @abstractmethod
    async def get_sales_stats(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        group_by: str | None = None,
    ) -> dict[str, Any]:
        """Get sales statistics."""
        pass

    @abstractmethod
    async def get_by_external_id(self, external_id: str) -> Invoice | None:
        """Get invoice by external system ID."""
        pass


class IPaymentRepository(ITenantRepository[Payment, UUID]):
    """Repository interface for payments."""

    @abstractmethod
    async def get_by_invoice(self, invoice_id: UUID) -> list[Payment]:
        """Get payments for an invoice."""
        pass

    @abstractmethod
    async def get_by_phone(
        self,
        phone_number: str,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Payment]:
        """Get payments by phone number."""
        pass

    @abstractmethod
    async def get_by_date_range(
        self,
        start_date: datetime,
        end_date: datetime,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Payment]:
        """Get payments within date range."""
        pass

    @abstractmethod
    async def get_payment_stats(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> dict[str, Any]:
        """Get payment statistics."""
        pass

    @abstractmethod
    async def get_by_external_id(self, external_id: str) -> Payment | None:
        """Get payment by external system ID."""
        pass

