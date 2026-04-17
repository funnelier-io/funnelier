"""
Stale Stage Notification Worker

External task worker for topic: notify-stale-stage
Fires when a contact has been stuck at a funnel stage longer than
the configured timeout (boundary timer in BPMN).
Creates an alert / notification for the tenant admin and optionally
for the assigned salesperson.
"""

import logging
from datetime import datetime
from typing import Any
from uuid import UUID

from src.infrastructure.camunda.client import CamundaClient, ExternalTask
from src.infrastructure.database.session import get_session_factory

logger = logging.getLogger(__name__)


async def handle_notify_stale_stage(
    task: ExternalTask,
    client: CamundaClient,
) -> dict[str, Any]:
    """
    Handle a stale-stage notification from a boundary timer event.

    Process variables expected:
        - contact_id (str): Contact UUID
        - tenant_id (str): Tenant UUID
        - phone_number (str): Contact phone number
        - current_stage (str): The stage the contact is stuck at
        - contact_name (str): Optional contact name

    Output variables:
        - notification_sent (bool): Whether notification was created
        - notified_at (str): ISO timestamp
    """
    contact_id = task.get_variable("contact_id")
    tenant_id = task.get_variable("tenant_id")
    phone_number = task.get_variable("phone_number")
    current_stage = task.get_variable("current_stage") or "unknown"
    contact_name = task.get_variable("contact_name") or phone_number

    if not contact_id or not tenant_id:
        logger.error(
            "Missing required variables in stale-stage task %s: contact_id=%s, tenant_id=%s",
            task.id, contact_id, tenant_id,
        )
        return {"notification_sent": False}

    now = datetime.utcnow()

    try:
        session_factory = get_session_factory()
        async with session_factory() as session:
            # Create an in-app notification for the tenant admin
            from src.infrastructure.database.models.notifications import NotificationModel
            from sqlalchemy import select
            from src.infrastructure.database.models.tenants import TenantUserModel

            # Find the tenant admin user to notify
            admin_stmt = (
                select(TenantUserModel.id)
                .where(TenantUserModel.tenant_id == UUID(tenant_id))
                .where(TenantUserModel.role.in_(["super_admin", "tenant_admin"]))
                .where(TenantUserModel.is_active.is_(True))
                .limit(1)
            )
            admin_result = await session.execute(admin_stmt)
            admin_row = admin_result.scalar_one_or_none()

            # Fall back to system UUID if no admin found
            user_id = admin_row if admin_row else UUID(tenant_id)

            notification = NotificationModel(
                tenant_id=UUID(tenant_id),
                user_id=user_id,
                type="alert",
                severity="warning",
                title=f"سرنخ راکد در مرحله {current_stage}",
                body=(
                    f"مخاطب {contact_name} ({phone_number}) "
                    f"بیش از حد معمول در مرحله «{current_stage}» باقی مانده است. "
                    f"لطفاً پیگیری کنید."
                ),
                source_type="stale_stage",
                metadata_json={
                    "contact_id": contact_id,
                    "phone_number": phone_number,
                    "current_stage": current_stage,
                    "source": "camunda_timer",
                    "process_instance_id": task.process_instance_id,
                },
            )
            session.add(notification)
            await session.commit()

        logger.info(
            "Stale stage notification created: contact %s (%s) stuck at '%s'",
            contact_id, phone_number, current_stage,
        )

        return {
            "notification_sent": True,
            "notified_at": now.isoformat(),
        }

    except Exception as e:
        logger.error("Failed to create stale-stage notification: %s", e)
        return {"notification_sent": False}

