"""
SQLAlchemy Models - Sales Module
"""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, JSON, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..session import Base
from ..base_models import UUIDMixin, TimestampMixin


class ProductModel(Base, UUIDMixin, TimestampMixin):
    """Product catalog item."""

    __tablename__ = "products"

    tenant_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str | None] = mapped_column(String(50), index=True)
    category: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    # cement, building_materials, etc.

    description: Mapped[str | None] = mapped_column(Text)
    unit: Mapped[str] = mapped_column(String(50), default="ton")
    current_price: Mapped[int] = mapped_column(Integer, default=0)
    # Price in IRR

    # Price history is stored separately
    min_order_quantity: Mapped[int] = mapped_column(Integer, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Target segments for recommendations
    target_segments: Mapped[list] = mapped_column(JSON, default=list)

    metadata_: Mapped[dict] = mapped_column("metadata", JSON, default=dict)

    # Relationships
    price_history: Mapped[list["ProductPriceModel"]] = relationship(back_populates="product")

    __table_args__ = (
        Index("ix_products_tenant_category", "tenant_id", "category"),
        Index("ix_products_tenant_code", "tenant_id", "code"),
    )


class ProductPriceModel(Base, UUIDMixin, TimestampMixin):
    """Product price history."""

    __tablename__ = "product_prices"

    product_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    price: Mapped[int] = mapped_column(Integer, nullable=False)
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    effective_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(Text)

    # Relationships
    product: Mapped["ProductModel"] = relationship(back_populates="price_history")

    __table_args__ = (
        Index("ix_product_prices_product_effective", "product_id", "effective_from"),
    )


class InvoiceModel(Base, UUIDMixin, TimestampMixin):
    """Pre-invoice / Invoice."""

    __tablename__ = "invoices"

    tenant_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    contact_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("contacts.id", ondelete="SET NULL"),
        index=True,
    )
    phone_number: Mapped[str] = mapped_column(String(20), nullable=False, index=True)

    # Invoice details
    invoice_number: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    invoice_type: Mapped[str] = mapped_column(String(20), default="pre_invoice")
    # pre_invoice, invoice

    # External reference (from source system)
    external_id: Mapped[str | None] = mapped_column(String(100))
    source_system: Mapped[str | None] = mapped_column(String(50))
    # mongodb, erp, etc.

    # Amounts
    subtotal: Mapped[int] = mapped_column(Integer, default=0)
    tax_amount: Mapped[int] = mapped_column(Integer, default=0)
    discount_amount: Mapped[int] = mapped_column(Integer, default=0)
    total_amount: Mapped[int] = mapped_column(Integer, default=0)

    # Status
    status: Mapped[str] = mapped_column(String(50), default="draft", index=True)
    # draft, issued, partially_paid, paid, cancelled

    # Dates
    issued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    due_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Salesperson
    salesperson_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("salespersons.id", ondelete="SET NULL"),
    )
    salesperson_name: Mapped[str | None] = mapped_column(String(255))

    notes: Mapped[str | None] = mapped_column(Text)
    metadata_: Mapped[dict] = mapped_column("metadata", JSON, default=dict)

    # Relationships
    line_items: Mapped[list["InvoiceLineItemModel"]] = relationship(back_populates="invoice")
    payments: Mapped[list["PaymentModel"]] = relationship(back_populates="invoice")

    __table_args__ = (
        Index("ix_invoices_tenant_phone", "tenant_id", "phone_number"),
        Index("ix_invoices_tenant_status", "tenant_id", "status"),
        Index("ix_invoices_tenant_issued", "tenant_id", "issued_at"),
        Index("ix_invoices_external_id", "tenant_id", "external_id"),
    )


class InvoiceLineItemModel(Base, UUIDMixin, TimestampMixin):
    """Invoice line item."""

    __tablename__ = "invoice_line_items"

    invoice_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("invoices.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    product_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="SET NULL"),
    )

    # Product details (denormalized for history)
    product_name: Mapped[str] = mapped_column(String(255), nullable=False)
    product_code: Mapped[str | None] = mapped_column(String(50))
    product_category: Mapped[str | None] = mapped_column(String(100))

    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str] = mapped_column(String(50), default="unit")
    unit_price: Mapped[int] = mapped_column(Integer, nullable=False)
    discount: Mapped[int] = mapped_column(Integer, default=0)
    total: Mapped[int] = mapped_column(Integer, nullable=False)

    metadata_: Mapped[dict] = mapped_column("metadata", JSON, default=dict)

    # Relationships
    invoice: Mapped["InvoiceModel"] = relationship(back_populates="line_items")


class PaymentModel(Base, UUIDMixin, TimestampMixin):
    """Payment record."""

    __tablename__ = "payments"

    tenant_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    invoice_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("invoices.id", ondelete="SET NULL"),
        index=True,
    )
    contact_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("contacts.id", ondelete="SET NULL"),
        index=True,
    )
    phone_number: Mapped[str] = mapped_column(String(20), nullable=False, index=True)

    # Payment details
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    payment_method: Mapped[str] = mapped_column(String(50), default="bank_transfer")
    # bank_transfer, card, cash, check

    # External reference
    external_id: Mapped[str | None] = mapped_column(String(100))
    source_system: Mapped[str | None] = mapped_column(String(50))
    reference_number: Mapped[str | None] = mapped_column(String(100))

    # Status
    status: Mapped[str] = mapped_column(String(50), default="confirmed", index=True)
    # pending, confirmed, failed, refunded

    # Timestamps
    paid_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    notes: Mapped[str | None] = mapped_column(Text)
    metadata_: Mapped[dict] = mapped_column("metadata", JSON, default=dict)

    # Relationships
    invoice: Mapped["InvoiceModel | None"] = relationship(back_populates="payments")

    __table_args__ = (
        Index("ix_payments_tenant_phone", "tenant_id", "phone_number"),
        Index("ix_payments_tenant_paid_at", "tenant_id", "paid_at"),
        Index("ix_payments_external_id", "tenant_id", "external_id"),
    )

