"""
Campaign Measure Results Worker

External task worker for topic: measure-campaign-results
Aggregates final campaign metrics and marks the campaign as completed.
"""

import logging
from datetime import datetime
from typing import Any
from uuid import UUID

from src.infrastructure.camunda.client import CamundaClient, ExternalTask
from src.infrastructure.database.session import get_session_factory

logger = logging.getLogger(__name__)


async def handle_measure_results(
    task: ExternalTask,
    client: CamundaClient,
) -> dict[str, Any]:
    """
    Calculate final campaign metrics and mark as completed.

    Process variables expected:
        - campaign_id (str): Campaign UUID
        - tenant_id (str): Tenant UUID
        - sent_count (int)
        - delivered_count (int)

    Output variables:
        - delivery_rate (float)
        - response_rate (float)
        - conversion_rate (float)
        - campaign_status (str): "completed"
    """
    campaign_id = task.get_variable("campaign_id")
    tenant_id = task.get_variable("tenant_id")

    if not campaign_id or not tenant_id:
        logger.error("Missing campaign_id or tenant_id in task %s", task.id)
        return {"campaign_status": "error"}

    campaign_uuid = UUID(campaign_id)
    tenant_uuid = UUID(tenant_id)

    session_factory = get_session_factory()
    metrics: dict[str, Any] = {}

    async with session_factory() as session:
        from src.infrastructure.database.models.campaigns import (
            CampaignModel,
            CampaignRecipientModel,
        )
        from sqlalchemy import select, func

        # Aggregate recipient stats
        result = await session.execute(
            select(
                func.count().label("total"),
                func.count().filter(CampaignRecipientModel.status == "delivered").label("delivered"),
                func.count().filter(CampaignRecipientModel.status == "responded").label("responded"),
                func.count().filter(CampaignRecipientModel.status == "converted").label("converted"),
                func.count().filter(CampaignRecipientModel.status == "failed").label("failed"),
            )
            .where(CampaignRecipientModel.campaign_id == campaign_uuid)
        )
        row = result.one()

        total = row.total or 0
        delivered = row.delivered or 0
        responded = row.responded or 0
        converted = row.converted or 0
        failed = row.failed or 0

        delivery_rate = delivered / total if total > 0 else 0.0
        response_rate = responded / delivered if delivered > 0 else 0.0
        conversion_rate = converted / delivered if delivered > 0 else 0.0

        # Update campaign to completed
        result = await session.execute(
            select(CampaignModel).where(
                CampaignModel.id == campaign_uuid,
                CampaignModel.tenant_id == tenant_uuid,
            )
        )
        campaign = result.scalar_one_or_none()
        if campaign:
            campaign.status = "completed"
            campaign.completed_at = datetime.utcnow()
            campaign.total_delivered = delivered
            campaign.total_calls_received = responded
            campaign.total_conversions = converted
            campaign.total_failed = failed
        await session.commit()

        metrics = {
            "campaign_status": "completed",
            "total_recipients": total,
            "delivered_count": delivered,
            "responded_count": responded,
            "converted_count": converted,
            "delivery_rate": round(delivery_rate, 4),
            "response_rate": round(response_rate, 4),
            "conversion_rate": round(conversion_rate, 4),
        }

    logger.info(
        "Campaign %s completed: delivered=%d, response_rate=%.2f%%, conversion_rate=%.2f%%",
        campaign_id, delivered, response_rate * 100, conversion_rate * 100,
    )
    return metrics

