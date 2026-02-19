"""
Leads Module - Domain Layer
Entities and business logic for lead management
"""

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import Field

from src.core.domain import (
    LeadSource,
    PhoneNumber,
    TenantAggregateRoot,
    TenantEntity,
    LeadCreatedEvent,
    LeadCategorizedEvent,
    LeadAssignedEvent,
)


class LeadCategory(TenantEntity[UUID]):
    """
    Category for organizing leads.
    Examples: سازندگان، خریداران سیمان، پیمانکاران
    """

    id: UUID = Field(default_factory=uuid4)
    name: str
    description: str | None = None
    parent_id: UUID | None = None  # For hierarchical categories
    color: str | None = None  # For UI display
    is_active: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class LeadSourceConfig(TenantEntity[UUID]):
    """
    Configuration for a lead source (file, API, etc.).
    """

    id: UUID = Field(default_factory=uuid4)
    name: str  # e.g., "تهران بردبار", "خریداران سیمان"
    source_type: LeadSource
    file_path: str | None = None
    category_id: UUID | None = None
    is_active: bool = True
    last_import_at: datetime | None = None
    total_leads: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)


class Contact(TenantAggregateRoot[UUID]):
    """
    Contact aggregate - represents a phone number with associated data.
    This is the core entity that moves through the funnel.
    """

    id: UUID = Field(default_factory=uuid4)
    phone_number: PhoneNumber
    name: str | None = None
    email: str | None = None

    # Source and categorization
    source_id: UUID | None = None
    source_name: str | None = None
    category_id: UUID | None = None
    category_name: str | None = None

    # Assignment
    assigned_to: UUID | None = None  # Salesperson ID
    assigned_at: datetime | None = None

    # Funnel tracking
    current_stage: str = "lead_acquired"
    stage_entered_at: datetime = Field(default_factory=datetime.utcnow)

    # RFM data (calculated)
    rfm_segment: str | None = None
    rfm_score: str | None = None  # e.g., "545"
    recency_score: int | None = None
    frequency_score: int | None = None
    monetary_score: int | None = None
    last_rfm_update: datetime | None = None

    # Engagement metrics
    total_sms_sent: int = 0
    total_sms_delivered: int = 0
    total_calls: int = 0
    total_answered_calls: int = 0
    total_call_duration: int = 0  # seconds

    # Sales metrics
    total_invoices: int = 0
    total_paid_invoices: int = 0
    total_revenue: int = 0  # In Rial
    last_purchase_at: datetime | None = None
    first_purchase_at: datetime | None = None

    # Status
    is_active: bool = True
    is_blocked: bool = False
    blocked_reason: str | None = None

    # Additional data
    tags: list[str] = Field(default_factory=list)
    custom_fields: dict[str, Any] = Field(default_factory=dict)
    notes: str | None = None

    def assign_category(self, category_id: UUID, category_name: str) -> None:
        """Assign contact to a category."""
        old_category = self.category_name
        self.category_id = category_id
        self.category_name = category_name

        self.add_domain_event(
            LeadCategorizedEvent(
                aggregate_id=self.id,
                tenant_id=self.tenant_id,
                phone_number=self.phone_number.normalized,
                old_category=old_category,
                new_category=category_name,
            )
        )

    def assign_to_salesperson(
        self,
        salesperson_id: UUID,
        salesperson_name: str,
    ) -> None:
        """Assign contact to a salesperson."""
        self.assigned_to = salesperson_id
        self.assigned_at = datetime.utcnow()

        self.add_domain_event(
            LeadAssignedEvent(
                aggregate_id=self.id,
                tenant_id=self.tenant_id,
                phone_number=self.phone_number.normalized,
                salesperson_id=salesperson_id,
                salesperson_name=salesperson_name,
            )
        )

    def update_stage(self, new_stage: str) -> None:
        """Update funnel stage."""
        if new_stage != self.current_stage:
            self.current_stage = new_stage
            self.stage_entered_at = datetime.utcnow()

    def record_sms_sent(self, delivered: bool = False) -> None:
        """Record an SMS being sent."""
        self.total_sms_sent += 1
        if delivered:
            self.total_sms_delivered += 1

        # Update stage if this is the first SMS
        if self.current_stage == "lead_acquired":
            self.update_stage("sms_sent")

    def record_call(
        self,
        duration_seconds: int,
        is_answered: bool,
        min_duration_threshold: int = 90,
    ) -> None:
        """Record a call."""
        self.total_calls += 1
        self.total_call_duration += duration_seconds

        if is_answered and duration_seconds >= min_duration_threshold:
            self.total_answered_calls += 1
            if self.current_stage in ["lead_acquired", "sms_sent", "sms_delivered", "call_attempted"]:
                self.update_stage("call_answered")
        elif self.current_stage in ["lead_acquired", "sms_sent", "sms_delivered"]:
            self.update_stage("call_attempted")

    def record_invoice(self, amount: int, is_paid: bool = False) -> None:
        """Record an invoice."""
        self.total_invoices += 1

        if is_paid:
            self.total_paid_invoices += 1
            self.total_revenue += amount
            now = datetime.utcnow()
            self.last_purchase_at = now
            if self.first_purchase_at is None:
                self.first_purchase_at = now
            self.update_stage("payment_received")
        else:
            if self.current_stage not in ["invoice_issued", "payment_received"]:
                self.update_stage("invoice_issued")

    def block(self, reason: str | None = None) -> None:
        """Block contact from receiving messages."""
        self.is_blocked = True
        self.blocked_reason = reason

    def unblock(self) -> None:
        """Unblock contact."""
        self.is_blocked = False
        self.blocked_reason = None

    @classmethod
    def create(
        cls,
        tenant_id: UUID,
        phone: str,
        source_id: UUID | None = None,
        source_name: str | None = None,
        name: str | None = None,
        category_id: UUID | None = None,
        category_name: str | None = None,
    ) -> "Contact":
        """Factory method to create a new contact."""
        phone_number = PhoneNumber.from_string(phone)
        contact = cls(
            tenant_id=tenant_id,
            phone_number=phone_number,
            name=name,
            source_id=source_id,
            source_name=source_name,
            category_id=category_id,
            category_name=category_name,
        )

        contact.add_domain_event(
            LeadCreatedEvent(
                aggregate_id=contact.id,
                tenant_id=tenant_id,
                phone_number=phone_number.normalized,
                source_name=source_name or "unknown",
                category=category_name,
            )
        )

        return contact

