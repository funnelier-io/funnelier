"""
Sales Module - Domain Layer
Entities for invoices, payments, and products
"""

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import Field

from src.core.domain import (
    InvoiceStatus,
    Money,
    PaymentStatus,
    TenantAggregateRoot,
    TenantEntity,
    InvoiceCancelledEvent,
    InvoiceCreatedEvent,
    InvoicePaidEvent,
)


class Product(TenantEntity[UUID]):
    """
    Product catalog item.
    """

    id: UUID = Field(default_factory=uuid4)
    name: str
    code: str | None = None
    description: str | None = None

    # Categorization
    category: str  # سیمان، بلوک، بتن، etc.
    subcategory: str | None = None

    # Pricing
    unit: str = "ton"  # ton, bag, m3, piece, etc.
    base_price: int = 0  # In Rial
    current_price: int = 0
    price_updated_at: datetime | None = None

    # Inventory (optional)
    is_available: bool = True
    stock_quantity: int | None = None

    # Attributes
    specifications: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)

    # RFM segment recommendations
    recommended_segments: list[str] = Field(default_factory=list)

    is_active: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class InvoiceLineItem(TenantEntity[UUID]):
    """
    Line item in an invoice.
    """

    id: UUID = Field(default_factory=uuid4)
    invoice_id: UUID

    product_id: UUID | None = None
    product_name: str
    product_code: str | None = None

    quantity: float
    unit: str
    unit_price: int  # In Rial
    total_price: int  # quantity * unit_price

    discount_amount: int = 0
    tax_amount: int = 0

    metadata: dict[str, Any] = Field(default_factory=dict)


class Invoice(TenantAggregateRoot[UUID]):
    """
    Pre-invoice / Invoice aggregate.
    """

    id: UUID = Field(default_factory=uuid4)
    invoice_number: str

    # Customer reference
    contact_id: UUID | None = None
    phone_number: str
    customer_name: str | None = None

    # Salesperson
    salesperson_id: UUID | None = None
    salesperson_name: str | None = None

    # Line items (stored separately, referenced here for totals)
    line_items: list[InvoiceLineItem] = Field(default_factory=list)

    # Totals
    subtotal: int = 0  # Sum of line items
    discount_amount: int = 0
    tax_amount: int = 0
    total_amount: int = 0  # subtotal - discount + tax

    # Status
    status: InvoiceStatus = InvoiceStatus.DRAFT

    # Dates
    issued_at: datetime | None = None
    due_date: datetime | None = None
    paid_at: datetime | None = None
    cancelled_at: datetime | None = None

    # Payment tracking
    amount_paid: int = 0
    payment_method: str | None = None

    # Notes
    notes: str | None = None
    internal_notes: str | None = None
    cancellation_reason: str | None = None

    # External reference (from source system)
    external_id: str | None = None

    metadata: dict[str, Any] = Field(default_factory=dict)

    def calculate_totals(self) -> None:
        """Recalculate totals from line items."""
        self.subtotal = sum(item.total_price for item in self.line_items)
        self.total_amount = self.subtotal - self.discount_amount + self.tax_amount

    def issue(self) -> None:
        """Issue the invoice."""
        if self.status != InvoiceStatus.DRAFT:
            raise ValueError(f"Cannot issue invoice in status {self.status}")

        self.status = InvoiceStatus.ISSUED
        self.issued_at = datetime.utcnow()

        self.add_domain_event(
            InvoiceCreatedEvent(
                aggregate_id=self.id,
                tenant_id=self.tenant_id,
                phone_number=self.phone_number,
                invoice_number=self.invoice_number,
                total_amount=self.total_amount,
                products=[
                    {
                        "name": item.product_name,
                        "quantity": item.quantity,
                        "total": item.total_price,
                    }
                    for item in self.line_items
                ],
            )
        )

    def record_payment(
        self,
        amount: int,
        payment_method: str | None = None,
    ) -> None:
        """Record a payment."""
        self.amount_paid += amount
        if payment_method:
            self.payment_method = payment_method

        if self.amount_paid >= self.total_amount:
            self.status = InvoiceStatus.PAID
            self.paid_at = datetime.utcnow()

            self.add_domain_event(
                InvoicePaidEvent(
                    aggregate_id=self.id,
                    tenant_id=self.tenant_id,
                    phone_number=self.phone_number,
                    invoice_number=self.invoice_number,
                    payment_amount=amount,
                    payment_method=payment_method,
                )
            )
        elif self.amount_paid > 0:
            self.status = InvoiceStatus.PARTIAL_PAID

    def cancel(self, reason: str | None = None) -> None:
        """Cancel the invoice."""
        if self.status == InvoiceStatus.PAID:
            raise ValueError("Cannot cancel a paid invoice")

        self.status = InvoiceStatus.CANCELLED
        self.cancelled_at = datetime.utcnow()
        self.cancellation_reason = reason

        self.add_domain_event(
            InvoiceCancelledEvent(
                aggregate_id=self.id,
                tenant_id=self.tenant_id,
                phone_number=self.phone_number,
                invoice_number=self.invoice_number,
                cancellation_reason=reason,
            )
        )

    @property
    def is_overdue(self) -> bool:
        """Check if invoice is overdue."""
        if self.status in [InvoiceStatus.PAID, InvoiceStatus.CANCELLED]:
            return False
        if self.due_date is None:
            return False
        return datetime.utcnow() > self.due_date

    @property
    def remaining_amount(self) -> int:
        """Get remaining amount to be paid."""
        return max(0, self.total_amount - self.amount_paid)


class Payment(TenantEntity[UUID]):
    """
    Payment record.
    """

    id: UUID = Field(default_factory=uuid4)

    # References
    invoice_id: UUID | None = None
    contact_id: UUID | None = None
    phone_number: str

    # Payment details
    amount: int  # In Rial
    payment_method: str  # cash, card, transfer, cheque, etc.
    status: PaymentStatus = PaymentStatus.PENDING

    # Dates
    payment_date: datetime
    confirmed_at: datetime | None = None

    # Reference numbers
    reference_number: str | None = None
    bank_reference: str | None = None

    # External reference (from source system)
    external_id: str | None = None

    notes: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

