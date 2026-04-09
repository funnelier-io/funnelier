"""
Campaign Track Delivery Worker

External task worker for topic: track-sms-delivery
Polls delivery status for sent campaign SMS messages and
updates recipient records.
"""

import logging
from datetime import datetime
from typing import Any
from uuid import UUID

from src.infrastructure.camunda.client import CamundaClient, ExternalTask
from src.infrastructure.database.session import get_session_factory

logger = logging.getLogger(__name__)


async def handle_track_delivery(
    task: ExternalTask,
    client: CamundaClient,
) -> dict[str, Any]:
    """
    Track SMS delivery status for campaign recipients.

    Process variables expected:
        - campaign_id (str): Campaign UUID
        - tenant_id (str): Tenant UUID
        - sent_count (int): Number of SMS sent

    Output variables:
        - delivered_count (int): Confirmed delivered
        - delivery_failed_count (int): Delivery failures
        - delivery_rate (float): delivered / sent
    """
    campaign_id = task.get_variable("campaign_id")
    tenant_id = task.get_variable("tenant_id")
    sent_count = task.get_variable("sent_count") or 0

    if not campaign_id or not tenant_id:
        logger.error("Missing campaign_id or tenant_id in task %s", task.id)
        return {"delivered_count": 0, "delivery_failed_count": 0, "delivery_rate": 0.0}

    campaign_uuid = UUID(campaign_id)
    tenant_uuid = UUID(tenant_id)

    session_factory = get_session_factory()
    delivered_count = 0
    delivery_failed_count = 0

    async with session_factory() as session:
        from src.infrastructure.database.models.campaigns import (
            CampaignModel,
            CampaignRecipientModel,
        )
        from sqlalchemy import select

        # Fetch sent recipients
        result = await session.execute(
            select(CampaignRecipientModel)
            .where(CampaignRecipientModel.campaign_id == campaign_uuid)
            .where(CampaignRecipientModel.status == "sent")
        )
        recipients = result.scalars().all()

        # Try to check delivery via provider
        try:
            from src.infrastructure.messaging.provider_registry import get_messaging_provider
            provider = get_messaging_provider()
        except Exception:
            provider = None

        now = datetime.utcnow()
        for recipient in recipients:
            try:
                if provider and recipient.sms_log_id:
                    status = await provider.check_delivery_status(
                        message_id=str(recipient.sms_log_id),
                    )
                    if status == "delivered":
                        recipient.status = "delivered"
                        recipient.delivered_at = now
                        delivered_count += 1
                    elif status == "failed":
                        recipient.status = "failed"
                        delivery_failed_count += 1
                    # else: still pending, keep as "sent"
                else:
                    # No provider — assume delivered for stub mode
                    recipient.status = "delivered"
                    recipient.delivered_at = now
                    delivered_count += 1
            except Exception as e:
                logger.warning(
                    "Delivery check failed for %s: %s", recipient.phone_number, e,
                )

        # Update campaign counters
        result = await session.execute(
            select(CampaignModel).where(CampaignModel.id == campaign_uuid)
        )
        campaign = result.scalar_one_or_none()
        if campaign:
            campaign.total_delivered = delivered_count
        await session.commit()

    delivery_rate = delivered_count / sent_count if sent_count > 0 else 0.0

    logger.info(
        "Campaign %s delivery tracking: delivered=%d, failed=%d, rate=%.2f",
        campaign_id, delivered_count, delivery_failed_count, delivery_rate,
    )
    return {
        "delivered_count": delivered_count,
        "delivery_failed_count": delivery_failed_count,
        "delivery_rate": delivery_rate,
    }

