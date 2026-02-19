"""
Core Domain Events
Events that can be published across bounded contexts
"""

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import Field

from .entities import DomainEvent


class EventCategory(str, Enum):
    """Categories of domain events."""

    LEAD = "lead"
    COMMUNICATION = "communication"
    SALES = "sales"
    SEGMENT = "segment"
    CAMPAIGN = "campaign"
    SYSTEM = "system"


# Lead Events


class LeadCreatedEvent(DomainEvent):
    """Event raised when a new lead/contact is created."""

    event_type: str = "lead.created"
    aggregate_type: str = "Lead"
    phone_number: str
    source_name: str
    category: str | None = None


class LeadCategorizedEvent(DomainEvent):
    """Event raised when a lead is assigned to a category."""

    event_type: str = "lead.categorized"
    aggregate_type: str = "Lead"
    phone_number: str
    old_category: str | None = None
    new_category: str


class LeadAssignedEvent(DomainEvent):
    """Event raised when a lead is assigned to a salesperson."""

    event_type: str = "lead.assigned"
    aggregate_type: str = "Lead"
    phone_number: str
    salesperson_id: UUID
    salesperson_name: str


# Communication Events


class SMSSentEvent(DomainEvent):
    """Event raised when an SMS is sent."""

    event_type: str = "communication.sms_sent"
    aggregate_type: str = "Communication"
    phone_number: str
    template_id: UUID | None = None
    message_preview: str
    campaign_id: UUID | None = None


class SMSDeliveredEvent(DomainEvent):
    """Event raised when SMS delivery is confirmed."""

    event_type: str = "communication.sms_delivered"
    aggregate_type: str = "Communication"
    phone_number: str
    message_id: str


class SMSFailedEvent(DomainEvent):
    """Event raised when SMS delivery fails."""

    event_type: str = "communication.sms_failed"
    aggregate_type: str = "Communication"
    phone_number: str
    message_id: str
    failure_reason: str


class CallReceivedEvent(DomainEvent):
    """Event raised when a call is logged."""

    event_type: str = "communication.call_received"
    aggregate_type: str = "Communication"
    phone_number: str
    call_type: str  # incoming, outgoing, missed
    duration_seconds: int
    salesperson_id: UUID | None = None
    is_successful: bool  # True if duration >= threshold


class CallAnsweredEvent(DomainEvent):
    """Event raised when a call meets the success threshold."""

    event_type: str = "communication.call_answered"
    aggregate_type: str = "Communication"
    phone_number: str
    duration_seconds: int
    salesperson_id: UUID | None = None


# Sales Events


class InvoiceCreatedEvent(DomainEvent):
    """Event raised when a pre-invoice is created."""

    event_type: str = "sales.invoice_created"
    aggregate_type: str = "Invoice"
    phone_number: str
    invoice_number: str
    total_amount: int  # In Rial
    products: list[dict[str, Any]]


class InvoicePaidEvent(DomainEvent):
    """Event raised when an invoice is paid."""

    event_type: str = "sales.invoice_paid"
    aggregate_type: str = "Invoice"
    phone_number: str
    invoice_number: str
    payment_amount: int
    payment_method: str | None = None


class InvoiceCancelledEvent(DomainEvent):
    """Event raised when an invoice is cancelled."""

    event_type: str = "sales.invoice_cancelled"
    aggregate_type: str = "Invoice"
    phone_number: str
    invoice_number: str
    cancellation_reason: str | None = None


# Segment Events


class ContactSegmentChangedEvent(DomainEvent):
    """Event raised when a contact's RFM segment changes."""

    event_type: str = "segment.contact_changed"
    aggregate_type: str = "Segment"
    phone_number: str
    old_segment: str | None = None
    new_segment: str
    rfm_score: str  # e.g., "545"
    recency_score: int
    frequency_score: int
    monetary_score: int


class SegmentRecommendationEvent(DomainEvent):
    """Event raised with product/action recommendations for a segment."""

    event_type: str = "segment.recommendation"
    aggregate_type: str = "Segment"
    segment_name: str
    recommended_products: list[str]
    recommended_action: str
    recommended_template_ids: list[UUID]


# Campaign Events


class CampaignCreatedEvent(DomainEvent):
    """Event raised when a campaign is created."""

    event_type: str = "campaign.created"
    aggregate_type: str = "Campaign"
    campaign_name: str
    target_segment: str | None = None
    scheduled_at: datetime | None = None


class CampaignStartedEvent(DomainEvent):
    """Event raised when a campaign starts sending."""

    event_type: str = "campaign.started"
    aggregate_type: str = "Campaign"
    campaign_name: str
    total_recipients: int


class CampaignCompletedEvent(DomainEvent):
    """Event raised when a campaign finishes."""

    event_type: str = "campaign.completed"
    aggregate_type: str = "Campaign"
    campaign_name: str
    total_sent: int
    total_delivered: int
    total_failed: int


# Funnel Events


class FunnelStageProgressedEvent(DomainEvent):
    """Event raised when a contact progresses through funnel stages."""

    event_type: str = "funnel.stage_progressed"
    aggregate_type: str = "FunnelProgress"
    phone_number: str
    from_stage: str
    to_stage: str
    days_in_previous_stage: int | None = None


class ConversionEvent(DomainEvent):
    """Event raised when a full funnel conversion occurs."""

    event_type: str = "funnel.conversion"
    aggregate_type: str = "FunnelProgress"
    phone_number: str
    total_days_to_convert: int
    total_amount: int
    attribution_source: str | None = None


# System Events


class DataImportCompletedEvent(DomainEvent):
    """Event raised when a data import job completes."""

    event_type: str = "system.import_completed"
    aggregate_type: str = "DataImport"
    import_type: str  # leads, sms_logs, call_logs, etc.
    source_name: str
    records_imported: int
    records_failed: int
    errors: list[str] = Field(default_factory=list)


class AlertTriggeredEvent(DomainEvent):
    """Event raised when an alert condition is met."""

    event_type: str = "system.alert_triggered"
    aggregate_type: str = "Alert"
    alert_name: str
    alert_type: str
    severity: str  # info, warning, critical
    message: str
    metric_value: float | None = None
    threshold_value: float | None = None

