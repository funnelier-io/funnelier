"""
Funnel Stage Update Worker

External task worker for topic: update-funnel-stage
Updates a contact's current_stage and stage_entered_at in the database
when a Camunda funnel_journey process advances to a new stage.
"""

import logging
from datetime import datetime
from typing import Any
from uuid import UUID

from src.infrastructure.camunda.client import CamundaClient, ExternalTask
from src.infrastructure.database.session import get_session_factory

logger = logging.getLogger(__name__)


async def handle_update_funnel_stage(
    task: ExternalTask,
    client: CamundaClient,
) -> dict[str, Any]:
    """
    Update a contact's funnel stage in the database.

    Process variables expected:
        - contact_id (str): Contact UUID
        - tenant_id (str): Tenant UUID
        - current_stage (str): New funnel stage name
        - phone_number (str): Contact phone number (for logging)

    Output variables:
        - stage_updated (bool): Whether the update succeeded
        - updated_at (str): ISO timestamp of the update
    """
    contact_id = task.get_variable("contact_id")
    tenant_id = task.get_variable("tenant_id")
    current_stage = task.get_variable("current_stage")
    phone_number = task.get_variable("phone_number")

    if not contact_id or not tenant_id or not current_stage:
        logger.error(
            "Missing required variables in task %s: contact_id=%s, tenant_id=%s, stage=%s",
            task.id, contact_id, tenant_id, current_stage,
        )
        return {"stage_updated": False}

    contact_uuid = UUID(contact_id)
    tenant_uuid = UUID(tenant_id)
    now = datetime.utcnow()

    session_factory = get_session_factory()
    async with session_factory() as session:
        from src.infrastructure.database.models.leads import ContactModel
        from sqlalchemy import update as sa_update

        stmt = (
            sa_update(ContactModel)
            .where(ContactModel.id == contact_uuid)
            .where(ContactModel.tenant_id == tenant_uuid)
            .values(
                current_stage=current_stage,
                stage_entered_at=now,
            )
        )
        result = await session.execute(stmt)
        await session.commit()

        updated = result.rowcount > 0

    if updated:
        logger.info(
            "Updated contact %s (phone=%s) to stage '%s'",
            contact_id, phone_number, current_stage,
        )
    else:
        logger.warning(
            "Contact %s not found for stage update to '%s'",
            contact_id, current_stage,
        )

    return {
        "stage_updated": updated,
        "updated_at": now.isoformat(),
    }

