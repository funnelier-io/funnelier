"""
Leads API Routes

FastAPI routes for lead management endpoints.
"""

from datetime import datetime
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File

from src.api.dependencies import (
    get_contact_repository,
    get_category_repository,
    get_lead_source_repository,
    get_current_tenant_id,
)
from src.core.domain.entities import PhoneNumber
from src.modules.leads.domain.entities import Contact, LeadCategory, LeadSourceConfig
from src.modules.leads.infrastructure.repositories import (
    ContactRepository,
    LeadCategoryRepository,
    LeadSourceRepository,
)

from .schemas import (
    AutoAssignRequest,
    AutoAssignResponse,
    BulkAssignRequest,
    BulkAssignResponse,
    BulkImportRequest,
    BulkImportResponse,
    CategoryListResponse,
    CategoryResponse,
    CategoryTreeResponse,
    ContactListResponse,
    ContactResponse,
    ContactSearchRequest,
    ContactStageUpdateRequest,
    CreateCategoryRequest,
    CreateContactRequest,
    CreateSourceRequest,
    SourceListResponse,
    SourceResponse,
    UpdateCategoryRequest,
    UpdateContactRequest,
    UpdateSourceRequest,
)

router = APIRouter(tags=["leads"])


# ============================================================================
# Helper: convert domain entity → API response
# ============================================================================

def _contact_to_response(c: Contact) -> ContactResponse:
    return ContactResponse(
        id=c.id,
        tenant_id=c.tenant_id,
        phone_number=c.phone_number.normalized if isinstance(c.phone_number, PhoneNumber) else c.phone_number,
        name=c.name,
        email=c.email,
        source_id=c.source_id,
        source_name=c.source_name,
        category_id=c.category_id,
        category_name=c.category_name,
        assigned_to=c.assigned_to,
        assigned_at=c.assigned_at,
        current_stage=c.current_stage,
        stage_entered_at=c.stage_entered_at,
        rfm_segment=c.rfm_segment,
        rfm_score=c.rfm_score,
        total_sms_sent=c.total_sms_sent,
        total_sms_delivered=c.total_sms_delivered,
        total_calls=c.total_calls,
        total_answered_calls=c.total_answered_calls,
        total_call_duration=c.total_call_duration,
        total_invoices=c.total_invoices,
        total_paid_invoices=c.total_paid_invoices,
        total_revenue=c.total_revenue,
        last_purchase_at=c.last_purchase_at,
        first_purchase_at=c.first_purchase_at,
        is_active=c.is_active,
        is_blocked=c.is_blocked,
        blocked_reason=c.blocked_reason,
        tags=c.tags,
        custom_fields=c.custom_fields,
        notes=c.notes,
        created_at=c.created_at,
        updated_at=c.updated_at,
    )


def _category_to_response(cat: LeadCategory, contact_count: int = 0) -> CategoryResponse:
    return CategoryResponse(
        id=cat.id,
        tenant_id=cat.tenant_id,
        name=cat.name,
        description=cat.description,
        parent_id=cat.parent_id,
        color=cat.color,
        is_active=cat.is_active,
        contact_count=contact_count,
        metadata=cat.metadata,
        created_at=cat.created_at,
        updated_at=cat.updated_at,
    )


# ============================================================================
# Contact Endpoints
# ============================================================================

