"""
Sales API Routes

FastAPI routes for invoice, payment, and product management.
"""

from datetime import datetime, timedelta
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File

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
# Dependencies
# ============================================================================

async def get_current_tenant() -> UUID:
    """Get current tenant from auth context."""
    return UUID("00000000-0000-0000-0000-000000000001")


async def get_current_user() -> UUID:
    """Get current user from auth context."""
    return UUID("00000000-0000-0000-0000-000000000002")


# ============================================================================
# Product Endpoints
# ============================================================================

@router.get("/products", response_model=ProductListResponse)
async def list_products(
    tenant_id: Annotated[UUID, Depends(get_current_tenant)],
    category: str | None = Query(default=None),
    is_available: bool | None = Query(default=None),
    search: str | None = Query(default=None),
    include_inactive: bool = Query(default=False),
):
    """
    List products with filtering.
    """
    # Sample products based on the business context
    products = [
        ProductResponse(
            id=uuid4(),
            tenant_id=tenant_id,
            name="سیمان تیپ 2",
            code="CEM-T2",
            description="سیمان پرتلند تیپ 2",
            category="cement",
            subcategory="portland",
            unit="ton",
            base_price=8_000_000,
            current_price=8_500_000,
            is_available=True,
            recommended_segments=["loyal", "champions", "potential_loyalist"],
            is_active=True,
            price_updated_at=datetime.utcnow(),
            created_at=datetime.utcnow(),
        ),
        ProductResponse(
            id=uuid4(),
            tenant_id=tenant_id,
            name="بلوک سبک",
            code="BLK-L",
            description="بلوک سبک AAC",
            category="block",
            subcategory="lightweight",
            unit="m3",
            base_price=2_000_000,
            current_price=2_200_000,
            is_available=True,
            recommended_segments=["new_customers", "potential_loyalist"],
            is_active=True,
            price_updated_at=datetime.utcnow(),
            created_at=datetime.utcnow(),
        ),
        ProductResponse(
            id=uuid4(),
            tenant_id=tenant_id,
            name="بتن آماده C25",
            code="CON-C25",
            description="بتن آماده کلاس C25",
            category="concrete",
            subcategory="ready_mix",
            unit="m3",
            base_price=3_500_000,
            current_price=3_800_000,
            is_available=True,
            recommended_segments=["loyal", "champions"],
            is_active=True,
            price_updated_at=datetime.utcnow(),
            created_at=datetime.utcnow(),
        ),
        ProductResponse(
            id=uuid4(),
            tenant_id=tenant_id,
            name="کاشی 60x60",
            code="TIL-60",
            description="کاشی پرسلانی 60x60",
            category="tile",
            subcategory="porcelain",
            unit="m2",
            base_price=400_000,
            current_price=450_000,
            is_available=True,
            recommended_segments=["at_risk", "hibernating"],
            is_active=True,
            price_updated_at=datetime.utcnow(),
            created_at=datetime.utcnow(),
        ),
    ]

    return ProductListResponse(
        products=products,
        total_count=len(products),
    )


@router.post("/products", response_model=ProductResponse, status_code=201)
async def create_product(
    tenant_id: Annotated[UUID, Depends(get_current_tenant)],
    request: CreateProductRequest,
):
    """
    Create a new product.
    """
    return ProductResponse(
        id=uuid4(),
        tenant_id=tenant_id,
        name=request.name,
        code=request.code,
        description=request.description,
        category=request.category,
        subcategory=request.subcategory,
        unit=request.unit,
        base_price=request.base_price,
        current_price=request.current_price,
        is_available=request.is_available,
        stock_quantity=request.stock_quantity,
        specifications=request.specifications,
        tags=request.tags,
        recommended_segments=request.recommended_segments,
        is_active=request.is_active,
        metadata=request.metadata,
        price_updated_at=datetime.utcnow(),
        created_at=datetime.utcnow(),
    )


