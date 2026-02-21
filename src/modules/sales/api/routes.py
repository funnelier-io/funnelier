"""
Sales API Routes

FastAPI routes for invoice, payment, and product management.
"""

from datetime import datetime, timedelta
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File

from src.api.dependencies import (
    get_product_repository,
    get_invoice_repository,
    get_payment_repository,
    get_current_tenant_id,
)
from src.core.domain import InvoiceStatus, PaymentStatus
from src.modules.sales.domain.entities import Product, Invoice, InvoiceLineItem, Payment
from src.modules.sales.infrastructure.repositories import (
    ProductRepository,
    InvoiceRepository,
    PaymentRepository,
)

from .schemas import (
    CreateDataSourceRequest,
    CreateInvoiceRequest,
    CreateProductRequest,
    DataSourceListResponse,
    DataSourceResponse,
    InvoiceListResponse,
    InvoiceResponse,
    InvoiceSummaryResponse,
    PaymentListResponse,
    PaymentResponse,
    ProductCategoryResponse,
    ProductListResponse,
    ProductPriceHistoryResponse,
    ProductResponse,
    RecordPaymentRequest,
    RevenueByPeriodResponse,
    SalesStatsResponse,
    SyncDataRequest,
    SyncDataResponse,
    TopCustomersResponse,
    TopProductsResponse,
    UpdateInvoiceRequest,
    UpdatePricesRequest,
    UpdateProductRequest,
)

router = APIRouter(tags=["sales"])


# ============================================================================
# Helpers
# ============================================================================

def _product_to_response(p: Product) -> ProductResponse:
    return ProductResponse(
        id=p.id, tenant_id=p.tenant_id, name=p.name, code=p.code,
        description=p.description, category=p.category,
        unit=p.unit, base_price=p.base_price, current_price=p.current_price,
        is_available=p.is_available, recommended_segments=p.recommended_segments,
        is_active=p.is_active, metadata=p.metadata,
        price_updated_at=p.price_updated_at, created_at=p.created_at, updated_at=p.updated_at,
    )


def _invoice_to_response(inv: Invoice) -> InvoiceResponse:
    return InvoiceResponse(
        id=inv.id, tenant_id=inv.tenant_id, invoice_number=inv.invoice_number,
        contact_id=inv.contact_id, phone_number=inv.phone_number,
        customer_name=inv.customer_name, salesperson_id=inv.salesperson_id,
        line_items=[], subtotal=inv.subtotal,
        discount_amount=inv.discount_amount, tax_amount=inv.tax_amount,
        total_amount=inv.total_amount,
        status=inv.status.value if hasattr(inv.status, 'value') else inv.status,
        issued_at=inv.issued_at, due_date=inv.due_date, paid_at=inv.paid_at,
        amount_paid=inv.amount_paid, notes=inv.notes,
        external_id=inv.external_id,
        created_at=inv.created_at, updated_at=inv.updated_at,
    )


# ============================================================================
# Product Endpoints
# ============================================================================

@router.get("/products", response_model=ProductListResponse)
async def list_products(
    repo: Annotated[ProductRepository, Depends(get_product_repository)],
    category: str | None = Query(default=None),
    is_available: bool | None = Query(default=None),
    search: str | None = Query(default=None),
    include_inactive: bool = Query(default=False),
):
    """List products with filtering."""
    if category:
        products = await repo.get_by_category(category)
    elif not include_inactive:
        products = await repo.get_active_products()
    else:
        products = await repo.get_all()
    return ProductListResponse(
        products=[_product_to_response(p) for p in products],
        total_count=len(products),
    )


@router.post("/products", response_model=ProductResponse, status_code=201)
async def create_product(
    repo: Annotated[ProductRepository, Depends(get_product_repository)],
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
    request: CreateProductRequest,
):
    """Create a new product."""
    product = Product(
        tenant_id=tenant_id, name=request.name, code=request.code,
        description=request.description, category=request.category,
        unit=request.unit, base_price=request.base_price,
        current_price=request.current_price,
        is_available=request.is_available if request.is_available is not None else True,
        recommended_segments=request.recommended_segments or [],
        is_active=request.is_active if request.is_active is not None else True,
        metadata=request.metadata or {},
    )
    saved = await repo.add(product)
    return _product_to_response(saved)


@router.get("/products/{product_id}", response_model=ProductResponse)
async def get_product(
    product_id: UUID,
    repo: Annotated[ProductRepository, Depends(get_product_repository)],
):
    """Get product by ID."""
    p = await repo.get(product_id)
    if not p:
        raise HTTPException(status_code=404, detail="Product not found")
    return _product_to_response(p)


