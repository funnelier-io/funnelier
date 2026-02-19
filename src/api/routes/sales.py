"""
API Routes - Sales Module
Invoices and payments endpoints
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Query
from pydantic import BaseModel

router = APIRouter()


# Response schemas
class InvoiceLineItemResponse(BaseModel):
    product_name: str
    quantity: float
    unit: str
    unit_price: int
    total_price: int


class InvoiceResponse(BaseModel):
    id: UUID
    invoice_number: str
    phone_number: str
    customer_name: str | None
    status: str
    total_amount: int
    amount_paid: int
    issued_at: datetime | None
    paid_at: datetime | None
    line_items: list[InvoiceLineItemResponse]


class InvoiceListResponse(BaseModel):
    items: list[InvoiceResponse]
    total: int
    page: int
    page_size: int


class PaymentResponse(BaseModel):
    id: UUID
    invoice_id: UUID | None
    phone_number: str
    amount: int
    payment_method: str
    status: str
    payment_date: datetime


class PaymentListResponse(BaseModel):
    items: list[PaymentResponse]
    total: int
    page: int
    page_size: int


class ProductResponse(BaseModel):
    id: UUID
    name: str
    code: str | None
    category: str
    unit: str
    current_price: int
    is_available: bool


class SalesStats(BaseModel):
    total_invoices: int
    paid_invoices: int
    total_revenue: int
    average_order_value: int
    payment_rate: float
    period_start: datetime
    period_end: datetime


class ProductSalesStats(BaseModel):
    product_id: UUID
    product_name: str
    units_sold: float
    total_revenue: int
    percentage_of_total: float


class ImportResult(BaseModel):
    success_count: int
    error_count: int
    errors: list[str]
    source_name: str


# Endpoints
@router.get("/invoices", response_model=InvoiceListResponse)
async def list_invoices(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    phone_number: str | None = None,
    status: str | None = None,
    salesperson_id: UUID | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
) -> InvoiceListResponse:
    """
    List invoices with filtering.
    """
    return InvoiceListResponse(
        items=[],
        total=0,
        page=page,
        page_size=page_size,
    )


@router.get("/invoices/{invoice_id}", response_model=InvoiceResponse)
async def get_invoice(invoice_id: UUID) -> InvoiceResponse:
    """
    Get a specific invoice.
    """
    from fastapi import HTTPException
    raise HTTPException(status_code=404, detail="Invoice not found")


@router.get("/invoices/stats", response_model=SalesStats)
async def get_sales_stats(
    start_date: datetime | None = None,
    end_date: datetime | None = None,
) -> SalesStats:
    """
    Get sales statistics.
    """
    now = datetime.utcnow()
    return SalesStats(
        total_invoices=0,
        paid_invoices=0,
        total_revenue=0,
        average_order_value=0,
        payment_rate=0.0,
        period_start=start_date or now,
        period_end=end_date or now,
    )


@router.get("/payments", response_model=PaymentListResponse)
async def list_payments(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    phone_number: str | None = None,
    invoice_id: UUID | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
) -> PaymentListResponse:
    """
    List payments with filtering.
    """
    return PaymentListResponse(
        items=[],
        total=0,
        page=page,
        page_size=page_size,
    )


@router.get("/products", response_model=list[ProductResponse])
async def list_products(
    category: str | None = None,
    available_only: bool = True,
) -> list[ProductResponse]:
    """
    List products.
    """
    return []


@router.get("/products/{product_id}", response_model=ProductResponse)
async def get_product(product_id: UUID) -> ProductResponse:
    """
    Get a specific product.
    """
    from fastapi import HTTPException
    raise HTTPException(status_code=404, detail="Product not found")


@router.get("/products/stats", response_model=list[ProductSalesStats])
async def get_product_sales_stats(
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    limit: int = Query(10, ge=1, le=50),
) -> list[ProductSalesStats]:
    """
    Get product sales statistics.
    """
    return []


@router.post("/sync/invoices", response_model=ImportResult)
async def sync_invoices_from_source(
    source_id: UUID,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
) -> ImportResult:
    """
    Sync invoices from external data source.
    """
    return ImportResult(
        success_count=0,
        error_count=0,
        errors=[],
        source_name="MongoDB",
    )


@router.post("/sync/payments", response_model=ImportResult)
async def sync_payments_from_source(
    source_id: UUID,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
) -> ImportResult:
    """
    Sync payments from external data source.
    """
    return ImportResult(
        success_count=0,
        error_count=0,
        errors=[],
        source_name="MongoDB",
    )