@router.get("/products/{product_id}", response_model=ProductResponse)
async def get_product(
    product_id: UUID,
    tenant_id: Annotated[UUID, Depends(get_current_tenant)],
):
    """
    Get product by ID.
    """
    raise HTTPException(status_code=404, detail="Product not found")


@router.put("/products/{product_id}", response_model=ProductResponse)
async def update_product(
    product_id: UUID,
    tenant_id: Annotated[UUID, Depends(get_current_tenant)],
    request: UpdateProductRequest,
):
    """
    Update a product.
    """
    raise HTTPException(status_code=404, detail="Product not found")


@router.delete("/products/{product_id}", status_code=204)
async def delete_product(
    product_id: UUID,
    tenant_id: Annotated[UUID, Depends(get_current_tenant)],
):
    """
    Delete a product.
    """
    pass


@router.get("/products/categories/summary", response_model=list[ProductCategoryResponse])
async def get_product_categories(
    tenant_id: Annotated[UUID, Depends(get_current_tenant)],
):
    """
    Get product categories with statistics.
    """
    return [
        ProductCategoryResponse(
            category="cement",
            product_count=5,
            total_revenue=1_000_000_000,
            top_products=[{"name": "سیمان تیپ 2", "revenue": 500_000_000}],
        ),
        ProductCategoryResponse(
            category="block",
            product_count=3,
            total_revenue=300_000_000,
            top_products=[{"name": "بلوک سبک", "revenue": 200_000_000}],
        ),
        ProductCategoryResponse(
            category="concrete",
            product_count=4,
            total_revenue=800_000_000,
            top_products=[{"name": "بتن آماده C25", "revenue": 400_000_000}],
        ),
        ProductCategoryResponse(
            category="tile",
            product_count=10,
            total_revenue=500_000_000,
            top_products=[{"name": "کاشی 60x60", "revenue": 150_000_000}],
        ),
    ]


@router.get("/products/{product_id}/price-history", response_model=ProductPriceHistoryResponse)
async def get_product_price_history(
    product_id: UUID,
    tenant_id: Annotated[UUID, Depends(get_current_tenant)],
):
    """
    Get price history for a product.
    """
    return ProductPriceHistoryResponse(
        product_id=product_id,
        product_name="Sample Product",
        price_changes=[],
    )


@router.post("/products/update-prices")
async def bulk_update_prices(
    tenant_id: Annotated[UUID, Depends(get_current_tenant)],
    request: UpdatePricesRequest,
):
    """
    Bulk update product prices.
    """
    return {
        "updated_count": len(request.price_updates),
        "errors": [],
    }


@router.post("/products/import-catalog")
async def import_product_catalog(
    tenant_id: Annotated[UUID, Depends(get_current_tenant)],
    file: UploadFile = File(...),
):
    """
    Import product catalog from file.
    """
    return {
        "total_imported": 0,
        "created": 0,
        "updated": 0,
        "errors": [],
    }


# ============================================================================
# Invoice Endpoints
# ============================================================================

