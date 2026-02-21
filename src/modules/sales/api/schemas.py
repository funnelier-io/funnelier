"""
Sales API Schemas

Pydantic schemas for sales module API endpoints.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


# ============================================================================
# Product Schemas
# ============================================================================

class ProductBase(BaseModel):
    """Base schema for product."""
    name: str
    code: str | None = None
    description: str | None = None
    category: str
    subcategory: str | None = None
    unit: str = "ton"
    base_price: int = 0
    current_price: int = 0
    is_available: bool = True
    stock_quantity: int | None = None
    specifications: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    recommended_segments: list[str] = Field(default_factory=list)
    is_active: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class CreateProductRequest(ProductBase):
    """Schema for creating a product."""
    pass


class UpdateProductRequest(BaseModel):
    """Schema for updating a product."""
    name: str | None = None
    code: str | None = None
    description: str | None = None
    category: str | None = None
    subcategory: str | None = None
    unit: str | None = None
    base_price: int | None = None
    current_price: int | None = None
    is_available: bool | None = None
    stock_quantity: int | None = None
    specifications: dict[str, Any] | None = None
    tags: list[str] | None = None
    recommended_segments: list[str] | None = None
    is_active: bool | None = None
    metadata: dict[str, Any] | None = None


class ProductResponse(ProductBase):
    """Schema for product response."""
    id: UUID
    tenant_id: UUID
    price_updated_at: datetime | None = None
    created_at: datetime
    updated_at: datetime | None = None

    class Config:
        from_attributes = True


class ProductListResponse(BaseModel):
    """Schema for product list."""
    products: list[ProductResponse]
    total_count: int


class ProductCategoryResponse(BaseModel):
    """Schema for product category."""
    category: str
    product_count: int
    total_revenue: int
    top_products: list[dict[str, Any]]


class ProductPriceHistoryResponse(BaseModel):
    """Schema for product price history."""
    product_id: UUID
    product_name: str
    price_changes: list[dict[str, Any]]


class UpdatePricesRequest(BaseModel):
    """Schema for bulk price update."""
    price_updates: list[dict[str, Any]]  # [{product_id, new_price}]


# ============================================================================
# Invoice Line Item Schemas
# ============================================================================

class InvoiceLineItemBase(BaseModel):
    """Base schema for invoice line item."""
    product_id: UUID | None = None
    product_name: str
    product_code: str | None = None
    quantity: float
    unit: str
    unit_price: int
    discount_amount: int = 0
    tax_amount: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)


class CreateLineItemRequest(InvoiceLineItemBase):
    """Schema for creating a line item."""
    pass


class LineItemResponse(InvoiceLineItemBase):
    """Schema for line item response."""
    id: UUID
    tenant_id: UUID
    invoice_id: UUID
    total_price: int

    class Config:
        from_attributes = True


# ============================================================================
# Invoice Schemas
# ============================================================================

class InvoiceBase(BaseModel):
    """Base schema for invoice."""
    phone_number: str
    customer_name: str | None = None
    notes: str | None = None
    internal_notes: str | None = None


class CreateInvoiceRequest(InvoiceBase):
    """Schema for creating an invoice."""
    contact_id: UUID | None = None
    salesperson_id: UUID | None = None
    line_items: list[CreateLineItemRequest]
    discount_amount: int = 0
    tax_amount: int = 0
    due_date: datetime | None = None
    external_id: str | None = None


class UpdateInvoiceRequest(BaseModel):
    """Schema for updating an invoice."""
    customer_name: str | None = None
    notes: str | None = None
    internal_notes: str | None = None
    discount_amount: int | None = None
    tax_amount: int | None = None
    due_date: datetime | None = None


class InvoiceResponse(BaseModel):
    """Schema for invoice response."""
    id: UUID
    tenant_id: UUID
    invoice_number: str
    contact_id: UUID | None = None
    phone_number: str
    customer_name: str | None = None
    salesperson_id: UUID | None = None
    salesperson_name: str | None = None
    line_items: list[LineItemResponse] = Field(default_factory=list)
    subtotal: int = 0
    discount_amount: int = 0
    tax_amount: int = 0
    total_amount: int = 0
    status: str
    issued_at: datetime | None = None
    due_date: datetime | None = None
    paid_at: datetime | None = None
    cancelled_at: datetime | None = None
    amount_paid: int = 0
    payment_method: str | None = None
    notes: str | None = None
    internal_notes: str | None = None
    cancellation_reason: str | None = None
    external_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime | None = None

    class Config:
        from_attributes = True


class InvoiceListResponse(BaseModel):
    """Schema for paginated invoice list."""
    invoices: list[InvoiceResponse]
    total_count: int
    page: int
    page_size: int
    has_next: bool
    has_prev: bool
    total_amount: int = 0
    total_paid: int = 0


class InvoiceSummaryResponse(BaseModel):
    """Schema for invoice summary."""
    total_invoices: int
    total_amount: int
    total_paid: int
    total_outstanding: int
    by_status: dict[str, int]
    by_salesperson: list[dict[str, Any]]


# ============================================================================
# Payment Schemas
# ============================================================================

class RecordPaymentRequest(BaseModel):
    """Schema for recording a payment."""
    amount: int
    payment_method: str | None = None
    payment_date: datetime | None = None
    reference_number: str | None = None
    notes: str | None = None


class PaymentResponse(BaseModel):
    """Schema for payment response."""
    id: UUID
    tenant_id: UUID
    invoice_id: UUID
    invoice_number: str
    amount: int
    payment_method: str | None = None
    payment_date: datetime
    reference_number: str | None = None
    notes: str | None = None
    created_at: datetime

    class Config:
        from_attributes = True


class PaymentListResponse(BaseModel):
    """Schema for payment list."""
    payments: list[PaymentResponse]
    total_count: int
    total_amount: int


# ============================================================================
# Data Sync Schemas (MongoDB Integration)
# ============================================================================

class DataSourceConfigBase(BaseModel):
    """Base schema for data source configuration."""
    name: str
    source_type: str  # mongodb, api, file
    connection_string: str | None = None
    database_name: str | None = None
    collection_name: str | None = None
    api_endpoint: str | None = None
    api_key: str | None = None
    field_mappings: dict[str, str] = Field(default_factory=dict)
    sync_interval_minutes: int = 60
    is_active: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class CreateDataSourceRequest(DataSourceConfigBase):
    """Schema for creating a data source."""
    pass


class DataSourceResponse(DataSourceConfigBase):
    """Schema for data source response."""
    id: UUID
    tenant_id: UUID
    last_sync_at: datetime | None = None
    last_sync_status: str | None = None
    total_records_synced: int = 0
    created_at: datetime
    updated_at: datetime | None = None

    class Config:
        from_attributes = True


class DataSourceListResponse(BaseModel):
    """Schema for data source list."""
    sources: list[DataSourceResponse]
    total_count: int


class SyncDataRequest(BaseModel):
    """Schema for data sync request."""
    full_sync: bool = False
    from_date: datetime | None = None
    to_date: datetime | None = None


class SyncDataResponse(BaseModel):
    """Schema for data sync response."""
    source_id: UUID
    sync_started_at: datetime
    records_fetched: int
    records_created: int
    records_updated: int
    errors: list[str] = Field(default_factory=list)


# ============================================================================
# Sales Statistics Schemas
# ============================================================================

class SalesStatsResponse(BaseModel):
    """Schema for sales statistics."""
    period_start: datetime
    period_end: datetime
    total_invoices: int
    total_paid: int
    total_cancelled: int
    total_revenue: int
    total_outstanding: int
    average_order_value: int
    by_product_category: list[dict[str, Any]]
    by_salesperson: list[dict[str, Any]]
    conversion_rate: float


class RevenueByPeriodResponse(BaseModel):
    """Schema for revenue by period."""
    data: list[dict[str, Any]]  # [{date, revenue, invoices, aov}]


class TopCustomersResponse(BaseModel):
    """Schema for top customers."""
    customers: list[dict[str, Any]]  # [{contact_id, phone, name, total_revenue, order_count}]


class TopProductsResponse(BaseModel):
    """Schema for top products."""
    products: list[dict[str, Any]]  # [{product_id, name, quantity_sold, revenue}]

