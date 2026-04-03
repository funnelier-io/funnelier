"""
Global Search API

Unified search across contacts, invoices, campaigns, and products.
Supports quick-find via GET /api/v1/search?q=...
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_db_session, get_current_tenant_id
from src.infrastructure.database.models.leads import ContactModel
from src.infrastructure.database.models.sales import InvoiceModel, ProductModel
from src.infrastructure.database.models.campaigns import CampaignModel

router = APIRouter(tags=["Search"])


class SearchResultItem(BaseModel):
    id: str
    type: str  # contact, invoice, campaign, product
    title: str
    subtitle: str | None = None
    url: str  # frontend route
    meta: dict = {}


class SearchResponse(BaseModel):
    query: str
    total: int
    results: list[SearchResultItem]


@router.get("/search", response_model=SearchResponse)
async def global_search(
    q: str = Query(..., min_length=1, max_length=200, description="Search query"),
    limit: int = Query(default=20, ge=1, le=50),
    session: AsyncSession = Depends(get_db_session),
    tenant_id: UUID = Depends(get_current_tenant_id),
):
    """
    Search across contacts, invoices, campaigns, and products.
    Returns a unified result list sorted by relevance.
    """
    query = q.strip()
    results: list[SearchResultItem] = []
    per_type = max(limit // 4, 5)

    # 1. Contacts — search by name, phone_number, email
    contact_q = (
        select(
            ContactModel.id,
            ContactModel.name,
            ContactModel.phone_number,
            ContactModel.current_stage,
            ContactModel.rfm_segment,
            ContactModel.category_name,
        )
        .where(
            ContactModel.tenant_id == tenant_id,
            or_(
                ContactModel.name.ilike(f"%{query}%"),
                ContactModel.phone_number.ilike(f"%{query}%"),
                ContactModel.email.ilike(f"%{query}%"),
            ),
        )
        .order_by(
            # Prefer exact prefix matches
            ContactModel.name.ilike(f"{query}%").desc(),
            ContactModel.name,
        )
        .limit(per_type)
    )
    contact_rows = (await session.execute(contact_q)).all()
    for row in contact_rows:
        results.append(SearchResultItem(
            id=str(row.id),
            type="contact",
            title=row.name or row.phone_number,
            subtitle=row.phone_number if row.name else None,
            url=f"/leads?search={row.phone_number}",
            meta={
                "stage": row.current_stage,
                "segment": row.rfm_segment,
                "category": row.category_name,
            },
        ))

    # 2. Invoices — search by invoice_number, phone_number
    invoice_q = (
        select(
            InvoiceModel.id,
            InvoiceModel.invoice_number,
            InvoiceModel.phone_number,
            InvoiceModel.status,
            InvoiceModel.total_amount,
        )
        .where(
            InvoiceModel.tenant_id == tenant_id,
            or_(
                InvoiceModel.invoice_number.ilike(f"%{query}%"),
                InvoiceModel.phone_number.ilike(f"%{query}%"),
            ),
        )
        .order_by(InvoiceModel.issued_at.desc())
        .limit(per_type)
    )
    invoice_rows = (await session.execute(invoice_q)).all()
    for row in invoice_rows:
        results.append(SearchResultItem(
            id=str(row.id),
            type="invoice",
            title=row.invoice_number or "فاکتور",
            subtitle=row.phone_number,
            url="/sales",
            meta={
                "status": row.status,
                "amount": row.total_amount,
            },
        ))

    # 3. Campaigns — search by name
    campaign_q = (
        select(
            CampaignModel.id,
            CampaignModel.name,
            CampaignModel.campaign_type,
            CampaignModel.status,
        )
        .where(
            CampaignModel.tenant_id == tenant_id,
            CampaignModel.name.ilike(f"%{query}%"),
        )
        .order_by(CampaignModel.created_at.desc())
        .limit(per_type)
    )
    campaign_rows = (await session.execute(campaign_q)).all()
    for row in campaign_rows:
        results.append(SearchResultItem(
            id=str(row.id),
            type="campaign",
            title=row.name,
            subtitle=None,
            url="/campaigns",
            meta={
                "type": row.campaign_type,
                "status": row.status,
            },
        ))

    # 4. Products — search by name, code
    product_q = (
        select(
            ProductModel.id,
            ProductModel.name,
            ProductModel.code,
            ProductModel.category,
            ProductModel.current_price,
        )
        .where(
            ProductModel.tenant_id == tenant_id,
            or_(
                ProductModel.name.ilike(f"%{query}%"),
                ProductModel.code.ilike(f"%{query}%"),
            ),
        )
        .order_by(ProductModel.name)
        .limit(per_type)
    )
    product_rows = (await session.execute(product_q)).all()
    for row in product_rows:
        results.append(SearchResultItem(
            id=str(row.id),
            type="product",
            title=row.name,
            subtitle=row.code,
            url="/sales",
            meta={
                "category": row.category,
                "price": row.current_price,
            },
        ))

    return SearchResponse(
        query=query,
        total=len(results),
        results=results[:limit],
    )

