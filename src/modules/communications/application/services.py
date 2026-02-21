"""
Communications Application Services

Business logic for SMS and call management.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from src.modules.communications.domain.entities import CallLog, SMSLog, SMSTemplate
from src.modules.communications.domain.repositories import (
    ICallLogRepository,
    ISMSLogRepository,
    ISMSTemplateRepository,
)
from src.modules.leads.domain.repositories import IContactRepository


class SMSService:
    """Service for SMS operations."""

    def __init__(
        self,
        sms_log_repo: ISMSLogRepository,
        template_repo: ISMSTemplateRepository,
        contact_repo: IContactRepository,
    ):
        self._sms_log_repo = sms_log_repo
        self._template_repo = template_repo
        self._contact_repo = contact_repo

    async def send_sms(
        self,
        tenant_id: UUID,
        phone_number: str,
        content: str,
        contact_id: UUID | None = None,
        template_id: UUID | None = None,
        campaign_id: UUID | None = None,
        provider_name: str = "kavenegar",
    ) -> SMSLog:
        """Send a single SMS."""
        # Create SMS log
        sms_log = SMSLog.create_outbound(
            tenant_id=tenant_id,
            phone_number=phone_number,
            content=content,
            contact_id=contact_id,
            template_id=template_id,
            campaign_id=campaign_id,
            provider_name=provider_name,
        )

        # TODO: Actually send via provider
        # For now, mark as sent
        sms_log.mark_sent(provider_message_id=f"msg_{sms_log.id}")

        await self._sms_log_repo.add(sms_log)

        # Update contact engagement metrics
        if contact_id:
            contact = await self._contact_repo.get(contact_id)
            if contact:
                contact.record_sms_sent(delivered=False)
                await self._contact_repo.update(contact)

        # Update template usage
        if template_id:
            template = await self._template_repo.get(template_id)
            if template:
                template.times_used += 1
                template.last_used_at = datetime.utcnow()
                await self._template_repo.update(template)

        return sms_log

    async def bulk_send_sms(
        self,
        tenant_id: UUID,
        recipients: list[dict[str, Any]],
        content: str | None = None,
        template_id: UUID | None = None,
        campaign_id: UUID | None = None,
    ) -> tuple[int, list[UUID]]:
        """
        Bulk send SMS to multiple recipients.
        Returns (queued_count, job_ids).
        """
        # Get template content if template_id provided
        if template_id and not content:
            template = await self._template_repo.get(template_id)
            if template:
                content = template.content

        if not content:
            raise ValueError("Either content or template_id must be provided")

        queued_count = 0
        sms_logs: list[SMSLog] = []

        for recipient in recipients:
            phone = recipient.get("phone_number")
            contact_id = recipient.get("contact_id")

            if not phone:
                continue

            # Personalize content if variables provided
            personalized_content = content
            if recipient.get("variables"):
                for key, value in recipient["variables"].items():
                    personalized_content = personalized_content.replace(f"{{{key}}}", str(value))

            sms_log = SMSLog.create_outbound(
                tenant_id=tenant_id,
                phone_number=phone,
                content=personalized_content,
                contact_id=contact_id,
                template_id=template_id,
                campaign_id=campaign_id,
            )
            sms_logs.append(sms_log)
            queued_count += 1

        # In production, this would queue to a message broker
        # For now, bulk create the logs
        if sms_logs:
            await self._sms_log_repo.bulk_create(sms_logs)

        return queued_count, []

    async def update_delivery_status(
        self,
        provider_message_id: str,
        status: str,
        failure_reason: str | None = None,
    ) -> SMSLog | None:
        """Update SMS delivery status from provider webhook."""
        sms_log = await self._sms_log_repo.get_by_provider_id(provider_message_id)
        if not sms_log:
            return None

        if status == "delivered":
            sms_log.mark_delivered()
            # Update contact metrics
            if sms_log.contact_id:
                contact = await self._contact_repo.get(sms_log.contact_id)
                if contact:
                    contact.total_sms_delivered += 1
                    if contact.current_stage == "sms_sent":
                        contact.update_stage("sms_delivered")
                    await self._contact_repo.update(contact)
        elif status == "failed":
            sms_log.mark_failed(failure_reason or "Unknown error")

        await self._sms_log_repo.update(sms_log)
        return sms_log


class CallLogService:
    """Service for call log management."""

    def __init__(
        self,
        call_log_repo: ICallLogRepository,
        contact_repo: IContactRepository,
    ):
        self._call_log_repo = call_log_repo
        self._contact_repo = contact_repo

    async def import_call_logs(
        self,
        tenant_id: UUID,
        calls_data: list[dict[str, Any]],
        successful_call_threshold: int = 90,
    ) -> tuple[int, int, int, int, list[str]]:
        """
        Import call logs.
        Returns (total, success_count, matched_contacts, new_contacts, errors).
        """
        success_count = 0
        matched_contacts = 0
        new_contacts = 0
        errors: list[str] = []

        for idx, data in enumerate(calls_data):
            try:
                phone_number = data.get("phone_number", "").strip()
                if not phone_number:
                    errors.append(f"Row {idx + 1}: Missing phone number")
                    continue

                # Try to match contact
                contact = await self._contact_repo.get_by_phone(phone_number)
                contact_id = contact.id if contact else None

                if contact:
                    matched_contacts += 1

                # Determine if call was successful
                duration = data.get("duration_seconds", 0)
                is_answered = data.get("is_answered", duration > 0)
                is_successful = is_answered and duration >= successful_call_threshold

                call_log = CallLog(
                    tenant_id=tenant_id,
                    contact_id=contact_id,
                    phone_number=phone_number,
                    contact_name=data.get("contact_name"),
                    call_type=data.get("call_type", "outbound"),
                    source=data.get("source", "mobile"),
                    duration_seconds=duration,
                    call_time=data.get("call_time", datetime.utcnow()),
                    salesperson_id=data.get("salesperson_id"),
                    salesperson_phone=data.get("salesperson_phone"),
                    salesperson_name=data.get("salesperson_name"),
                    is_answered=is_answered,
                    is_successful=is_successful,
                    voip_unique_id=data.get("voip_unique_id"),
                    recording_url=data.get("recording_url"),
                )

                await self._call_log_repo.add(call_log)
                success_count += 1

                # Update contact metrics
                if contact:
                    contact.record_call(duration, is_answered, successful_call_threshold)
                    await self._contact_repo.update(contact)

            except Exception as e:
                errors.append(f"Row {idx + 1}: {str(e)}")

        return len(calls_data), success_count, matched_contacts, new_contacts, errors


class SMSTemplateService:
    """Service for SMS template management."""

    def __init__(self, template_repo: ISMSTemplateRepository):
        self._template_repo = template_repo

    async def create_template(
        self,
        tenant_id: UUID,
        name: str,
        content: str,
        description: str | None = None,
        category: str | None = None,
        target_segments: list[str] | None = None,
        target_products: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> SMSTemplate:
        """Create an SMS template."""
        template = SMSTemplate(
            tenant_id=tenant_id,
            name=name,
            content=content,
            description=description,
            category=category,
            target_segments=target_segments or [],
            target_products=target_products or [],
            metadata=metadata or {},
        )

        await self._template_repo.add(template)
        return template

    async def get_templates_for_segment(
        self,
        tenant_id: UUID,
        segment: str,
    ) -> list[SMSTemplate]:
        """Get templates recommended for a segment."""
        return await self._template_repo.get_by_segment(segment)

