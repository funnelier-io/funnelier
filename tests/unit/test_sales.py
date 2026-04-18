"""
Tests for Sales Module — Sprint 1 P0 Gap Closure.

Covers:
- Product, InvoiceLineItem, Invoice, Payment domain entities
- Invoice lifecycle (issue, record_payment, cancel)
- InvoiceService (with mocked repos)
- ProductService (create, update_price, bulk_update)
- API schemas validation
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

from src.core.domain import (
    InvoiceStatus,
    PaymentStatus,
    InvoiceCreatedEvent,
    InvoicePaidEvent,
    InvoiceCancelledEvent,
)
from src.modules.sales.domain.entities import (
    Product,
    InvoiceLineItem,
    Invoice,
    Payment,
)
from src.modules.sales.application.services import InvoiceService, ProductService
from src.modules.sales.api.schemas import (
    CreateProductRequest,
    UpdateProductRequest,
    ProductResponse,
    ProductListResponse,
    UpdatePricesRequest,
    CreateInvoiceRequest,
    CreateLineItemRequest,
    InvoiceResponse,
    InvoiceListResponse,
    InvoiceSummaryResponse,
    RecordPaymentRequest,
    PaymentResponse,
    SalesStatsResponse,
    CreateDataSourceRequest,
)

TENANT_ID = UUID("00000000-0000-0000-0000-000000000001")


# ═══════════════════════════════════════════════════════════════════
# Product Entity
# ═══════════════════════════════════════════════════════════════════


class TestProductEntity:
    def test_basic_creation(self):
        p = Product(
            tenant_id=TENANT_ID,
            name="سیمان تیپ ۲",
            category="سیمان",
            unit="ton",
            base_price=5_000_000,
            current_price=5_500_000,
        )
        assert p.name == "سیمان تیپ ۲"
        assert p.category == "سیمان"
        assert p.is_active is True
        assert p.is_available is True

    def test_default_values(self):
        p = Product(tenant_id=TENANT_ID, name="Test", category="Test")
        assert p.unit == "ton"
        assert p.base_price == 0
        assert p.specifications == {}
        assert p.tags == []
        assert p.recommended_segments == []

    def test_with_specifications(self):
        p = Product(
            tenant_id=TENANT_ID,
            name="بلوک سبک",
            category="بلوک",
            specifications={"weight": "10kg", "size": "20x40"},
        )
        assert p.specifications["weight"] == "10kg"


# ═══════════════════════════════════════════════════════════════════
# InvoiceLineItem Entity
# ═══════════════════════════════════════════════════════════════════


class TestInvoiceLineItem:
    def test_creation(self):
        item = InvoiceLineItem(
            tenant_id=TENANT_ID,
            invoice_id=uuid4(),
            product_name="سیمان",
            quantity=10.0,
            unit="ton",
            unit_price=5_000_000,
            total_price=50_000_000,
        )
        assert item.quantity == 10.0
        assert item.total_price == 50_000_000

    def test_with_discount_and_tax(self):
        item = InvoiceLineItem(
            tenant_id=TENANT_ID,
            invoice_id=uuid4(),
            product_name="بتن",
            quantity=5.0,
            unit="m3",
            unit_price=3_000_000,
            total_price=15_000_000,
            discount_amount=500_000,
            tax_amount=1_350_000,
        )
        assert item.discount_amount == 500_000
        assert item.tax_amount == 1_350_000


# ═══════════════════════════════════════════════════════════════════
# Invoice Entity
# ═══════════════════════════════════════════════════════════════════


class TestInvoiceEntity:
    def _make_invoice(self, **kwargs) -> Invoice:
        defaults = dict(
            tenant_id=TENANT_ID,
            invoice_number="INV-20260418-00001",
            phone_number="9121234567",
            customer_name="Test Customer",
            total_amount=10_000_000,
        )
        defaults.update(kwargs)
        return Invoice(**defaults)

    def test_basic_creation(self):
        inv = self._make_invoice()
        assert inv.status == InvoiceStatus.DRAFT
        assert inv.total_amount == 10_000_000
        assert inv.amount_paid == 0

    def test_calculate_totals(self):
        items = [
            InvoiceLineItem(
                tenant_id=TENANT_ID,
                invoice_id=uuid4(),
                product_name="A",
                quantity=1,
                unit="unit",
                unit_price=5_000_000,
                total_price=5_000_000,
            ),
            InvoiceLineItem(
                tenant_id=TENANT_ID,
                invoice_id=uuid4(),
                product_name="B",
                quantity=2,
                unit="unit",
                unit_price=3_000_000,
                total_price=6_000_000,
            ),
        ]
        inv = self._make_invoice(line_items=items, discount_amount=1_000_000, tax_amount=500_000)
        inv.calculate_totals()
        assert inv.subtotal == 11_000_000
        assert inv.total_amount == 11_000_000 - 1_000_000 + 500_000

    def test_issue_from_draft(self):
        inv = self._make_invoice()
        inv.issue()
        assert inv.status == InvoiceStatus.ISSUED
        assert inv.issued_at is not None
        events = [e for e in inv.domain_events if isinstance(e, InvoiceCreatedEvent)]
        assert len(events) == 1

    def test_issue_non_draft_raises(self):
        inv = self._make_invoice(status=InvoiceStatus.ISSUED)
        with pytest.raises(ValueError, match="Cannot issue"):
            inv.issue()

    def test_record_full_payment(self):
        inv = self._make_invoice(status=InvoiceStatus.ISSUED, total_amount=10_000_000)
        inv.record_payment(10_000_000, "card")
        assert inv.status == InvoiceStatus.PAID
        assert inv.paid_at is not None
        assert inv.payment_method == "card"
        events = [e for e in inv.domain_events if isinstance(e, InvoicePaidEvent)]
        assert len(events) == 1

    def test_record_partial_payment(self):
        inv = self._make_invoice(total_amount=10_000_000)
        inv.record_payment(5_000_000)
        assert inv.status == InvoiceStatus.PARTIAL_PAID
        assert inv.amount_paid == 5_000_000
        assert inv.paid_at is None

    def test_record_payment_completes_partial(self):
        inv = self._make_invoice(total_amount=10_000_000, amount_paid=5_000_000,
                                 status=InvoiceStatus.PARTIAL_PAID)
        inv.record_payment(5_000_000, "transfer")
        assert inv.status == InvoiceStatus.PAID

    def test_cancel_invoice(self):
        inv = self._make_invoice()
        inv.cancel("مشتری انصراف داد")
        assert inv.status == InvoiceStatus.CANCELLED
        assert inv.cancelled_at is not None
        assert inv.cancellation_reason == "مشتری انصراف داد"

    def test_cancel_paid_invoice_raises(self):
        inv = self._make_invoice(status=InvoiceStatus.PAID)
        with pytest.raises(ValueError, match="Cannot cancel a paid"):
            inv.cancel()

    def test_is_overdue_false_when_paid(self):
        inv = self._make_invoice(status=InvoiceStatus.PAID, due_date=datetime(2020, 1, 1))
        assert inv.is_overdue is False

    def test_is_overdue_false_no_due_date(self):
        inv = self._make_invoice(status=InvoiceStatus.ISSUED)
        assert inv.is_overdue is False

    def test_is_overdue_true(self):
        inv = self._make_invoice(
            status=InvoiceStatus.ISSUED,
            due_date=datetime(2020, 1, 1),
        )
        assert inv.is_overdue is True

    def test_remaining_amount(self):
        inv = self._make_invoice(total_amount=10_000_000, amount_paid=3_000_000)
        assert inv.remaining_amount == 7_000_000

    def test_remaining_amount_never_negative(self):
        inv = self._make_invoice(total_amount=10_000_000, amount_paid=15_000_000)
        assert inv.remaining_amount == 0


# ═══════════════════════════════════════════════════════════════════
# Payment Entity
# ═══════════════════════════════════════════════════════════════════


class TestPaymentEntity:
    def test_creation(self):
        p = Payment(
            tenant_id=TENANT_ID,
            phone_number="9121234567",
            amount=5_000_000,
            payment_method="cash",
            status=PaymentStatus.COMPLETED,
            payment_date=datetime.utcnow(),
        )
        assert p.amount == 5_000_000
        assert p.status == PaymentStatus.COMPLETED

    def test_pending_default(self):
        p = Payment(
            tenant_id=TENANT_ID,
            phone_number="9121234567",
            amount=1_000_000,
            payment_method="transfer",
            payment_date=datetime.utcnow(),
        )
        assert p.status == PaymentStatus.PENDING


# ═══════════════════════════════════════════════════════════════════
# InvoiceService (Application Layer)
# ═══════════════════════════════════════════════════════════════════


class TestInvoiceService:
    def _make_service(self):
        invoice_repo = AsyncMock()
        product_repo = AsyncMock()
        contact_repo = AsyncMock()
        svc = InvoiceService(invoice_repo, product_repo, contact_repo)
        return svc, invoice_repo, product_repo, contact_repo

    @pytest.mark.asyncio
    async def test_create_invoice(self):
        svc, invoice_repo, _, contact_repo = self._make_service()
        invoice_repo.count_by_tenant.return_value = 0
        contact_repo.get.return_value = None

        result = await svc.create_invoice(
            tenant_id=TENANT_ID,
            phone_number="9121234567",
            line_items=[
                {
                    "product_name": "سیمان",
                    "quantity": 10,
                    "unit_price": 5_000_000,
                    "unit": "ton",
                },
            ],
        )
        assert result.invoice_number.startswith("INV-")
        assert result.total_amount == 50_000_000
        invoice_repo.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_invoice_with_discount_and_tax(self):
        svc, invoice_repo, _, contact_repo = self._make_service()
        invoice_repo.count_by_tenant.return_value = 5
        contact_repo.get.return_value = None

        result = await svc.create_invoice(
            tenant_id=TENANT_ID,
            phone_number="9121234567",
            line_items=[
                {"product_name": "بتن", "quantity": 5, "unit_price": 3_000_000, "unit": "m3"},
            ],
            discount_amount=500_000,
            tax_amount=1_350_000,
        )
        # subtotal = 15_000_000, total = 15M - 500K + 1.35M = 15_850_000
        assert result.total_amount == 15_850_000

    @pytest.mark.asyncio
    async def test_issue_invoice(self):
        svc, invoice_repo, _, _ = self._make_service()
        inv = Invoice(
            tenant_id=TENANT_ID,
            invoice_number="INV-001",
            phone_number="9121234567",
            total_amount=10_000_000,
        )
        invoice_repo.get.return_value = inv

        result = await svc.issue_invoice(inv.id)
        assert result.status == InvoiceStatus.ISSUED
        invoice_repo.update.assert_called_once()

    @pytest.mark.asyncio
    async def test_issue_nonexistent_invoice_raises(self):
        svc, invoice_repo, _, _ = self._make_service()
        invoice_repo.get.return_value = None

        with pytest.raises(ValueError, match="not found"):
            await svc.issue_invoice(uuid4())

    @pytest.mark.asyncio
    async def test_record_payment(self):
        svc, invoice_repo, _, contact_repo = self._make_service()
        inv = Invoice(
            tenant_id=TENANT_ID,
            invoice_number="INV-001",
            phone_number="9121234567",
            total_amount=10_000_000,
            status=InvoiceStatus.ISSUED,
        )
        invoice_repo.get.return_value = inv

        result = await svc.record_payment(inv.id, 10_000_000, "card")
        assert result.status == InvoiceStatus.PAID
        invoice_repo.update.assert_called_once()

    @pytest.mark.asyncio
    async def test_cancel_invoice(self):
        svc, invoice_repo, _, _ = self._make_service()
        inv = Invoice(
            tenant_id=TENANT_ID,
            invoice_number="INV-001",
            phone_number="9121234567",
            total_amount=5_000_000,
        )
        invoice_repo.get.return_value = inv

        result = await svc.cancel_invoice(inv.id, "مشتری لغو کرد")
        assert result.status == InvoiceStatus.CANCELLED
        assert result.cancellation_reason == "مشتری لغو کرد"


# ═══════════════════════════════════════════════════════════════════
# ProductService
# ═══════════════════════════════════════════════════════════════════


class TestProductService:
    def _make_service(self):
        repo = AsyncMock()
        return ProductService(repo), repo

    @pytest.mark.asyncio
    async def test_create_product(self):
        svc, repo = self._make_service()
        p = await svc.create_product(
            tenant_id=TENANT_ID,
            name="سیمان تیپ ۲",
            category="سیمان",
            unit="ton",
            base_price=5_000_000,
            current_price=5_500_000,
        )
        assert p.name == "سیمان تیپ ۲"
        assert p.current_price == 5_500_000
        repo.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_product_defaults_current_to_base(self):
        svc, repo = self._make_service()
        p = await svc.create_product(
            tenant_id=TENANT_ID,
            name="بلوک",
            category="بلوک",
            base_price=2_000_000,
        )
        assert p.current_price == 2_000_000

    @pytest.mark.asyncio
    async def test_update_price(self):
        svc, repo = self._make_service()
        existing = Product(
            tenant_id=TENANT_ID,
            name="سیمان",
            category="سیمان",
            current_price=5_000_000,
        )
        repo.get.return_value = existing

        result = await svc.update_price(existing.id, 6_000_000)
        assert result.current_price == 6_000_000
        assert result.price_updated_at is not None

    @pytest.mark.asyncio
    async def test_update_price_nonexistent_raises(self):
        svc, repo = self._make_service()
        repo.get.return_value = None

        with pytest.raises(ValueError, match="not found"):
            await svc.update_price(uuid4(), 100)

    @pytest.mark.asyncio
    async def test_bulk_update_prices(self):
        svc, repo = self._make_service()
        p1 = Product(tenant_id=TENANT_ID, name="A", category="X", current_price=100)
        p2 = Product(tenant_id=TENANT_ID, name="B", category="X", current_price=200)
        repo.get.side_effect = [p1, p2]

        updated, errors = await svc.bulk_update_prices([
            {"product_id": str(p1.id), "new_price": 150},
            {"product_id": str(p2.id), "new_price": 250},
        ])
        assert updated == 2
        assert len(errors) == 0

    @pytest.mark.asyncio
    async def test_bulk_update_prices_invalid_entry(self):
        svc, repo = self._make_service()
        updated, errors = await svc.bulk_update_prices([
            {"product_id": None, "new_price": None},
        ])
        assert updated == 0
        assert len(errors) == 1

    @pytest.mark.asyncio
    async def test_get_products_for_segment(self):
        svc, repo = self._make_service()
        repo.get_by_segment.return_value = [
            Product(tenant_id=TENANT_ID, name="سیمان", category="سیمان"),
        ]
        result = await svc.get_products_for_segment("champions")
        assert len(result) == 1


# ═══════════════════════════════════════════════════════════════════
# Sales API Schemas
# ═══════════════════════════════════════════════════════════════════


class TestSalesSchemas:
    def test_create_product_request(self):
        req = CreateProductRequest(name="سیمان", category="سیمان")
        assert req.unit == "ton"
        assert req.is_active is True

    def test_update_product_all_optional(self):
        req = UpdateProductRequest()
        assert req.name is None

    def test_update_prices_request(self):
        req = UpdatePricesRequest(
            price_updates=[
                {"product_id": str(uuid4()), "new_price": 5_000_000},
            ]
        )
        assert len(req.price_updates) == 1

    def test_create_invoice_request(self):
        req = CreateInvoiceRequest(
            phone_number="9121234567",
            line_items=[
                CreateLineItemRequest(
                    product_name="سیمان",
                    quantity=10,
                    unit="ton",
                    unit_price=5_000_000,
                ),
            ],
        )
        assert len(req.line_items) == 1
        assert req.discount_amount == 0

    def test_record_payment_request(self):
        req = RecordPaymentRequest(amount=5_000_000, payment_method="card")
        assert req.amount == 5_000_000

    def test_invoice_summary_response(self):
        resp = InvoiceSummaryResponse(
            total_invoices=100,
            total_amount=500_000_000,
            total_paid=300_000_000,
            total_outstanding=200_000_000,
            by_status={"paid": 60, "issued": 40},
            by_salesperson=[],
        )
        assert resp.total_outstanding == 200_000_000

    def test_sales_stats_response(self):
        now = datetime.utcnow()
        resp = SalesStatsResponse(
            period_start=now - timedelta(days=30),
            period_end=now,
            total_invoices=50,
            total_paid=30,
            total_cancelled=5,
            total_revenue=150_000_000,
            total_outstanding=50_000_000,
            average_order_value=3_000_000,
            by_product_category=[],
            by_salesperson=[],
            conversion_rate=0.6,
        )
        assert resp.conversion_rate == 0.6

    def test_data_source_request(self):
        req = CreateDataSourceRequest(
            name="MongoDB CRM",
            source_type="mongodb",
            connection_string="mongodb://localhost:27017",
            database_name="crm",
            collection_name="invoices",
        )
        assert req.source_type == "mongodb"
        assert req.sync_interval_minutes == 60

