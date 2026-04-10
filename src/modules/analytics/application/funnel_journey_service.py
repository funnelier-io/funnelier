"""
Funnel Journey Orchestration Service

Application service that manages contact funnel journeys via Camunda BPMS.
Starts a funnel_journey process for each contact and correlates domain events
(SMS sent, call answered, invoice issued, payment received) to advance the
contact through the funnel stages.

When Camunda is disabled the service falls back to direct DB updates so the
funnel stage tracking still works without the process engine.
"""

import logging
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.camunda.client import (
    CamundaClient,
    CamundaConnectionError,
    CamundaError,
)

logger = logging.getLogger(__name__)

# Default funnel stages mapping
FUNNEL_STAGES = [
    "lead_acquired",
    "sms_sent",
    "sms_delivered",
    "call_attempted",
    "call_answered",
    "invoice_issued",
    "payment_received",
]


class FunnelJourneyService:
    """
    Orchestrates contact funnel journeys via Camunda BPMS.

    When Camunda is enabled:
      - start_journey: starts funnel_journey process for a contact
      - correlate_event: correlates a domain event to advance the journey
      - get_journey_status: queries process variables for current state

    When disabled:
      - Falls back to direct DB updates for funnel stage tracking
    """

    def __init__(self, camunda_client: CamundaClient):
        self._camunda = camunda_client

    async def start_journey(
        self,
        contact_id: UUID,
        tenant_id: UUID,
        phone_number: str,
        contact_name: str | None = None,
    ) -> str | None:
        """
        Start a funnel journey process instance for a contact.

        Business key is the phone number (used for message correlation).
        Returns the process_instance_id or None.
        """
        if not self._camunda.enabled:
            return None

        try:
            instance = await self._camunda.start_process(
                process_key="funnel_journey",
                business_key=phone_number,
                variables={
                    "contact_id": str(contact_id),
                    "tenant_id": str(tenant_id),
                    "phone_number": phone_number,
                    "contact_name": contact_name or "",
                    "current_stage": "lead_acquired",
                    "journey_started_at": datetime.utcnow().isoformat(),
                },
                tenant_id=str(tenant_id),
            )
            logger.info(
                "Funnel journey started for contact %s (process=%s)",
                phone_number, instance.id,
            )
            return instance.id
        except (CamundaConnectionError, CamundaError) as e:
            logger.warning(
                "Camunda unavailable for funnel journey %s: %s", phone_number, e,
            )
            return None

    async def correlate_event(
        self,
        event_name: str,
        phone_number: str,
        tenant_id: UUID | None = None,
        variables: dict[str, Any] | None = None,
        session: AsyncSession | None = None,
    ) -> bool:
        """
        Correlate a domain event to advance a contact's funnel journey.

        Event names match BPMN message names:
            sms_sent, sms_delivered, call_attempted,
            call_answered, invoice_issued, payment_received

        Also updates the contact's current_stage in the database.

        Args:
            event_name: BPMN message name
            phone_number: Business key for correlation
            tenant_id: Optional tenant filter
            variables: Additional process variables
            session: Optional DB session for direct stage update

        Returns:
            True if event was correlated successfully
        """
        if event_name not in FUNNEL_STAGES[1:]:  # Skip lead_acquired (start)
            logger.warning("Unknown funnel event: %s", event_name)
            return False

        # Always update the DB stage (works with or without Camunda)
        if session and tenant_id:
            await self._update_contact_stage(
                session, phone_number, tenant_id, event_name,
            )

        if not self._camunda.enabled:
            return session is not None  # True if DB update was done

        try:
            event_vars = {
                "current_stage": event_name,
                f"{event_name}_at": datetime.utcnow().isoformat(),
                **(variables or {}),
            }
            await self._camunda.correlate_message(
                message_name=event_name,
                business_key=phone_number,
                tenant_id=str(tenant_id) if tenant_id else None,
                variables=event_vars,
            )
            logger.info(
                "Correlated funnel event '%s' for %s", event_name, phone_number,
            )
            return True
        except CamundaConnectionError as e:
            logger.warning("Camunda unreachable for event %s: %s", event_name, e)
            return session is not None  # Still True if DB was updated
        except CamundaError as e:
            # Could be "no matching process instance" — not a fatal error
            logger.debug(
                "Camunda correlate failed for %s/%s: %s",
                event_name, phone_number, e,
            )
            return session is not None

    async def _update_contact_stage(
        self,
        session: AsyncSession,
        phone_number: str,
        tenant_id: UUID,
        stage: str,
    ) -> bool:
        """
        Update a contact's funnel stage directly in the database.

        Args:
            session: Async DB session
            phone_number: Contact phone number
            tenant_id: Tenant UUID
            stage: New funnel stage name

        Returns:
            True if the contact was found and updated
        """
        from src.infrastructure.database.models.leads import ContactModel
        from sqlalchemy import update as sa_update

        now = datetime.utcnow()
        stmt = (
            sa_update(ContactModel)
            .where(ContactModel.phone_number == phone_number)
            .where(ContactModel.tenant_id == tenant_id)
            .values(current_stage=stage, stage_entered_at=now)
        )
        result = await session.execute(stmt)
        updated = result.rowcount > 0
        if updated:
            await session.flush()
            logger.info(
                "Updated contact %s stage to '%s' in DB", phone_number, stage,
            )
        else:
            logger.warning(
                "Contact %s not found for stage update to '%s'",
                phone_number, stage,
            )
        return updated

    async def get_journey_status(
        self,
        phone_number: str,
        tenant_id: UUID | None = None,
    ) -> dict[str, Any] | None:
        """
        Get the current funnel journey status for a contact.

        Returns dict with process variables, or None if no active journey.
        """
        if not self._camunda.enabled:
            return None

        try:
            instances = await self._camunda.list_process_instances(
                process_key="funnel_journey",
                business_key=phone_number,
                active=True,
            )
            if not instances:
                return None

            instance = instances[0]
            variables = await self._camunda.get_process_variables(instance.id)
            return {
                "process_instance_id": instance.id,
                "current_stage": variables.get("current_stage", "unknown"),
                "started_at": variables.get("journey_started_at"),
                "contact_id": variables.get("contact_id"),
                **{k: v for k, v in variables.items() if k.endswith("_at")},
            }
        except (CamundaConnectionError, CamundaError) as e:
            logger.debug("Could not get journey status: %s", e)
            return None

    async def start_batch_journeys(
        self,
        contacts: list[dict[str, Any]],
        tenant_id: UUID,
    ) -> int:
        """
        Start funnel journeys for multiple contacts (batch import).

        Args:
            contacts: List of dicts with 'id', 'phone_number', 'name' keys
            tenant_id: Tenant UUID

        Returns:
            Count of successfully started journeys
        """
        if not self._camunda.enabled:
            return 0

        started = 0
        for contact in contacts:
            result = await self.start_journey(
                contact_id=contact["id"],
                tenant_id=tenant_id,
                phone_number=contact["phone_number"],
                contact_name=contact.get("name"),
            )
            if result:
                started += 1

        logger.info("Started %d/%d batch funnel journeys", started, len(contacts))
        return started