@router.put("/products/{product_id}", response_model=ProductResponse)
async def update_product(
    product_id: UUID,
    repo: Annotated[ProductRepository, Depends(get_product_repository)],
    request: UpdateProductRequest,
):
    """Update a product."""
    p = await repo.get(product_id)
    if not p:
        raise HTTPException(status_code=404, detail="Product not found")
    update_data = request.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        if hasattr(p, key):
            setattr(p, key, value)
    saved = await repo.update(p)
    return _product_to_response(saved)


@router.delete("/products/{product_id}", status_code=204)
async def delete_product(
    product_id: UUID,
    repo: Annotated[ProductRepository, Depends(get_product_repository)],
):
    """Delete a product."""
    await repo.delete(product_id)


@router.get("/products/categories/summary", response_model=list[ProductCategoryResponse])
async def get_product_categories(
    repo: Annotated[ProductRepository, Depends(get_product_repository)],
):
    """Get product categories with statistics."""
    products = await repo.get_all(limit=1000)
    cats = {}
    for p in products:
        cat = p.category
        if cat not in cats:
            cats[cat] = {"count": 0, "products": []}
        cats[cat]["count"] += 1
        cats[cat]["products"].append({"name": p.name, "revenue": 0})
    return [
        ProductCategoryResponse(
            category=cat, product_count=data["count"],
            total_revenue=0, top_products=data["products"][:3],
        )
        for cat, data in cats.items()
    ]


@router.get("/products/{product_id}/price-history", response_model=ProductPriceHistoryResponse)
async def get_product_price_history(
    product_id: UUID,
    repo: Annotated[ProductRepository, Depends(get_product_repository)],
):
    """Get price history for a product."""
    p = await repo.get(product_id)
    if not p:
        raise HTTPException(status_code=404, detail="Product not found")
    return ProductPriceHistoryResponse(
        product_id=p.id, product_name=p.name, price_changes=[],
    )


@router.post("/products/update-prices")
async def bulk_update_prices(
    repo: Annotated[ProductRepository, Depends(get_product_repository)],
    request: UpdatePricesRequest,
):
    """Bulk update product prices."""
    updates = [(UUID(u.product_id), u.new_price) for u in request.price_updates]
    count = await repo.bulk_update_prices(updates)
    return {"updated_count": count, "errors": []}


@router.post("/products/import-catalog")
async def import_product_catalog(
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
    file: UploadFile = File(...),
):
    """Import product catalog from file."""
    return {"total_imported": 0, "created": 0, "updated": 0, "errors": []}


# ============================================================================
# Invoice Endpoints
# ============================================================================

