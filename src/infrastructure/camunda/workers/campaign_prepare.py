"""
Campaign Prepare Recipients Worker

External task worker for topic: prepare-campaign-recipients
Queries contacts matching campaign targeting filters and bulk-inserts
them into campaign_recipients.  Sets `recipient_count` output variable
for the BPMN gateway decision.
"""

import logging
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from src.infrastructure.camunda.client import CamundaClient, ExternalTask
from src.infrastructure.database.session import get_session_factory

logger = logging.getLogger(__name__)


async def handle_prepare_recipients(
    task: ExternalTask,
    client: CamundaClient,
) -> dict[str, Any]:
    """
    Prepare campaign recipients from targeting filters.

    Process variables expected:
        - campaign_id (str): Campaign UUID
        - tenant_id (str): Tenant UUID

    Output variables:
        - recipient_count (int): Number of recipients prepared
    """
    campaign_id = task.get_variable("campaign_id")
    tenant_id = task.get_variable("tenant_id")

    if not campaign_id or not tenant_id:
        logger.error("Missing campaign_id or tenant_id in task %s", task.id)
        return {"recipient_count": 0}

    campaign_uuid = UUID(campaign_id)
    tenant_uuid = UUID(tenant_id)

    session_factory = get_session_factory()
    recipient_count = 0

    async with session_factory() as session:
        from src.infrastructure.database.models.campaigns import (
            CampaignModel,
            CampaignRecipientModel,
        )
        from src.infrastructure.database.models.leads import ContactModel
        from sqlalchemy import select, func

        # Fetch campaign
        result = await session.execute(
            select(CampaignModel).where(
                CampaignModel.id == campaign_uuid,
                CampaignModel.tenant_id == tenant_uuid,
            )
        )
        campaign = result.scalar_one_or_none()
        if not campaign:
            logger.warning("Campaign %s not found for tenant %s", campaign_id, tenant_id)
            return {"recipient_count": 0}

        # Build contact query from targeting
        targeting = campaign.targeting or {}
        stmt = (
            select(ContactModel)
            .where(ContactModel.tenant_id == tenant_uuid)
            .where(ContactModel.is_active.is_(True))
        )

        # Apply segment filter
        segments = targeting.get("segments", [])
        if segments:
            stmt = stmt.where(ContactModel.rfm_segment.in_(segments))

        # Apply category filter
        categories = targeting.get("categories", [])
        if categories:
            stmt = stmt.where(ContactModel.category_id.in_(categories))

        # Apply stage filter
        stages = targeting.get("stages", [])
        if stages:
            stmt = stmt.where(ContactModel.funnel_stage.in_(stages))

        # Max contacts limit
        max_contacts = targeting.get("max_contacts")
        if max_contacts:
            stmt = stmt.limit(max_contacts)

        result = await session.execute(stmt)
        contacts = result.scalars().all()

        # Bulk-insert recipients
        recipients = []
        for contact in contacts:
            phone = contact.phone or contact.mobile
            if not phone:
                continue
            recipients.append(
                CampaignRecipientModel(
                    id=uuid4(),
                    tenant_id=tenant_uuid,
                    campaign_id=campaign_uuid,
                    contact_id=contact.id,
                    phone_number=phone,
                    name=contact.full_name,
                    segment=contact.rfm_segment,
                    status="pending",
                    metadata_={},
                )
            )

        if recipients:
            session.add_all(recipients)
            recipient_count = len(recipients)

        # Update campaign counter
        campaign.total_recipients = recipient_count
        campaign.status = "running"
        campaign.started_at = campaign.started_at or datetime.utcnow()
        await session.commit()

    logger.info(
        "Prepared %d recipients for campaign %s", recipient_count, campaign_id,
    )
    return {"recipient_count": recipient_count}

