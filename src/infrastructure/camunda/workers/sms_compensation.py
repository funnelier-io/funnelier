"""
SMS Send Failure Compensation Worker

External task worker for topic: compensate-sms-failure
Handles compensation when an SMS send batch fails mid-way.
Marks affected recipients as "failed" so they can be retried or
excluded from delivery tracking.
"""

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from src.infrastructure.camunda.client import CamundaClient, ExternalTask
from src.infrastructure.database.session import get_session_factory

logger = logging.getLogger(__name__)


async def handle_compensate_sms_failure(
    task: ExternalTask,
    client: CamundaClient,
) -> dict[str, Any]:
    """
    Compensate for a failed SMS send batch.

    When the campaign send step fails (throws a BPMN error), this
    compensation handler:
    1. Marks unsent recipients as status='send_failed'
    2. Updates campaign status to 'partially_sent'
    3. Creates a notification for the tenant admin
    4. Records the failure in import_logs

    Process variables expected:
        - campaign_id (str): Campaign UUID
        - tenant_id (str): Tenant UUID
        - error_message (str): What went wrong
        - sent_count (int): Number successfully sent before failure
        - total_recipients (int): Total intended recipients

    Output variables:
        - compensated (bool): Whether compensation succeeded
        - compensated_at (str): ISO timestamp
    """
    campaign_id = task.get_variable("campaign_id")
    tenant_id = task.get_variable("tenant_id")
    error_message = task.get_variable("error_message") or "SMS send failed"
    sent_count = task.get_variable("sent_count") or 0
    total_recipients = task.get_variable("total_recipients") or 0

    if not campaign_id or not tenant_id:
        logger.error(
            "Missing campaign_id or tenant_id in sms-compensation task %s", task.id
        )
        return {"compensated": False}

    now = datetime.now(timezone.utc)

    try:
        session_factory = get_session_factory()
        async with session_factory() as session:
            from sqlalchemy import update, select
            from src.infrastructure.database.models.communications import SMSLogModel

            # Mark pending/queued SMS logs for this campaign as 'failed'
            failed_update = (
                update(SMSLogModel)
                .where(SMSLogModel.tenant_id == UUID(tenant_id))
                .where(SMSLogModel.campaign_id == UUID(campaign_id))
                .where(SMSLogModel.status.in_(["pending", "queued"]))
                .values(status="failed", error_message=error_message)
            )
            result = await session.execute(failed_update)
            failed_count = result.rowcount

            # Update campaign status to partially_sent
            from src.infrastructure.database.models.communications import CampaignModel
            campaign_update = (
                update(CampaignModel)
                .where(CampaignModel.id == UUID(campaign_id))
                .values(
                    status="partially_sent",
                    error_message=f"Failed after {sent_count}/{total_recipients} sent: {error_message}",
                )
            )
            await session.execute(campaign_update)

            # Create admin notification
            from src.infrastructure.database.models.notifications import NotificationModel
            from src.infrastructure.database.models.tenants import TenantUserModel

            admin_stmt = (
                select(TenantUserModel.id)
                .where(TenantUserModel.tenant_id == UUID(tenant_id))
                .where(TenantUserModel.role.in_(["super_admin", "tenant_admin"]))
                .where(TenantUserModel.is_active.is_(True))
                .limit(1)
            )
            admin_result = await session.execute(admin_stmt)
            admin_id = admin_result.scalar_one_or_none()
            user_id = admin_id if admin_id else UUID(tenant_id)

            notification = NotificationModel(
                tenant_id=UUID(tenant_id),
                user_id=user_id,
                type="alert",
                severity="critical",
                title="خطا در ارسال پیامک کمپین",
                body=(
                    f"ارسال پیامک کمپین پس از {sent_count} از {total_recipients} پیام "
                    f"متوقف شد.\nخطا: {error_message[:200]}\n"
                    f"{failed_count} پیام به وضعیت «ناموفق» تغییر یافت."
                ),
                source_type="sms_compensation",
                metadata_json={
                    "campaign_id": campaign_id,
                    "sent_count": sent_count,
                    "failed_count": failed_count,
                    "total_recipients": total_recipients,
                    "error_message": error_message,
                    "process_instance_id": task.process_instance_id,
                },
            )
            session.add(notification)

            await session.commit()

        logger.warning(
            "SMS compensation completed: campaign=%s sent=%d failed=%d total=%d",
            campaign_id[:8] if campaign_id else "?",
            sent_count, failed_count, total_recipients,
        )

        return {
            "compensated": True,
            "compensated_at": now.isoformat(),
            "failed_marked": failed_count,
        }

    except Exception as e:
        logger.error("SMS compensation failed: %s", e)
        return {"compensated": False}