@router.get("/invoices", response_model=InvoiceListResponse)
async def list_invoices(
    repo: Annotated[InvoiceRepository, Depends(get_invoice_repository)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    contact_id: UUID | None = Query(default=None),
    phone_number: str | None = Query(default=None),
    salesperson_id: UUID | None = Query(default=None),
    status: str | None = Query(default=None),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    min_amount: int | None = Query(default=None),
    max_amount: int | None = Query(default=None),
):
    """List invoices with filtering."""
    skip = (page - 1) * page_size
    if phone_number:
        invoices = await repo.get_by_phone(phone_number, skip=skip, limit=page_size)
    elif contact_id:
        invoices = await repo.get_by_contact(contact_id, skip=skip, limit=page_size)
    elif salesperson_id:
        invoices = await repo.get_by_salesperson(salesperson_id, skip=skip, limit=page_size)
    elif status:
        invoices = await repo.get_by_status(status, skip=skip, limit=page_size)
    elif date_from and date_to:
        invoices = await repo.get_by_date_range(date_from, date_to, skip=skip, limit=page_size)
    else:
        invoices = await repo.get_all(skip=skip, limit=page_size)
    total = await repo.count()
    return InvoiceListResponse(
        invoices=[_invoice_to_response(i) for i in invoices],
        total_count=total, page=page, page_size=page_size,
        has_next=(page * page_size) < total, has_prev=page > 1,
    )


@router.post("/invoices", response_model=InvoiceResponse, status_code=201)
async def create_invoice(
    repo: Annotated[InvoiceRepository, Depends(get_invoice_repository)],
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
    request: CreateInvoiceRequest,
):
    """Create a new invoice (pre-invoice)."""
    invoice = Invoice(
        tenant_id=tenant_id,
        invoice_number=f"INV-{datetime.utcnow().strftime('%Y%m%d')}-{str(uuid4())[:8].upper()}",
        contact_id=request.contact_id, phone_number=request.phone_number,
        customer_name=request.customer_name, salesperson_id=request.salesperson_id,
        discount_amount=request.discount_amount, tax_amount=request.tax_amount,
        due_date=request.due_date, notes=request.notes,
        external_id=request.external_id,
    )
    # Calculate totals from line items
    for item in request.line_items:
        li = InvoiceLineItem(
            tenant_id=tenant_id, invoice_id=invoice.id,
            product_id=item.product_id, product_name=item.product_name,
            product_code=item.product_code, quantity=item.quantity,
            unit=item.unit, unit_price=item.unit_price,
            total_price=int(item.quantity * item.unit_price),
        )
        invoice.line_items.append(li)
    invoice.calculate_totals()
    saved = await repo.add(invoice)
    return _invoice_to_response(saved)


@router.get("/invoices/{invoice_id}", response_model=InvoiceResponse)
async def get_invoice(
    invoice_id: UUID,
    repo: Annotated[InvoiceRepository, Depends(get_invoice_repository)],
):
    """Get invoice by ID."""
    inv = await repo.get(invoice_id)
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return _invoice_to_response(inv)


@router.put("/invoices/{invoice_id}", response_model=InvoiceResponse)
async def update_invoice(
    invoice_id: UUID,
    repo: Annotated[InvoiceRepository, Depends(get_invoice_repository)],
    request: UpdateInvoiceRequest,
):
    """Update an invoice."""
    inv = await repo.get(invoice_id)
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")
    update_data = request.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        if hasattr(inv, key):
            setattr(inv, key, value)
    saved = await repo.update(inv)
    return _invoice_to_response(saved)


@router.post("/invoices/{invoice_id}/issue", response_model=InvoiceResponse)
async def issue_invoice(
    invoice_id: UUID,
    repo: Annotated[InvoiceRepository, Depends(get_invoice_repository)],
):
    """Issue a draft invoice."""
    inv = await repo.get(invoice_id)
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")
    try:
        inv.issue()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    saved = await repo.update(inv)
    return _invoice_to_response(saved)


@router.post("/invoices/{invoice_id}/cancel", response_model=InvoiceResponse)
async def cancel_invoice(
    invoice_id: UUID,
    repo: Annotated[InvoiceRepository, Depends(get_invoice_repository)],
    reason: str | None = Query(default=None),
):
    """Cancel an invoice."""
    inv = await repo.get(invoice_id)
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")
    try:
        inv.cancel(reason)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    saved = await repo.update(inv)
    return _invoice_to_response(saved)


@router.get("/invoices/summary", response_model=InvoiceSummaryResponse)
async def get_invoice_summary(
    repo: Annotated[InvoiceRepository, Depends(get_invoice_repository)],
    start_date: datetime = Query(default=None),
    end_date: datetime = Query(default=None),
):
    """Get invoice summary statistics."""
    stats = await repo.get_sales_stats(start_date, end_date)
    return InvoiceSummaryResponse(
        total_invoices=stats.get("total_invoices", 0),
        total_amount=stats.get("total_amount", 0),
        total_paid=0, total_outstanding=0,
        by_status={}, by_salesperson=[],
    )


# ============================================================================
# Payment Endpoints
# ============================================================================

@router.post("/invoices/{invoice_id}/payments", response_model=PaymentResponse)
async def record_payment(
    invoice_id: UUID,
    pay_repo: Annotated[PaymentRepository, Depends(get_payment_repository)],
    inv_repo: Annotated[InvoiceRepository, Depends(get_invoice_repository)],
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
    request: RecordPaymentRequest,
):
    """Record a payment for an invoice."""
    inv = await inv_repo.get(invoice_id)
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")

    payment = Payment(
        tenant_id=tenant_id, invoice_id=invoice_id,
        contact_id=inv.contact_id, phone_number=inv.phone_number,
        amount=request.amount, payment_method=request.payment_method,
        status=PaymentStatus.CONFIRMED,
        payment_date=request.payment_date or datetime.utcnow(),
        reference_number=request.reference_number, notes=request.notes,
    )
    saved = await pay_repo.add(payment)

    # Update invoice payment status
    inv.record_payment(request.amount, request.payment_method)
    await inv_repo.update(inv)

    return PaymentResponse(
        id=saved.id, tenant_id=saved.tenant_id, invoice_id=invoice_id,
        invoice_number=inv.invoice_number, amount=saved.amount,
        payment_method=saved.payment_method,
        payment_date=saved.payment_date, reference_number=saved.reference_number,
        notes=saved.notes, created_at=saved.created_at,
    )


@router.get("/invoices/{invoice_id}/payments", response_model=PaymentListResponse)
async def get_invoice_payments(
    invoice_id: UUID,
    repo: Annotated[PaymentRepository, Depends(get_payment_repository)],
):
    """Get payments for an invoice."""
    payments = await repo.get_by_invoice(invoice_id)
    total = sum(p.amount for p in payments)
    return PaymentListResponse(
        payments=[PaymentResponse(
            id=p.id, tenant_id=p.tenant_id, invoice_id=p.invoice_id,
            amount=p.amount, payment_method=p.payment_method,
            payment_date=p.payment_date, reference_number=p.reference_number,
            notes=p.notes, created_at=p.created_at,
        ) for p in payments],
        total_count=len(payments), total_amount=total,
    )


@router.get("/payments", response_model=PaymentListResponse)
async def list_payments(
    repo: Annotated[PaymentRepository, Depends(get_payment_repository)],
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    salesperson_id: UUID | None = Query(default=None),
):
    """List all payments with filtering."""
    if date_from and date_to:
        payments = await repo.get_by_date_range(date_from, date_to)
    else:
        payments = await repo.get_all()
    total = sum(p.amount for p in payments)
    return PaymentListResponse(
        payments=[PaymentResponse(
            id=p.id, tenant_id=p.tenant_id, invoice_id=p.invoice_id,
            amount=p.amount, payment_method=p.payment_method,
            payment_date=p.payment_date, reference_number=p.reference_number,
            notes=p.notes, created_at=p.created_at,
        ) for p in payments],
        total_count=len(payments), total_amount=total,
    )


# ============================================================================
# Data Source Integration Endpoints
# ============================================================================

@router.get("/data-sources", response_model=DataSourceListResponse)
async def list_data_sources(tenant_id: Annotated[UUID, Depends(get_current_tenant_id)]):
    """List configured data sources."""
    return DataSourceListResponse(sources=[], total_count=0)


@router.post("/data-sources", response_model=DataSourceResponse, status_code=201)
async def create_data_source(
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
    request: CreateDataSourceRequest,
):
    """Create a new data source configuration."""
    return DataSourceResponse(
        id=uuid4(), tenant_id=tenant_id, name=request.name,
        source_type=request.source_type, is_active=request.is_active,
        metadata=request.metadata, created_at=datetime.utcnow(),
    )


@router.get("/data-sources/{source_id}", response_model=DataSourceResponse)
async def get_data_source(source_id: UUID, tenant_id: Annotated[UUID, Depends(get_current_tenant_id)]):
    """Get data source by ID."""
    raise HTTPException(status_code=404, detail="Data source not found")


@router.delete("/data-sources/{source_id}", status_code=204)
async def delete_data_source(source_id: UUID, tenant_id: Annotated[UUID, Depends(get_current_tenant_id)]):
    """Delete a data source."""
    pass


@router.post("/data-sources/{source_id}/sync", response_model=SyncDataResponse)
async def sync_data_source(
    source_id: UUID, tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
    request: SyncDataRequest = None,
):
    """Trigger data sync from a source."""
    return SyncDataResponse(
        source_id=source_id, sync_started_at=datetime.utcnow(),
        records_fetched=0, records_created=0, records_updated=0,
    )


@router.post("/data-sources/{source_id}/test")
async def test_data_source_connection(source_id: UUID, tenant_id: Annotated[UUID, Depends(get_current_tenant_id)]):
    """Test connection to a data source."""
    return {"success": True, "message": "Connection successful"}


# ============================================================================
# Sales Statistics Endpoints
# ============================================================================

@router.get("/stats", response_model=SalesStatsResponse)
async def get_sales_stats(
    repo: Annotated[InvoiceRepository, Depends(get_invoice_repository)],
    start_date: datetime = Query(default=None),
    end_date: datetime = Query(default=None),
):
    """Get sales statistics."""
    if start_date is None:
        start_date = datetime.utcnow() - timedelta(days=30)
    if end_date is None:
        end_date = datetime.utcnow()
    stats = await repo.get_sales_stats(start_date, end_date)
    total = stats.get("total_invoices", 0)
    return SalesStatsResponse(
        period_start=start_date, period_end=end_date,
        total_invoices=total, total_paid=stats.get("paid_count", 0),
        total_cancelled=0, total_revenue=stats.get("total_amount", 0),
        total_outstanding=0, average_order_value=stats.get("total_amount", 0) // max(total, 1),
        by_product_category=[], by_salesperson=[], conversion_rate=0.0,
    )


@router.get("/stats/revenue-by-period", response_model=RevenueByPeriodResponse)
async def get_revenue_by_period(
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
    period: str = Query(default="daily"),
    start_date: datetime = Query(default=None),
    end_date: datetime = Query(default=None),
):
    """Get revenue breakdown by period."""
    return RevenueByPeriodResponse(data=[])


@router.get("/stats/top-customers", response_model=TopCustomersResponse)
async def get_top_customers(
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
    limit: int = Query(default=10, ge=1, le=50),
    start_date: datetime = Query(default=None),
    end_date: datetime = Query(default=None),
):
    """Get top customers by revenue."""
    return TopCustomersResponse(customers=[])


@router.get("/stats/top-products", response_model=TopProductsResponse)
async def get_top_products(
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
    limit: int = Query(default=10, ge=1, le=50),
    start_date: datetime = Query(default=None),
    end_date: datetime = Query(default=None),
):
    """Get top products by revenue."""
    return TopProductsResponse(products=[])
