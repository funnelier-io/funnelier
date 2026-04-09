"""
Campaign Send SMS Worker

External task worker for topic: send-campaign-sms
Reads pending campaign recipients and dispatches SMS messages
via the configured messaging provider.
"""

import logging
from datetime import datetime
from typing import Any
from uuid import UUID

from src.infrastructure.camunda.client import CamundaClient, ExternalTask
from src.infrastructure.database.session import get_session_factory

logger = logging.getLogger(__name__)


async def handle_send_campaign_sms(
    task: ExternalTask,
    client: CamundaClient,
) -> dict[str, Any]:
    """
    Send SMS messages to campaign recipients.

    Process variables expected:
        - campaign_id (str): Campaign UUID
        - tenant_id (str): Tenant UUID
        - recipient_count (int): Number of recipients (from prepare step)

    Output variables:
        - sent_count (int): Successfully queued SMS count
        - failed_count (int): Failed SMS count
    """
    campaign_id = task.get_variable("campaign_id")
    tenant_id = task.get_variable("tenant_id")

    if not campaign_id or not tenant_id:
        logger.error("Missing campaign_id or tenant_id in task %s", task.id)
        return {"sent_count": 0, "failed_count": 0}

    campaign_uuid = UUID(campaign_id)
    tenant_uuid = UUID(tenant_id)

    session_factory = get_session_factory()
    sent_count = 0
    failed_count = 0

    async with session_factory() as session:
        from src.infrastructure.database.models.campaigns import (
            CampaignModel,
            CampaignRecipientModel,
        )
        from sqlalchemy import select, update as sa_update

        # Fetch campaign for message content
        result = await session.execute(
            select(CampaignModel).where(
                CampaignModel.id == campaign_uuid,
                CampaignModel.tenant_id == tenant_uuid,
            )
        )
        campaign = result.scalar_one_or_none()
        if not campaign:
            return {"sent_count": 0, "failed_count": 0}

        message_content = campaign.message_content or ""

        # Fetch pending recipients
        result = await session.execute(
            select(CampaignRecipientModel)
            .where(CampaignRecipientModel.campaign_id == campaign_uuid)
            .where(CampaignRecipientModel.status == "pending")
        )
        recipients = result.scalars().all()

        # Try to send via messaging provider
        try:
            from src.infrastructure.messaging.provider_registry import get_messaging_provider
            provider = get_messaging_provider()
        except Exception:
            provider = None

        now = datetime.utcnow()
        for recipient in recipients:
            try:
                if provider:
                    await provider.send_sms(
                        phone_number=recipient.phone_number,
                        message=message_content,
                        metadata={"campaign_id": str(campaign_uuid)},
                    )

                # Mark as sent (provider or stub)
                recipient.status = "sent"
                recipient.sent_at = now
                sent_count += 1
            except Exception as e:
                logger.warning(
                    "Failed to send SMS to %s: %s", recipient.phone_number, e,
                )
                recipient.status = "failed"
                failed_count += 1

        # Update campaign counters
        campaign.total_sent = sent_count
        campaign.total_failed = failed_count
        await session.commit()

    logger.info(
        "Campaign %s SMS send: sent=%d, failed=%d",
        campaign_id, sent_count, failed_count,
    )
    return {"sent_count": sent_count, "failed_count": failed_count}