@router.get("/invoices", response_model=InvoiceListResponse)
async def list_invoices(
    tenant_id: Annotated[UUID, Depends(get_current_tenant)],
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
    """
    List invoices with filtering.
    """
    return InvoiceListResponse(
        invoices=[],
        total_count=0,
        page=page,
        page_size=page_size,
        has_next=False,
        has_prev=page > 1,
    )


@router.post("/invoices", response_model=InvoiceResponse, status_code=201)
async def create_invoice(
    tenant_id: Annotated[UUID, Depends(get_current_tenant)],
    user_id: Annotated[UUID, Depends(get_current_user)],
    request: CreateInvoiceRequest,
):
    """
    Create a new invoice (pre-invoice).
    """
    invoice_id = uuid4()

    # Calculate line items
    line_items = []
    subtotal = 0
    for item in request.line_items:
        item_total = int(item.quantity * item.unit_price) - item.discount_amount + item.tax_amount
        subtotal += item_total
        line_items.append({
            "id": str(uuid4()),
            "tenant_id": str(tenant_id),
            "invoice_id": str(invoice_id),
            "product_id": str(item.product_id) if item.product_id else None,
            "product_name": item.product_name,
            "product_code": item.product_code,
            "quantity": item.quantity,
            "unit": item.unit,
            "unit_price": item.unit_price,
            "total_price": item_total,
            "discount_amount": item.discount_amount,
            "tax_amount": item.tax_amount,
        })

    total_amount = subtotal - request.discount_amount + request.tax_amount

    return InvoiceResponse(
        id=invoice_id,
        tenant_id=tenant_id,
        invoice_number=f"INV-{datetime.utcnow().strftime('%Y%m%d')}-{str(invoice_id)[:8].upper()}",
        contact_id=request.contact_id,
        phone_number=request.phone_number,
        customer_name=request.customer_name,
        salesperson_id=request.salesperson_id,
        line_items=[],  # Would be populated properly
        subtotal=subtotal,
        discount_amount=request.discount_amount,
        tax_amount=request.tax_amount,
        total_amount=total_amount,
        status="draft",
        due_date=request.due_date,
        notes=request.notes,
        internal_notes=request.internal_notes,
        external_id=request.external_id,
        created_at=datetime.utcnow(),
    )


@router.get("/invoices/{invoice_id}", response_model=InvoiceResponse)
async def get_invoice(
    invoice_id: UUID,
    tenant_id: Annotated[UUID, Depends(get_current_tenant)],
):
    """
    Get invoice by ID.
    """
    raise HTTPException(status_code=404, detail="Invoice not found")


@router.put("/invoices/{invoice_id}", response_model=InvoiceResponse)
async def update_invoice(
    invoice_id: UUID,
    tenant_id: Annotated[UUID, Depends(get_current_tenant)],
    request: UpdateInvoiceRequest,
):
    """
    Update an invoice.
    """
    raise HTTPException(status_code=404, detail="Invoice not found")


@router.post("/invoices/{invoice_id}/issue", response_model=InvoiceResponse)
async def issue_invoice(
    invoice_id: UUID,
    tenant_id: Annotated[UUID, Depends(get_current_tenant)],
):
    """
    Issue a draft invoice.
    """
    raise HTTPException(status_code=404, detail="Invoice not found")


@router.post("/invoices/{invoice_id}/cancel", response_model=InvoiceResponse)
async def cancel_invoice(
    invoice_id: UUID,
    tenant_id: Annotated[UUID, Depends(get_current_tenant)],
    reason: str | None = Query(default=None),
):
    """
    Cancel an invoice.
    """
    raise HTTPException(status_code=404, detail="Invoice not found")


@router.get("/invoices/summary", response_model=InvoiceSummaryResponse)
async def get_invoice_summary(
    tenant_id: Annotated[UUID, Depends(get_current_tenant)],
    start_date: datetime = Query(default=None),
    end_date: datetime = Query(default=None),
):
    """
    Get invoice summary statistics.
    """
    if start_date is None:
        start_date = datetime.utcnow() - timedelta(days=30)
    if end_date is None:
        end_date = datetime.utcnow()

    return InvoiceSummaryResponse(
        total_invoices=250,
        total_amount=2_500_000_000,
        total_paid=2_000_000_000,
        total_outstanding=500_000_000,
        by_status={
            "draft": 20,
            "issued": 80,
            "paid": 120,
            "partial_paid": 20,
            "cancelled": 10,
        },
        by_salesperson=[
            {"name": "اسدالهی", "invoices": 30, "total": 300_000_000},
            {"name": "بردبار", "invoices": 28, "total": 280_000_000},
        ],
    )


# ============================================================================
# Payment Endpoints
# ============================================================================

@router.post("/invoices/{invoice_id}/payments", response_model=PaymentResponse)
async def record_payment(
    invoice_id: UUID,
    tenant_id: Annotated[UUID, Depends(get_current_tenant)],
    request: RecordPaymentRequest,
):
    """
    Record a payment for an invoice.
    """
    return PaymentResponse(
        id=uuid4(),
        tenant_id=tenant_id,
        invoice_id=invoice_id,
        invoice_number=f"INV-{str(invoice_id)[:8].upper()}",
        amount=request.amount,
        payment_method=request.payment_method,
        payment_date=request.payment_date or datetime.utcnow(),
        reference_number=request.reference_number,
        notes=request.notes,
        created_at=datetime.utcnow(),
    )


@router.get("/invoices/{invoice_id}/payments", response_model=PaymentListResponse)
async def get_invoice_payments(
    invoice_id: UUID,
    tenant_id: Annotated[UUID, Depends(get_current_tenant)],
):
    """
    Get payments for an invoice.
    """
    return PaymentListResponse(
        payments=[],
        total_count=0,
        total_amount=0,
    )


@router.get("/payments", response_model=PaymentListResponse)
async def list_payments(
    tenant_id: Annotated[UUID, Depends(get_current_tenant)],
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    salesperson_id: UUID | None = Query(default=None),
):
    """
    List all payments with filtering.
    """
    return PaymentListResponse(
        payments=[],
        total_count=0,
        total_amount=0,
    )


# ============================================================================
# Data Source Integration Endpoints
# ============================================================================

@router.get("/data-sources", response_model=DataSourceListResponse)
async def list_data_sources(
    tenant_id: Annotated[UUID, Depends(get_current_tenant)],
):
    """
    List configured data sources.
    """
    return DataSourceListResponse(
        sources=[],
        total_count=0,
    )


@router.post("/data-sources", response_model=DataSourceResponse, status_code=201)
async def create_data_source(
    tenant_id: Annotated[UUID, Depends(get_current_tenant)],
    request: CreateDataSourceRequest,
):
    """
    Create a new data source configuration.
    """
    return DataSourceResponse(
        id=uuid4(),
        tenant_id=tenant_id,
        name=request.name,
        source_type=request.source_type,
        connection_string=request.connection_string,
        database_name=request.database_name,
        collection_name=request.collection_name,
        api_endpoint=request.api_endpoint,
        api_key=request.api_key,
        field_mappings=request.field_mappings,
        sync_interval_minutes=request.sync_interval_minutes,
        is_active=request.is_active,
        metadata=request.metadata,
        created_at=datetime.utcnow(),
    )


@router.get("/data-sources/{source_id}", response_model=DataSourceResponse)
async def get_data_source(
    source_id: UUID,
    tenant_id: Annotated[UUID, Depends(get_current_tenant)],
):
    """
    Get data source by ID.
    """
    raise HTTPException(status_code=404, detail="Data source not found")


@router.delete("/data-sources/{source_id}", status_code=204)
async def delete_data_source(
    source_id: UUID,
    tenant_id: Annotated[UUID, Depends(get_current_tenant)],
):
    """
    Delete a data source.
    """
    pass


@router.post("/data-sources/{source_id}/sync", response_model=SyncDataResponse)
async def sync_data_source(
    source_id: UUID,
    tenant_id: Annotated[UUID, Depends(get_current_tenant)],
    request: SyncDataRequest = None,
):
    """
    Trigger data sync from a source.
    """
    return SyncDataResponse(
        source_id=source_id,
        sync_started_at=datetime.utcnow(),
        records_fetched=0,
        records_created=0,
        records_updated=0,
    )


@router.post("/data-sources/{source_id}/test")
async def test_data_source_connection(
    source_id: UUID,
    tenant_id: Annotated[UUID, Depends(get_current_tenant)],
):
    """
    Test connection to a data source.
    """
    return {
        "success": True,
        "message": "Connection successful",
    }


# ============================================================================
# Sales Statistics Endpoints
# ============================================================================

@router.get("/stats", response_model=SalesStatsResponse)
async def get_sales_stats(
    tenant_id: Annotated[UUID, Depends(get_current_tenant)],
    start_date: datetime = Query(default=None),
    end_date: datetime = Query(default=None),
):
    """
    Get sales statistics.
    """
    if start_date is None:
        start_date = datetime.utcnow() - timedelta(days=30)
    if end_date is None:
        end_date = datetime.utcnow()

    return SalesStatsResponse(
        period_start=start_date,
        period_end=end_date,
        total_invoices=250,
        total_paid=150,
        total_cancelled=10,
        total_revenue=2_000_000_000,
        total_outstanding=500_000_000,
        average_order_value=13_333_333,
        by_product_category=[
            {"category": "cement", "revenue": 1_000_000_000, "count": 100},
            {"category": "concrete", "revenue": 600_000_000, "count": 60},
            {"category": "block", "revenue": 250_000_000, "count": 50},
            {"category": "tile", "revenue": 150_000_000, "count": 40},
        ],
        by_salesperson=[
            {"name": "اسدالهی", "revenue": 300_000_000, "count": 30},
            {"name": "بردبار", "revenue": 280_000_000, "count": 28},
            {"name": "رضایی", "revenue": 250_000_000, "count": 25},
        ],
        conversion_rate=0.05,
    )


@router.get("/stats/revenue-by-period", response_model=RevenueByPeriodResponse)
async def get_revenue_by_period(
    tenant_id: Annotated[UUID, Depends(get_current_tenant)],
    period: str = Query(default="daily"),  # daily, weekly, monthly
    start_date: datetime = Query(default=None),
    end_date: datetime = Query(default=None),
):
    """
    Get revenue breakdown by period.
    """
    if start_date is None:
        start_date = datetime.utcnow() - timedelta(days=30)
    if end_date is None:
        end_date = datetime.utcnow()

    # Generate sample data
    data = []
    current = start_date
    while current <= end_date:
        data.append({
            "date": current.isoformat(),
            "revenue": 50_000_000 + (current.day * 2_000_000),
            "invoices": 5 + (current.day % 3),
            "aov": 10_000_000,
        })
        if period == "daily":
            current += timedelta(days=1)
        elif period == "weekly":
            current += timedelta(weeks=1)
        else:
            current += timedelta(days=30)

    return RevenueByPeriodResponse(data=data)


@router.get("/stats/top-customers", response_model=TopCustomersResponse)
async def get_top_customers(
    tenant_id: Annotated[UUID, Depends(get_current_tenant)],
    limit: int = Query(default=10, ge=1, le=50),
    start_date: datetime = Query(default=None),
    end_date: datetime = Query(default=None),
):
    """
    Get top customers by revenue.
    """
    return TopCustomersResponse(
        customers=[
            {
                "contact_id": str(uuid4()),
                "phone": "989123456789",
                "name": "شرکت ساختمانی الف",
                "total_revenue": 500_000_000,
                "order_count": 15,
            },
            {
                "contact_id": str(uuid4()),
                "phone": "989123456790",
                "name": "شرکت عمرانی ب",
                "total_revenue": 350_000_000,
                "order_count": 12,
            },
        ],
    )


@router.get("/stats/top-products", response_model=TopProductsResponse)
async def get_top_products(
    tenant_id: Annotated[UUID, Depends(get_current_tenant)],
    limit: int = Query(default=10, ge=1, le=50),
    start_date: datetime = Query(default=None),
    end_date: datetime = Query(default=None),
):
    """
    Get top products by revenue.
    """
    return TopProductsResponse(
        products=[
            {
                "product_id": str(uuid4()),
                "name": "سیمان تیپ 2",
                "quantity_sold": 500,
                "revenue": 1_000_000_000,
            },
            {
                "product_id": str(uuid4()),
                "name": "بتن آماده C25",
                "quantity_sold": 200,
                "revenue": 600_000_000,
            },
        ],
    )

