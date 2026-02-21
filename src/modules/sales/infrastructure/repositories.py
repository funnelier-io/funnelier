"""
Sales Module - Repository Implementations
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select, func, update as sa_update
from sqlalchemy.orm import selectinload

from src.core.domain import InvoiceStatus, PaymentStatus
from src.infrastructure.database.repositories import SqlAlchemyRepository
from src.infrastructure.database.models.sales import (
    ProductModel,
    ProductPriceModel,
    InvoiceModel,
    InvoiceLineItemModel,
    PaymentModel,
)
from src.modules.sales.domain.entities import Product, Invoice, InvoiceLineItem, Payment
from src.modules.sales.domain.repositories import (
    IProductRepository,
    IInvoiceRepository,
    IPaymentRepository,
)


class ProductRepository(SqlAlchemyRepository[ProductModel, Product], IProductRepository):
    """SQLAlchemy implementation of IProductRepository."""

    def __init__(self, session, tenant_id: UUID):
        super().__init__(session, tenant_id, ProductModel)

    def _to_entity(self, model: ProductModel) -> Product:
        return Product(
            id=model.id,
            tenant_id=model.tenant_id,
            name=model.name,
            code=model.code,
            description=model.description,
            category=model.category,
            unit=model.unit,
            current_price=model.current_price,
            base_price=model.current_price,
            is_available=model.is_active,
            recommended_segments=model.target_segments or [],
            is_active=model.is_active,
            metadata=model.metadata_ or {},
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    def _to_model(self, entity: Product) -> ProductModel:
        return ProductModel(
            id=entity.id,
            tenant_id=entity.tenant_id,
            name=entity.name,
            code=entity.code,
            description=entity.description,
            category=entity.category,
            unit=entity.unit,
            current_price=entity.current_price,
            is_active=entity.is_active,
            target_segments=entity.recommended_segments,
            metadata_=entity.metadata,
        )

    async def get_by_code(self, code: str) -> Product | None:
        stmt = self._base_query().where(ProductModel.code == code)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def get_by_category(self, category: str, skip: int = 0, limit: int = 100) -> list[Product]:
        stmt = self._base_query().where(ProductModel.category == category).offset(skip).limit(limit)
        result = await self._session.execute(stmt)
        return [self._to_entity(m) for m in result.scalars().all()]

    async def get_active_products(self) -> list[Product]:
        stmt = self._base_query().where(ProductModel.is_active.is_(True))
        result = await self._session.execute(stmt)
        return [self._to_entity(m) for m in result.scalars().all()]

    async def get_by_segment(self, segment: str) -> list[Product]:
        stmt = self._base_query().where(ProductModel.target_segments.contains([segment]))
        result = await self._session.execute(stmt)
        return [self._to_entity(m) for m in result.scalars().all()]

    async def update_price(self, product_id: UUID, new_price: int) -> None:
        # Record price history
        product_stmt = self._base_query().where(ProductModel.id == product_id)
        result = await self._session.execute(product_stmt)
        product = result.scalar_one_or_none()
        if product:
            price_history = ProductPriceModel(
                product_id=product_id,
                price=product.current_price,
                effective_from=product.updated_at or product.created_at,
                effective_until=datetime.utcnow(),
            )
            self._session.add(price_history)
            product.current_price = new_price
            await self._session.flush()

    async def bulk_update_prices(self, price_updates: list[tuple[UUID, int]]) -> int:
        count = 0
        for product_id, new_price in price_updates:
            await self.update_price(product_id, new_price)
            count += 1
        return count


class InvoiceRepository(SqlAlchemyRepository[InvoiceModel, Invoice], IInvoiceRepository):
    """SQLAlchemy implementation of IInvoiceRepository."""

    def __init__(self, session, tenant_id: UUID):
        super().__init__(session, tenant_id, InvoiceModel)

    def _base_query(self):
        stmt = select(InvoiceModel).options(
            selectinload(InvoiceModel.line_items),
            selectinload(InvoiceModel.payments),
        )
        return stmt.where(InvoiceModel.tenant_id == self._tenant_id)

    def _to_entity(self, model: InvoiceModel) -> Invoice:
        line_items = []
        for li in (model.line_items or []):
            line_items.append(InvoiceLineItem(
                id=li.id,
                tenant_id=model.tenant_id,
                invoice_id=li.invoice_id,
                product_id=li.product_id,
                product_name=li.product_name,
                product_code=li.product_code,
                quantity=li.quantity,
                unit=li.unit,
                unit_price=li.unit_price,
                total_price=li.total,
                metadata=li.metadata_ or {},
            ))

        amount_paid = sum(p.amount for p in (model.payments or []) if p.status == "confirmed")

        return Invoice(
            id=model.id,
            tenant_id=model.tenant_id,
            invoice_number=model.invoice_number,
            contact_id=model.contact_id,
            phone_number=model.phone_number,
            salesperson_id=model.salesperson_id,
            salesperson_name=model.salesperson_name,
            line_items=line_items,
            subtotal=model.subtotal,
            discount_amount=model.discount_amount,
            tax_amount=model.tax_amount,
            total_amount=model.total_amount,
            status=InvoiceStatus(model.status) if model.status else InvoiceStatus.DRAFT,
            issued_at=model.issued_at,
            due_date=model.due_date,
            paid_at=model.paid_at,
            amount_paid=amount_paid,
            external_id=model.external_id,
            notes=model.notes,
            metadata=model.metadata_ or {},
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    def _to_model(self, entity: Invoice) -> InvoiceModel:
        return InvoiceModel(
            id=entity.id,
            tenant_id=entity.tenant_id,
            invoice_number=entity.invoice_number,
            contact_id=entity.contact_id,
            phone_number=entity.phone_number,
            invoice_type="pre_invoice",
            external_id=entity.external_id,
            subtotal=entity.subtotal,
            discount_amount=entity.discount_amount,
            tax_amount=entity.tax_amount,
            total_amount=entity.total_amount,
            status=entity.status.value if hasattr(entity.status, 'value') else entity.status,
            issued_at=entity.issued_at,
            due_date=entity.due_date,
            paid_at=entity.paid_at,
            salesperson_id=entity.salesperson_id,
            salesperson_name=entity.salesperson_name,
            notes=entity.notes,
            metadata_=entity.metadata,
        )

    async def count_by_tenant(self, tenant_id: UUID) -> int:
        stmt = select(func.count()).select_from(InvoiceModel).where(InvoiceModel.tenant_id == tenant_id)
        result = await self._session.execute(stmt)
        return result.scalar_one()

    async def get_by_number(self, invoice_number: str) -> Invoice | None:
        stmt = self._base_query().where(InvoiceModel.invoice_number == invoice_number)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def get_by_phone(self, phone_number: str, skip: int = 0, limit: int = 100) -> list[Invoice]:
        stmt = self._base_query().where(InvoiceModel.phone_number == phone_number).offset(skip).limit(limit)
        result = await self._session.execute(stmt)
        return [self._to_entity(m) for m in result.scalars().unique().all()]

    async def get_by_contact(self, contact_id: UUID, skip: int = 0, limit: int = 100) -> list[Invoice]:
        stmt = self._base_query().where(InvoiceModel.contact_id == contact_id).offset(skip).limit(limit)
        result = await self._session.execute(stmt)
        return [self._to_entity(m) for m in result.scalars().unique().all()]

    async def get_by_salesperson(self, salesperson_id: UUID, skip: int = 0, limit: int = 100) -> list[Invoice]:
        stmt = self._base_query().where(InvoiceModel.salesperson_id == salesperson_id).offset(skip).limit(limit)
        result = await self._session.execute(stmt)
        return [self._to_entity(m) for m in result.scalars().unique().all()]

    async def get_by_status(self, status: str, skip: int = 0, limit: int = 100) -> list[Invoice]:
        stmt = self._base_query().where(InvoiceModel.status == status).offset(skip).limit(limit)
        result = await self._session.execute(stmt)
        return [self._to_entity(m) for m in result.scalars().unique().all()]

    async def get_by_date_range(self, start_date: datetime, end_date: datetime, skip: int = 0, limit: int = 100) -> list[Invoice]:
        stmt = (
            self._base_query()
            .where(InvoiceModel.issued_at >= start_date)
            .where(InvoiceModel.issued_at <= end_date)
            .offset(skip).limit(limit)
        )
        result = await self._session.execute(stmt)
        return [self._to_entity(m) for m in result.scalars().unique().all()]

    async def get_overdue_invoices(self) -> list[Invoice]:
        now = datetime.utcnow()
        stmt = (
            self._base_query()
            .where(InvoiceModel.status.in_(["issued", "partially_paid"]))
            .where(InvoiceModel.due_date < now)
        )
        result = await self._session.execute(stmt)
        return [self._to_entity(m) for m in result.scalars().unique().all()]

    async def get_sales_stats(self, start_date: datetime | None = None, end_date: datetime | None = None, group_by: str | None = None) -> dict[str, Any]:
        base = select(
            func.count().label("total_invoices"),
            func.sum(InvoiceModel.total_amount).label("total_amount"),
            func.count().filter(InvoiceModel.status == "paid").label("paid_count"),
        ).where(InvoiceModel.tenant_id == self._tenant_id)
        if start_date:
            base = base.where(InvoiceModel.issued_at >= start_date)
        if end_date:
            base = base.where(InvoiceModel.issued_at <= end_date)
        result = await self._session.execute(base)
        row = result.one()
        return {
            "total_invoices": row.total_invoices,
            "total_amount": row.total_amount or 0,
            "paid_count": row.paid_count,
        }

    async def get_by_external_id(self, external_id: str) -> Invoice | None:
        stmt = self._base_query().where(InvoiceModel.external_id == external_id)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None


class PaymentRepository(SqlAlchemyRepository[PaymentModel, Payment], IPaymentRepository):
    """SQLAlchemy implementation of IPaymentRepository."""

    def __init__(self, session, tenant_id: UUID):
        super().__init__(session, tenant_id, PaymentModel)

    def _to_entity(self, model: PaymentModel) -> Payment:
        return Payment(
            id=model.id,
            tenant_id=model.tenant_id,
            invoice_id=model.invoice_id,
            contact_id=model.contact_id,
            phone_number=model.phone_number,
            amount=model.amount,
            payment_method=model.payment_method,
            status=PaymentStatus(model.status) if model.status else PaymentStatus.PENDING,
            payment_date=model.paid_at,
            reference_number=model.reference_number,
            external_id=model.external_id,
            notes=model.notes,
            metadata=model.metadata_ or {},
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    def _to_model(self, entity: Payment) -> PaymentModel:
        return PaymentModel(
            id=entity.id,
            tenant_id=entity.tenant_id,
            invoice_id=entity.invoice_id,
            contact_id=entity.contact_id,
            phone_number=entity.phone_number,
            amount=entity.amount,
            payment_method=entity.payment_method,
            status=entity.status.value if hasattr(entity.status, 'value') else entity.status,
            paid_at=entity.payment_date,
            reference_number=entity.reference_number,
            external_id=entity.external_id,
            notes=entity.notes,
            metadata_=entity.metadata,
        )

    async def get_by_invoice(self, invoice_id: UUID) -> list[Payment]:
        stmt = self._base_query().where(PaymentModel.invoice_id == invoice_id)
        result = await self._session.execute(stmt)
        return [self._to_entity(m) for m in result.scalars().all()]

    async def get_by_phone(self, phone_number: str, skip: int = 0, limit: int = 100) -> list[Payment]:
        stmt = self._base_query().where(PaymentModel.phone_number == phone_number).order_by(PaymentModel.paid_at.desc()).offset(skip).limit(limit)
        result = await self._session.execute(stmt)
        return [self._to_entity(m) for m in result.scalars().all()]

    async def get_by_date_range(self, start_date: datetime, end_date: datetime, skip: int = 0, limit: int = 100) -> list[Payment]:
        stmt = (
            self._base_query()
            .where(PaymentModel.paid_at >= start_date)
            .where(PaymentModel.paid_at <= end_date)
            .order_by(PaymentModel.paid_at.desc())
            .offset(skip).limit(limit)
        )
        result = await self._session.execute(stmt)
        return [self._to_entity(m) for m in result.scalars().all()]

    async def get_payment_stats(self, start_date: datetime | None = None, end_date: datetime | None = None) -> dict[str, Any]:
        base = select(
            func.count().label("total"),
            func.sum(PaymentModel.amount).label("total_amount"),
        ).where(PaymentModel.tenant_id == self._tenant_id).where(PaymentModel.status == "confirmed")
        if start_date:
            base = base.where(PaymentModel.paid_at >= start_date)
        if end_date:
            base = base.where(PaymentModel.paid_at <= end_date)
        result = await self._session.execute(base)
        row = result.one()
        return {"total_payments": row.total, "total_amount": row.total_amount or 0}

    async def get_by_external_id(self, external_id: str) -> Payment | None:
        stmt = self._base_query().where(PaymentModel.external_id == external_id)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

