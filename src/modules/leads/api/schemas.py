"""
Leads API Schemas

Pydantic schemas for leads module API endpoints.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


# ============================================================================
# Contact Schemas
# ============================================================================

class ContactBase(BaseModel):
    """Base schema for contact data."""
    phone_number: str
    name: str | None = None
    email: str | None = None
    source_name: str | None = None
    category_name: str | None = None
    tags: list[str] = Field(default_factory=list)
    custom_fields: dict[str, Any] = Field(default_factory=dict)
    notes: str | None = None


class CreateContactRequest(ContactBase):
    """Schema for creating a new contact."""
    category_id: UUID | None = None
    source_id: UUID | None = None
    assigned_to: UUID | None = None


class UpdateContactRequest(BaseModel):
    """Schema for updating an existing contact."""
    name: str | None = None
    email: str | None = None
    category_id: UUID | None = None
    category_name: str | None = None
    assigned_to: UUID | None = None
    tags: list[str] | None = None
    custom_fields: dict[str, Any] | None = None
    notes: str | None = None
    is_blocked: bool | None = None
    blocked_reason: str | None = None


class ContactResponse(BaseModel):
    """Schema for contact response."""
    id: UUID
    tenant_id: UUID
    phone_number: str
    name: str | None = None
    email: str | None = None

    # Source and categorization
    source_id: UUID | None = None
    source_name: str | None = None
    category_id: UUID | None = None
    category_name: str | None = None

    # Assignment
    assigned_to: UUID | None = None
    assigned_at: datetime | None = None

    # Funnel tracking
    current_stage: str
    stage_entered_at: datetime

    # RFM data
    rfm_segment: str | None = None
    rfm_score: str | None = None

    # Engagement metrics
    total_sms_sent: int = 0
    total_sms_delivered: int = 0
    total_calls: int = 0
    total_answered_calls: int = 0
    total_call_duration: int = 0

    # Sales metrics
    total_invoices: int = 0
    total_paid_invoices: int = 0
    total_revenue: int = 0
    last_purchase_at: datetime | None = None
    first_purchase_at: datetime | None = None

    # Status
    is_active: bool
    is_blocked: bool
    blocked_reason: str | None = None

    # Additional data
    tags: list[str] = Field(default_factory=list)
    custom_fields: dict[str, Any] = Field(default_factory=dict)
    notes: str | None = None

    # Timestamps
    created_at: datetime
    updated_at: datetime | None = None

    class Config:
        from_attributes = True


class ContactListResponse(BaseModel):
    """Schema for paginated contact list."""
    contacts: list[ContactResponse]
    total_count: int
    page: int
    page_size: int
    has_next: bool
    has_prev: bool


class ContactStageUpdateRequest(BaseModel):
    """Schema for updating contact's funnel stage."""
    stage: str


# ============================================================================
# Bulk Import Schemas
# ============================================================================

class BulkImportRequest(BaseModel):
    """Schema for bulk import request."""
    source_id: UUID | None = None
    source_name: str | None = None
    category_id: UUID | None = None
    category_name: str | None = None
    assigned_to: UUID | None = None
    contacts: list[CreateContactRequest]
    skip_duplicates: bool = True


class BulkImportResponse(BaseModel):
    """Schema for bulk import response."""
    total_submitted: int
    success_count: int
    error_count: int
    duplicate_count: int
    errors: list[str] = Field(default_factory=list)
    created_contacts: list[UUID] = Field(default_factory=list)


# ============================================================================
# Lead Category Schemas
# ============================================================================

class CategoryBase(BaseModel):
    """Base schema for lead category."""
    name: str
    description: str | None = None
    color: str | None = None
    is_active: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class CreateCategoryRequest(CategoryBase):
    """Schema for creating a new category."""
    parent_id: UUID | None = None


class UpdateCategoryRequest(BaseModel):
    """Schema for updating a category."""
    name: str | None = None
    description: str | None = None
    color: str | None = None
    parent_id: UUID | None = None
    is_active: bool | None = None
    metadata: dict[str, Any] | None = None


class CategoryResponse(CategoryBase):
    """Schema for category response."""
    id: UUID
    tenant_id: UUID
    parent_id: UUID | None = None
    contact_count: int = 0
    created_at: datetime
    updated_at: datetime | None = None

    class Config:
        from_attributes = True


class CategoryListResponse(BaseModel):
    """Schema for category list response."""
    categories: list[CategoryResponse]
    total_count: int


class CategoryTreeResponse(BaseModel):
    """Schema for hierarchical category tree."""
    id: UUID
    name: str
    description: str | None = None
    color: str | None = None
    contact_count: int = 0
    children: list["CategoryTreeResponse"] = Field(default_factory=list)


# ============================================================================
# Lead Source Schemas
# ============================================================================

class SourceBase(BaseModel):
    """Base schema for lead source."""
    name: str
    source_type: str  # file, api, manual, etc.
    file_path: str | None = None
    is_active: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class CreateSourceRequest(SourceBase):
    """Schema for creating a new source."""
    category_id: UUID | None = None


class UpdateSourceRequest(BaseModel):
    """Schema for updating a source."""
    name: str | None = None
    source_type: str | None = None
    file_path: str | None = None
    category_id: UUID | None = None
    is_active: bool | None = None
    metadata: dict[str, Any] | None = None


class SourceResponse(SourceBase):
    """Schema for source response."""
    id: UUID
    tenant_id: UUID
    category_id: UUID | None = None
    last_import_at: datetime | None = None
    total_leads: int = 0
    created_at: datetime
    updated_at: datetime | None = None

    class Config:
        from_attributes = True


class SourceListResponse(BaseModel):
    """Schema for source list response."""
    sources: list[SourceResponse]
    total_count: int


# ============================================================================
# Assignment Schemas
# ============================================================================

class BulkAssignRequest(BaseModel):
    """Schema for bulk assignment request."""
    contact_ids: list[UUID]
    salesperson_id: UUID


class BulkAssignResponse(BaseModel):
    """Schema for bulk assignment response."""
    success_count: int
    error_count: int
    errors: list[str] = Field(default_factory=list)


class AutoAssignRequest(BaseModel):
    """Schema for auto-assignment request."""
    category_id: UUID | None = None
    source_id: UUID | None = None
    assignment_strategy: str = "round_robin"  # round_robin, balanced, region_based


class AutoAssignResponse(BaseModel):
    """Schema for auto-assignment response."""
    total_assigned: int
    assignments: dict[UUID, int]  # salesperson_id -> count


# ============================================================================
# Search and Filter Schemas
# ============================================================================

class ContactSearchRequest(BaseModel):
    """Schema for contact search request."""
    query: str | None = None
    phone_number: str | None = None
    category_id: UUID | None = None
    source_id: UUID | None = None
    segment: str | None = None
    stage: str | None = None
    salesperson_id: UUID | None = None
    is_active: bool | None = None
    is_blocked: bool | None = None
    has_rfm: bool | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None
    tags: list[str] | None = None

