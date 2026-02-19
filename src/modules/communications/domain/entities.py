"""
Communications Module - Domain Layer
Entities for SMS and Call tracking
"""

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import Field

from src.core.domain import (
    CallSource,
    CallType,
    SMSDirection,
    SMSStatus,
    TenantAggregateRoot,
    TenantEntity,
    CallAnsweredEvent,
    CallReceivedEvent,
    SMSDeliveredEvent,
    SMSFailedEvent,
    SMSSentEvent,
)


class SMSTemplate(TenantEntity[UUID]):
    """
    SMS message template.
    Used for campaign and automated messages.
    """

    id: UUID = Field(default_factory=uuid4)
    name: str
    content: str
    description: str | None = None

    # Categorization
    category: str | None = None  # welcome, follow_up, promotion, etc.
    target_segments: list[str] = Field(default_factory=list)  # RFM segments
    target_products: list[str] = Field(default_factory=list)

    # Usage stats
    times_used: int = 0
    last_used_at: datetime | None = None

    # A/B testing
    variant_group: str | None = None
    variant_name: str | None = None

    is_active: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def character_count(self) -> int:
        """Get character count of content."""
        return len(self.content)

    @property
    def sms_parts(self) -> int:
        """Calculate number of SMS parts (for Persian text)."""
        # Persian SMS: 70 chars for 1 part, 67 chars per part for multi-part
        length = len(self.content)
        if length <= 70:
            return 1
        return (length + 66) // 67


class SMSLog(TenantAggregateRoot[UUID]):
    """
    SMS communication log.
    Records all SMS sent and received.
    """

    id: UUID = Field(default_factory=uuid4)

    # Contact reference
    contact_id: UUID | None = None
    phone_number: str  # Normalized phone number

    # Message details
    direction: SMSDirection
    content: str
    template_id: UUID | None = None

    # Delivery tracking
    status: SMSStatus = SMSStatus.PENDING
    provider_message_id: str | None = None
    sent_at: datetime | None = None
    delivered_at: datetime | None = None
    failed_at: datetime | None = None
    failure_reason: str | None = None

    # Campaign reference
    campaign_id: UUID | None = None

    # Provider info
    provider_name: str | None = None  # kavenegar, etc.
    cost: int = 0  # Cost in Rial

    metadata: dict[str, Any] = Field(default_factory=dict)

    def mark_sent(self, provider_message_id: str | None = None) -> None:
        """Mark SMS as sent."""
        self.status = SMSStatus.SENT
        self.sent_at = datetime.utcnow()
        self.provider_message_id = provider_message_id

        self.add_domain_event(
            SMSSentEvent(
                aggregate_id=self.id,
                tenant_id=self.tenant_id,
                phone_number=self.phone_number,
                template_id=self.template_id,
                message_preview=self.content[:50],
                campaign_id=self.campaign_id,
            )
        )

    def mark_delivered(self) -> None:
        """Mark SMS as delivered."""
        self.status = SMSStatus.DELIVERED
        self.delivered_at = datetime.utcnow()

        self.add_domain_event(
            SMSDeliveredEvent(
                aggregate_id=self.id,
                tenant_id=self.tenant_id,
                phone_number=self.phone_number,
                message_id=self.provider_message_id or str(self.id),
            )
        )

    def mark_failed(self, reason: str) -> None:
        """Mark SMS as failed."""
        self.status = SMSStatus.FAILED
        self.failed_at = datetime.utcnow()
        self.failure_reason = reason

        self.add_domain_event(
            SMSFailedEvent(
                aggregate_id=self.id,
                tenant_id=self.tenant_id,
                phone_number=self.phone_number,
                message_id=self.provider_message_id or str(self.id),
                failure_reason=reason,
            )
        )

    @classmethod
    def create_outbound(
        cls,
        tenant_id: UUID,
        phone_number: str,
        content: str,
        contact_id: UUID | None = None,
        template_id: UUID | None = None,
        campaign_id: UUID | None = None,
        provider_name: str | None = None,
    ) -> "SMSLog":
        """Factory method to create outbound SMS."""
        return cls(
            tenant_id=tenant_id,
            contact_id=contact_id,
            phone_number=phone_number,
            direction=SMSDirection.OUTBOUND,
            content=content,
            template_id=template_id,
            campaign_id=campaign_id,
            provider_name=provider_name,
        )