@router.get("/contacts", response_model=ContactListResponse)
async def list_contacts(
    repo: Annotated[ContactRepository, Depends(get_contact_repository)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    category_id: UUID | None = Query(default=None),
    source_id: UUID | None = Query(default=None),
    segment: str | None = Query(default=None),
    stage: str | None = Query(default=None),
    salesperson_id: UUID | None = Query(default=None),
    is_active: bool | None = Query(default=None),
    search: str | None = Query(default=None),
):
    """List contacts with filtering and pagination."""
    skip = (page - 1) * page_size
    filters = {}
    if is_active is not None:
        filters["is_active"] = is_active

    if search:
        contacts = await repo.search(search, skip=skip, limit=page_size)
    elif category_id:
        contacts = await repo.get_by_category(category_id, skip=skip, limit=page_size)
    elif segment:
        contacts = await repo.get_by_segment(segment, skip=skip, limit=page_size)
    elif stage:
        contacts = await repo.get_by_stage(stage, skip=skip, limit=page_size)
    elif salesperson_id:
        contacts = await repo.get_by_salesperson(salesperson_id, skip=skip, limit=page_size)
    else:
        contacts = await repo.get_all(skip=skip, limit=page_size, **filters)

    total = await repo.count(**filters)
    return ContactListResponse(
        contacts=[_contact_to_response(c) for c in contacts],
        total_count=total,
        page=page,
        page_size=page_size,
        has_next=(page * page_size) < total,
        has_prev=page > 1,
    )


@router.post("/contacts", response_model=ContactResponse, status_code=201)
async def create_contact(
    repo: Annotated[ContactRepository, Depends(get_contact_repository)],
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
    request: CreateContactRequest,
):
    """Create a new contact."""
    # Check for duplicate
    existing = await repo.get_by_phone(request.phone_number)
    if existing:
        raise HTTPException(status_code=409, detail="Contact with this phone number already exists")

    contact = Contact(
        tenant_id=tenant_id,
        phone_number=PhoneNumber.from_string(request.phone_number),
        name=request.name,
        email=request.email,
        source_id=request.source_id,
        source_name=request.source_name,
        category_id=request.category_id,
        category_name=request.category_name,
        assigned_to=request.assigned_to,
        assigned_at=datetime.utcnow() if request.assigned_to else None,
        tags=request.tags or [],
        custom_fields=request.custom_fields or {},
        notes=request.notes,
    )
    saved = await repo.add(contact)
    return _contact_to_response(saved)


@router.get("/contacts/{contact_id}", response_model=ContactResponse)
async def get_contact(
    contact_id: UUID,
    repo: Annotated[ContactRepository, Depends(get_contact_repository)],
):
    """Get contact by ID."""
    contact = await repo.get(contact_id)
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    return _contact_to_response(contact)


@router.put("/contacts/{contact_id}", response_model=ContactResponse)
async def update_contact(
    contact_id: UUID,
    repo: Annotated[ContactRepository, Depends(get_contact_repository)],
    request: UpdateContactRequest,
):
    """Update an existing contact."""
    contact = await repo.get(contact_id)
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    update_data = request.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        if hasattr(contact, key):
            setattr(contact, key, value)

    saved = await repo.update(contact)
    return _contact_to_response(saved)


@router.delete("/contacts/{contact_id}", status_code=204)
async def delete_contact(
    contact_id: UUID,
    repo: Annotated[ContactRepository, Depends(get_contact_repository)],
):
    """Delete a contact."""
    deleted = await repo.delete(contact_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Contact not found")


@router.patch("/contacts/{contact_id}/stage", response_model=ContactResponse)
async def update_contact_stage(
    contact_id: UUID,
    repo: Annotated[ContactRepository, Depends(get_contact_repository)],
    request: ContactStageUpdateRequest,
):
    """Update contact's funnel stage."""
    contact = await repo.get(contact_id)
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    contact.update_stage(request.stage)
    saved = await repo.update(contact)
    return _contact_to_response(saved)


@router.post("/contacts/{contact_id}/block", response_model=ContactResponse)
async def block_contact(
    contact_id: UUID,
    repo: Annotated[ContactRepository, Depends(get_contact_repository)],
    reason: str | None = Query(default=None),
):
    """Block a contact from receiving communications."""
    contact = await repo.get(contact_id)
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    contact.is_blocked = True
    contact.blocked_reason = reason
    saved = await repo.update(contact)
    return _contact_to_response(saved)


@router.post("/contacts/{contact_id}/unblock", response_model=ContactResponse)
async def unblock_contact(
    contact_id: UUID,
    repo: Annotated[ContactRepository, Depends(get_contact_repository)],
):
    """Unblock a contact."""
    contact = await repo.get(contact_id)
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    contact.is_blocked = False
    contact.blocked_reason = None
    saved = await repo.update(contact)
    return _contact_to_response(saved)


# ============================================================================
# Bulk Operations Endpoints
# ============================================================================

@router.post("/contacts/bulk-import", response_model=BulkImportResponse)
async def bulk_import_contacts(
    repo: Annotated[ContactRepository, Depends(get_contact_repository)],
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
    request: BulkImportRequest,
):
    """Bulk import contacts from a list."""
    contacts = []
    for item in request.contacts:
        contacts.append(Contact(
            tenant_id=tenant_id,
            phone_number=PhoneNumber.from_string(item.phone_number),
            name=item.name,
            tags=item.tags or [],
        ))
    success, error_count, errors = await repo.bulk_create(contacts)
    return BulkImportResponse(
        total_submitted=len(request.contacts),
        success_count=success,
        error_count=error_count,
        duplicate_count=error_count,  # most errors are duplicates
    )


@router.post("/contacts/import-file", response_model=BulkImportResponse)
async def import_contacts_from_file(
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
    file: UploadFile = File(...),
    source_id: UUID | None = Query(default=None),
    category_id: UUID | None = Query(default=None),
    assigned_to: UUID | None = Query(default=None),
    skip_duplicates: bool = Query(default=True),
):
    """Import contacts from an uploaded file (CSV, Excel)."""
    allowed_types = [
        "text/csv",
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ]
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed: {', '.join(allowed_types)}",
        )
    # TODO: Process file with ETL pipeline
    return BulkImportResponse(
        total_submitted=0,
        success_count=0,
        error_count=0,
        duplicate_count=0,
    )


@router.post("/contacts/bulk-assign", response_model=BulkAssignResponse)
async def bulk_assign_contacts(
    repo: Annotated[ContactRepository, Depends(get_contact_repository)],
    request: BulkAssignRequest,
):
    """Bulk assign contacts to a salesperson."""
    count = await repo.bulk_assign(request.contact_ids, request.salesperson_id)
    return BulkAssignResponse(
        success_count=count,
        error_count=len(request.contact_ids) - count,
    )


@router.post("/contacts/auto-assign", response_model=AutoAssignResponse)
async def auto_assign_contacts(
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
    repo: Annotated[ContactRepository, Depends(get_contact_repository)],
    request: AutoAssignRequest,
):
    """Auto-assign unassigned contacts to salespeople."""
    # TODO: Implement auto-assignment logic
    return AutoAssignResponse(
        total_assigned=0,
        assignments={},
    )


# ============================================================================
# Category Endpoints
# ============================================================================

@router.get("/categories", response_model=CategoryListResponse)
async def list_categories(
    repo: Annotated[LeadCategoryRepository, Depends(get_category_repository)],
    include_inactive: bool = Query(default=False),
):
    """List all categories."""
    categories_with_counts = await repo.get_with_contact_count()
    items = [
        _category_to_response(cat, count)
        for cat, count in categories_with_counts
        if include_inactive or cat.is_active
    ]
    return CategoryListResponse(categories=items, total_count=len(items))


@router.get("/categories/tree", response_model=list[CategoryTreeResponse])
async def get_category_tree(
    repo: Annotated[LeadCategoryRepository, Depends(get_category_repository)],
):
    """Get categories in hierarchical tree structure."""
    roots = await repo.get_root_categories()
    tree = []
    for root in roots:
        children_entities = await repo.get_children(root.id)
        children = [_category_to_response(c) for c in children_entities]
        tree.append(CategoryTreeResponse(
            **_category_to_response(root).model_dump(),
            children=children,
        ))
    return tree


@router.post("/categories", response_model=CategoryResponse, status_code=201)
async def create_category(
    repo: Annotated[LeadCategoryRepository, Depends(get_category_repository)],
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
    request: CreateCategoryRequest,
):
    """Create a new category."""
    cat = LeadCategory(
        tenant_id=tenant_id,
        name=request.name,
        description=request.description,
        parent_id=request.parent_id,
        color=request.color,
        is_active=request.is_active if request.is_active is not None else True,
        metadata=request.metadata or {},
    )
    saved = await repo.add(cat)
    return _category_to_response(saved)


@router.get("/categories/{category_id}", response_model=CategoryResponse)
async def get_category(
    category_id: UUID,
    repo: Annotated[LeadCategoryRepository, Depends(get_category_repository)],
):
    """Get category by ID."""
    cat = await repo.get(category_id)
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")
    return _category_to_response(cat)


@router.put("/categories/{category_id}", response_model=CategoryResponse)
async def update_category(
    category_id: UUID,
    repo: Annotated[LeadCategoryRepository, Depends(get_category_repository)],
    request: UpdateCategoryRequest,
):
    """Update an existing category."""
    cat = await repo.get(category_id)
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")
    update_data = request.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        if hasattr(cat, key):
            setattr(cat, key, value)
    saved = await repo.update(cat)
    return _category_to_response(saved)


@router.delete("/categories/{category_id}", status_code=204)
async def delete_category(
    category_id: UUID,
    repo: Annotated[LeadCategoryRepository, Depends(get_category_repository)],
):
    """Delete a category."""
    deleted = await repo.delete(category_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Category not found")


# ============================================================================
# Source Endpoints
# ============================================================================

@router.get("/sources", response_model=SourceListResponse)
async def list_sources(
    repo: Annotated[LeadSourceRepository, Depends(get_lead_source_repository)],
    include_inactive: bool = Query(default=False),
):
    """List all lead sources."""
    if include_inactive:
        sources = await repo.get_all()
    else:
        sources = await repo.get_active_sources()
    items = [
        SourceResponse(
            id=s.id, tenant_id=s.tenant_id, name=s.name,
            source_type=s.source_type.value if hasattr(s.source_type, 'value') else s.source_type,
            file_path=s.file_path, category_id=s.category_id,
            is_active=s.is_active, last_import_at=s.last_import_at,
            total_leads=s.total_leads, metadata=s.metadata,
            created_at=s.created_at, updated_at=s.updated_at,
        )
        for s in sources
    ]
    return SourceListResponse(sources=items, total_count=len(items))


@router.post("/sources", response_model=SourceResponse, status_code=201)
async def create_source(
    repo: Annotated[LeadSourceRepository, Depends(get_lead_source_repository)],
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
    request: CreateSourceRequest,
):
    """Create a new lead source."""
    from src.core.domain import LeadSource
    source = LeadSourceConfig(
        tenant_id=tenant_id,
        name=request.name,
        source_type=LeadSource(request.source_type),
        file_path=request.file_path,
        category_id=request.category_id,
        is_active=request.is_active if request.is_active is not None else True,
        metadata=request.metadata or {},
    )
    saved = await repo.add(source)
    return SourceResponse(
        id=saved.id, tenant_id=saved.tenant_id, name=saved.name,
        source_type=saved.source_type.value if hasattr(saved.source_type, 'value') else saved.source_type,
        file_path=saved.file_path, category_id=saved.category_id,
        is_active=saved.is_active, total_leads=saved.total_leads,
        metadata=saved.metadata, created_at=saved.created_at,
    )


@router.get("/sources/{source_id}", response_model=SourceResponse)
async def get_source(
    source_id: UUID,
    repo: Annotated[LeadSourceRepository, Depends(get_lead_source_repository)],
):
    """Get source by ID."""
    source = await repo.get(source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    return SourceResponse(
        id=source.id, tenant_id=source.tenant_id, name=source.name,
        source_type=source.source_type.value if hasattr(source.source_type, 'value') else source.source_type,
        file_path=source.file_path, category_id=source.category_id,
        is_active=source.is_active, total_leads=source.total_leads,
        metadata=source.metadata, created_at=source.created_at,
    )


@router.put("/sources/{source_id}", response_model=SourceResponse)
async def update_source(
    source_id: UUID,
    repo: Annotated[LeadSourceRepository, Depends(get_lead_source_repository)],
    request: UpdateSourceRequest,
):
    """Update an existing source."""
    source = await repo.get(source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    update_data = request.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        if hasattr(source, key):
            setattr(source, key, value)
    saved = await repo.update(source)
    return SourceResponse(
        id=saved.id, tenant_id=saved.tenant_id, name=saved.name,
        source_type=saved.source_type.value if hasattr(saved.source_type, 'value') else saved.source_type,
        file_path=saved.file_path, category_id=saved.category_id,
        is_active=saved.is_active, total_leads=saved.total_leads,
        metadata=saved.metadata, created_at=saved.created_at,
    )


@router.delete("/sources/{source_id}", status_code=204)
async def delete_source(
    source_id: UUID,
    repo: Annotated[LeadSourceRepository, Depends(get_lead_source_repository)],
):
    """Delete a source."""
    await repo.delete(source_id)


@router.post("/sources/{source_id}/sync", response_model=BulkImportResponse)
async def sync_source(
    source_id: UUID,
    repo: Annotated[LeadSourceRepository, Depends(get_lead_source_repository)],
):
    """Sync/reimport contacts from a source."""
    source = await repo.get(source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    # TODO: Trigger ETL pipeline
    return BulkImportResponse(total_submitted=0, success_count=0, error_count=0, duplicate_count=0)


# ============================================================================
# Search Endpoints
# ============================================================================

@router.post("/contacts/search", response_model=ContactListResponse)
async def search_contacts(
    repo: Annotated[ContactRepository, Depends(get_contact_repository)],
    request: ContactSearchRequest,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    """Advanced search for contacts."""
    skip = (page - 1) * page_size
    query = request.query if hasattr(request, 'query') else ""
    contacts = await repo.search(query, skip=skip, limit=page_size)
    return ContactListResponse(
        contacts=[_contact_to_response(c) for c in contacts],
        total_count=len(contacts),
        page=page,
        page_size=page_size,
        has_next=len(contacts) == page_size,
        has_prev=page > 1,
    )


@router.get("/contacts/by-phone/{phone_number}", response_model=ContactResponse)
async def get_contact_by_phone(
    phone_number: str,
    repo: Annotated[ContactRepository, Depends(get_contact_repository)],
):
    """Get contact by phone number."""
    contact = await repo.get_by_phone(phone_number)
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    return _contact_to_response(contact)


# ============================================================================
# Statistics Endpoints
# ============================================================================

@router.get("/stats/summary")
async def get_leads_summary(
    repo: Annotated[ContactRepository, Depends(get_contact_repository)],
):
    """Get summary statistics for leads."""
    total = await repo.count()
    active = await repo.count(is_active=True)
    blocked = await repo.count(is_blocked=True)

    return {
        "total_contacts": total,
        "active_contacts": active,
        "blocked_contacts": blocked,
        "unassigned_contacts": 0,  # TODO: count where assigned_to is null
    }


@router.get("/stats/by-salesperson")
async def get_leads_by_salesperson(
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
    repo: Annotated[ContactRepository, Depends(get_contact_repository)],
):
    """Get lead distribution by salesperson."""
    # TODO: aggregate query by salesperson
    return {"salespeople": []}
