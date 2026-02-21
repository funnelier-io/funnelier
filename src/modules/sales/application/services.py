"""
Sales Application Services

Business logic for invoice and payment management.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from src.modules.sales.domain.entities import Invoice, InvoiceLineItem, Product
from src.modules.sales.domain.repositories import (
    IInvoiceRepository,
    IProductRepository,
)
from src.modules.leads.domain.repositories import IContactRepository


class InvoiceService:
    """Service for invoice management."""

    def __init__(
        self,
        invoice_repo: IInvoiceRepository,
        product_repo: IProductRepository,
        contact_repo: IContactRepository,
    ):
        self._invoice_repo = invoice_repo
        self._product_repo = product_repo
        self._contact_repo = contact_repo

    async def create_invoice(
        self,
        tenant_id: UUID,
        phone_number: str,
        line_items: list[dict[str, Any]],
        customer_name: str | None = None,
        contact_id: UUID | None = None,
        salesperson_id: UUID | None = None,
        salesperson_name: str | None = None,
        discount_amount: int = 0,
        tax_amount: int = 0,
        due_date: datetime | None = None,
        notes: str | None = None,
        external_id: str | None = None,
    ) -> Invoice:
        """Create a new invoice."""
        # Generate invoice number
        invoice_count = await self._invoice_repo.count_by_tenant(tenant_id)
        invoice_number = f"INV-{datetime.utcnow().strftime('%Y%m%d')}-{invoice_count + 1:05d}"

        # Create line items
        items: list[InvoiceLineItem] = []
        subtotal = 0

        for item_data in line_items:
            quantity = item_data.get("quantity", 1)
            unit_price = item_data.get("unit_price", 0)
            item_discount = item_data.get("discount_amount", 0)
            item_tax = item_data.get("tax_amount", 0)
            total = int(quantity * unit_price) - item_discount + item_tax

            item = InvoiceLineItem(
                tenant_id=tenant_id,
                invoice_id=None,  # Will be set after invoice creation
                product_id=item_data.get("product_id"),
                product_name=item_data.get("product_name", ""),
                product_code=item_data.get("product_code"),
                quantity=quantity,
                unit=item_data.get("unit", "unit"),
                unit_price=unit_price,
                total_price=total,
                discount_amount=item_discount,
                tax_amount=item_tax,
            )
            items.append(item)
            subtotal += total

        # Create invoice
        invoice = Invoice(
            tenant_id=tenant_id,
            invoice_number=invoice_number,
            contact_id=contact_id,
            phone_number=phone_number,
            customer_name=customer_name,
            salesperson_id=salesperson_id,
            salesperson_name=salesperson_name,
            line_items=items,
            subtotal=subtotal,
            discount_amount=discount_amount,
            tax_amount=tax_amount,
            total_amount=subtotal - discount_amount + tax_amount,
            due_date=due_date,
            notes=notes,
            external_id=external_id,
        )

        await self._invoice_repo.add(invoice)

        # Update contact stage
        if contact_id:
            contact = await self._contact_repo.get(contact_id)
            if contact:
                contact.record_invoice(invoice.total_amount, is_paid=False)
                await self._contact_repo.update(contact)

        return invoice

    async def issue_invoice(self, invoice_id: UUID) -> Invoice:
        """Issue a draft invoice."""
        invoice = await self._invoice_repo.get(invoice_id)
        if not invoice:
            raise ValueError(f"Invoice {invoice_id} not found")

        invoice.issue()
        await self._invoice_repo.update(invoice)
        return invoice

    async def record_payment(
        self,
        invoice_id: UUID,
        amount: int,
        payment_method: str | None = None,
    ) -> Invoice:
        """Record a payment for an invoice."""
        invoice = await self._invoice_repo.get(invoice_id)
        if not invoice:
            raise ValueError(f"Invoice {invoice_id} not found")

        was_unpaid = invoice.amount_paid == 0
        invoice.record_payment(amount, payment_method)
        await self._invoice_repo.update(invoice)

        # Update contact if payment completes the invoice
        if invoice.contact_id and invoice.status.value == "paid":
            contact = await self._contact_repo.get(invoice.contact_id)
            if contact:
                contact.record_invoice(invoice.total_amount, is_paid=True)
                await self._contact_repo.update(contact)

        return invoice

    async def cancel_invoice(
        self,
        invoice_id: UUID,
        reason: str | None = None,
    ) -> Invoice:
        """Cancel an invoice."""
        invoice = await self._invoice_repo.get(invoice_id)
        if not invoice:
            raise ValueError(f"Invoice {invoice_id} not found")

        invoice.cancel(reason)
        await self._invoice_repo.update(invoice)
        return invoice


class ProductService:
    """Service for product management."""

    def __init__(self, product_repo: IProductRepository):
        self._product_repo = product_repo

    async def create_product(
        self,
        tenant_id: UUID,
        name: str,
        category: str,
        unit: str = "unit",
        base_price: int = 0,
        current_price: int = 0,
        code: str | None = None,
        description: str | None = None,
        subcategory: str | None = None,
        specifications: dict[str, Any] | None = None,
        tags: list[str] | None = None,
        recommended_segments: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Product:
        """Create a new product."""
        product = Product(
            tenant_id=tenant_id,
            name=name,
            code=code,
            description=description,
            category=category,
            subcategory=subcategory,
            unit=unit,
            base_price=base_price,
            current_price=current_price or base_price,
            price_updated_at=datetime.utcnow(),
            specifications=specifications or {},
            tags=tags or [],
            recommended_segments=recommended_segments or [],
            metadata=metadata or {},
        )

        await self._product_repo.add(product)
        return product

    async def update_price(
        self,
        product_id: UUID,
        new_price: int,
    ) -> Product:
        """Update product price."""
        product = await self._product_repo.get(product_id)
        if not product:
            raise ValueError(f"Product {product_id} not found")

        product.current_price = new_price
        product.price_updated_at = datetime.utcnow()
        await self._product_repo.update(product)
        return product

    async def bulk_update_prices(
        self,
        price_updates: list[dict[str, Any]],
    ) -> tuple[int, list[str]]:
        """
        Bulk update product prices.
        Returns (updated_count, errors).
        """
        updated = 0
        errors: list[str] = []

        for update in price_updates:
            try:
                product_id = update.get("product_id")
                new_price = update.get("new_price")

                if not product_id or new_price is None:
                    errors.append(f"Invalid update data: {update}")
                    continue

                await self.update_price(UUID(product_id), new_price)
                updated += 1

            except Exception as e:
                errors.append(f"Product {update.get('product_id')}: {str(e)}")

        return updated, errors

    async def get_products_for_segment(
        self,
        segment: str,
    ) -> list[Product]:
        """Get products recommended for an RFM segment."""
        return await self._product_repo.get_by_segment(segment)