class CallLog(TenantAggregateRoot[UUID]):
    """
    Call communication log.
    Records all calls from mobile phones and VoIP.
    """

    id: UUID = Field(default_factory=uuid4)

    # Contact reference
    contact_id: UUID | None = None
    phone_number: str  # Normalized phone number
    contact_name: str | None = None  # Name from phone book if available

    # Call details
    call_type: CallType
    source: CallSource  # mobile or voip
    duration_seconds: int = 0

    # Timing
    call_time: datetime
    answered_at: datetime | None = None
    ended_at: datetime | None = None

    # Salesperson
    salesperson_id: UUID | None = None
    salesperson_phone: str | None = None
    salesperson_name: str | None = None

    # VoIP specific
    voip_extension: str | None = None
    voip_call_id: str | None = None
    recording_url: str | None = None

    # Status (calculated)
    is_successful: bool = False  # True if answered and duration >= threshold

    # Raw data reference
    raw_data: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    def evaluate_success(self, min_duration_seconds: int = 90) -> None:
        """
        Evaluate if call is successful based on threshold.
        Default threshold is 90 seconds (1.5 minutes).
        """
        self.is_successful = (
            self.call_type in [CallType.INCOMING, CallType.OUTGOING]
            and self.duration_seconds >= min_duration_seconds
        )

    @classmethod
    def from_mobile_log(
        cls,
        tenant_id: UUID,
        phone_number: str,
        call_type: str,
        duration_seconds: int,
        call_time: datetime,
        salesperson_id: UUID | None = None,
        salesperson_phone: str | None = None,
        contact_name: str | None = None,
        raw_data: dict | None = None,
        min_duration_threshold: int = 90,
    ) -> "CallLog":
        """Create from mobile phone call log."""
        # Map call type string to enum
        type_mapping = {
            "incoming": CallType.INCOMING,
            "incomming": CallType.INCOMING,  # Handle typo in data
            "outgoing": CallType.OUTGOING,
            "missed": CallType.MISSED,
        }
        mapped_type = type_mapping.get(call_type.lower(), CallType.MISSED)

        call = cls(
            tenant_id=tenant_id,
            phone_number=phone_number,
            contact_name=contact_name,
            call_type=mapped_type,
            source=CallSource.MOBILE,
            duration_seconds=duration_seconds,
            call_time=call_time,
            salesperson_id=salesperson_id,
            salesperson_phone=salesperson_phone,
            raw_data=raw_data or {},
        )

        call.evaluate_success(min_duration_threshold)

        # Add domain event
        call.add_domain_event(
            CallReceivedEvent(
                aggregate_id=call.id,
                tenant_id=tenant_id,
                phone_number=phone_number,
                call_type=mapped_type.value,
                duration_seconds=duration_seconds,
                salesperson_id=salesperson_id,
                is_successful=call.is_successful,
            )
        )

        if call.is_successful:
            call.add_domain_event(
                CallAnsweredEvent(
                    aggregate_id=call.id,
                    tenant_id=tenant_id,
                    phone_number=phone_number,
                    duration_seconds=duration_seconds,
                    salesperson_id=salesperson_id,
                )
            )

        return call

    @classmethod
    def from_voip_log(
        cls,
        tenant_id: UUID,
        phone_number: str,
        call_type: str,
        duration_seconds: int,
        call_time: datetime,
        extension: str | None = None,
        voip_call_id: str | None = None,
        recording_url: str | None = None,
        raw_data: dict | None = None,
        min_duration_threshold: int = 90,
    ) -> "CallLog":
        """Create from VoIP call log."""
        type_mapping = {
            "inbound": CallType.INCOMING,
            "incoming": CallType.INCOMING,
            "outbound": CallType.OUTGOING,
            "outgoing": CallType.OUTGOING,
            "missed": CallType.MISSED,
            "no-answer": CallType.MISSED,
            "busy": CallType.MISSED,
            "failed": CallType.MISSED,
        }
        mapped_type = type_mapping.get(call_type.lower(), CallType.MISSED)

        call = cls(
            tenant_id=tenant_id,
            phone_number=phone_number,
            call_type=mapped_type,
            source=CallSource.VOIP,
            duration_seconds=duration_seconds,
            call_time=call_time,
            voip_extension=extension,
            voip_call_id=voip_call_id,
            recording_url=recording_url,
            raw_data=raw_data or {},
        )

        call.evaluate_success(min_duration_threshold)

        # Add domain events
        call.add_domain_event(
            CallReceivedEvent(
                aggregate_id=call.id,
                tenant_id=tenant_id,
                phone_number=phone_number,
                call_type=mapped_type.value,
                duration_seconds=duration_seconds,
                salesperson_id=None,
                is_successful=call.is_successful,
            )
        )

        if call.is_successful:
            call.add_domain_event(
                CallAnsweredEvent(
                    aggregate_id=call.id,
                    tenant_id=tenant_id,
                    phone_number=phone_number,
                    duration_seconds=duration_seconds,
                    salesperson_id=None,
                )
            )

        return call

