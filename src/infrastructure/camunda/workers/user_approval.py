"""
User Approval External Task Workers

Workers for the user_approval BPMN process:
- notify-pending-user: Send notification to admins about new registration
- activate-approved-user: Set is_approved=True in database
- notify-user-approved: Send notification to user (approved)
- notify-user-rejected: Send notification to user (rejected)
- send-approval-reminder: Reminder to admins after 48h timeout
"""

import logging
from datetime import datetime
from typing import Any
from uuid import UUID

from src.infrastructure.camunda.client import CamundaClient, ExternalTask
from src.infrastructure.database.session import get_session_factory

logger = logging.getLogger(__name__)


async def handle_notify_pending_user(
    task: ExternalTask,
    client: CamundaClient,
) -> dict[str, Any]:
    """
    Notify admins about a new user registration pending approval.

    Process variables expected:
        - user_id (str): UUID of the registered user
        - tenant_id (str): Tenant UUID
        - username (str): Username of the registered user
        - email (str): Email of the registered user
    """
    user_id = task.get_variable("user_id")
    tenant_id = task.get_variable("tenant_id")
    username = task.get_variable("username") or "unknown"
    email = task.get_variable("email") or ""

    if not user_id or not tenant_id:
        logger.error("Missing user_id or tenant_id in task %s", task.id)
        return {"notification_sent": False}

    session_factory = get_session_factory()
    notification_sent = False

    async with session_factory() as session:
        try:
            from src.infrastructure.database.models.notifications import NotificationModel
            from src.infrastructure.database.models.tenants import TenantUserModel
            from sqlalchemy import select
            from uuid import uuid4

            tenant_uuid = UUID(tenant_id)

            # Find admin users in the same tenant
            result = await session.execute(
                select(TenantUserModel)
                .where(TenantUserModel.tenant_id == tenant_uuid)
                .where(TenantUserModel.role.in_(["super_admin", "tenant_admin"]))
                .where(TenantUserModel.is_active.is_(True))
            )
            admins = result.scalars().all()

            # Create notification for each admin
            for admin in admins:
                notification = NotificationModel(
                    id=uuid4(),
                    tenant_id=tenant_uuid,
                    user_id=admin.id,
                    title="کاربر جدید منتظر تأیید",
                    message=f"کاربر {username} ({email}) ثبت‌نام کرده و منتظر تأیید است.",
                    notification_type="user_approval",
                    priority="high",
                    data={"pending_user_id": user_id, "username": username},
                )
                session.add(notification)

            await session.commit()
            notification_sent = len(admins) > 0
            logger.info(
                "Notified %d admin(s) about pending user %s", len(admins), username,
            )
        except Exception as e:
            logger.warning("Failed to create approval notifications: %s", e)
            await session.rollback()

    return {"notification_sent": notification_sent, "admin_count": len(admins) if notification_sent else 0}


async def handle_activate_approved_user(
    task: ExternalTask,
    client: CamundaClient,
) -> dict[str, Any]:
    """
    Activate a user that has been approved by an admin.

    Process variables expected:
        - user_id (str): UUID of the user to activate
        - tenant_id (str): Tenant UUID
        - approved (bool): Must be True
    """
    user_id = task.get_variable("user_id")
    tenant_id = task.get_variable("tenant_id")

    if not user_id or not tenant_id:
        logger.error("Missing user_id or tenant_id in task %s", task.id)
        return {"activated": False}

    session_factory = get_session_factory()

    async with session_factory() as session:
        from src.infrastructure.database.models.tenants import TenantUserModel
        from sqlalchemy import select, update as sa_update

        user_uuid = UUID(user_id)
        tenant_uuid = UUID(tenant_id)

        result = await session.execute(
            sa_update(TenantUserModel)
            .where(TenantUserModel.id == user_uuid)
            .where(TenantUserModel.tenant_id == tenant_uuid)
            .values(is_approved=True)
        )
        await session.commit()

    logger.info("Activated approved user %s", user_id)
    return {"activated": True}


async def handle_notify_user_approved(
    task: ExternalTask,
    client: CamundaClient,
) -> dict[str, Any]:
    """
    Notify the user that their registration has been approved.

    Process variables:
        - user_id (str): UUID of the approved user
        - tenant_id (str): Tenant UUID
    """
    user_id = task.get_variable("user_id")
    tenant_id = task.get_variable("tenant_id")

    if not user_id or not tenant_id:
        return {"notified": False}

    session_factory = get_session_factory()

    async with session_factory() as session:
        try:
            from src.infrastructure.database.models.notifications import NotificationModel
            from uuid import uuid4

            notification = NotificationModel(
                id=uuid4(),
                tenant_id=UUID(tenant_id),
                user_id=UUID(user_id),
                title="حساب شما تأیید شد",
                message="حساب کاربری شما توسط مدیر تأیید شد. اکنون می‌توانید وارد شوید.",
                notification_type="account_approved",
                priority="high",
                data={},
            )
            session.add(notification)
            await session.commit()
        except Exception as e:
            logger.warning("Failed to notify approved user: %s", e)
            await session.rollback()

    logger.info("Notified user %s of approval", user_id)
    return {"notified": True}


async def handle_notify_user_rejected(
    task: ExternalTask,
    client: CamundaClient,
) -> dict[str, Any]:
    """
    Notify the user that their registration has been rejected.

    Process variables:
        - user_id (str): UUID of the rejected user
        - tenant_id (str): Tenant UUID
        - rejection_reason (str): Optional reason
    """
    user_id = task.get_variable("user_id")
    tenant_id = task.get_variable("tenant_id")
    reason = task.get_variable("rejection_reason") or "دلیل خاصی اعلام نشده"

    if not user_id or not tenant_id:
        return {"notified": False}

    session_factory = get_session_factory()

    async with session_factory() as session:
        try:
            from src.infrastructure.database.models.notifications import NotificationModel
            from src.infrastructure.database.models.tenants import TenantUserModel
            from sqlalchemy import update as sa_update
            from uuid import uuid4

            # Deactivate the user
            await session.execute(
                sa_update(TenantUserModel)
                .where(TenantUserModel.id == UUID(user_id))
                .values(is_active=False)
            )

            # Notify user
            notification = NotificationModel(
                id=uuid4(),
                tenant_id=UUID(tenant_id),
                user_id=UUID(user_id),
                title="حساب شما رد شد",
                message=f"متأسفانه درخواست ثبت‌نام شما رد شد. دلیل: {reason}",
                notification_type="account_rejected",
                priority="high",
                data={"reason": reason},
            )
            session.add(notification)
            await session.commit()
        except Exception as e:
            logger.warning("Failed to process rejected user: %s", e)
            await session.rollback()

    logger.info("Processed rejection for user %s", user_id)
    return {"notified": True}


async def handle_send_approval_reminder(
    task: ExternalTask,
    client: CamundaClient,
) -> dict[str, Any]:
    """
    Send a reminder to admins about a pending user after 48h.

    Process variables:
        - user_id (str): UUID of the pending user
        - tenant_id (str): Tenant UUID
        - username (str): Username
    """
    user_id = task.get_variable("user_id")
    tenant_id = task.get_variable("tenant_id")
    username = task.get_variable("username") or "unknown"

    if not user_id or not tenant_id:
        return {"reminder_sent": False}

    session_factory = get_session_factory()

    async with session_factory() as session:
        try:
            from src.infrastructure.database.models.notifications import NotificationModel
            from src.infrastructure.database.models.tenants import TenantUserModel
            from sqlalchemy import select
            from uuid import uuid4

            tenant_uuid = UUID(tenant_id)

            result = await session.execute(
                select(TenantUserModel)
                .where(TenantUserModel.tenant_id == tenant_uuid)
                .where(TenantUserModel.role.in_(["super_admin", "tenant_admin"]))
                .where(TenantUserModel.is_active.is_(True))
            )
            admins = result.scalars().all()

            for admin in admins:
                notification = NotificationModel(
                    id=uuid4(),
                    tenant_id=tenant_uuid,
                    user_id=admin.id,
                    title="یادآوری: کاربر منتظر تأیید",
                    message=f"کاربر {username} بیش از ۴۸ ساعت منتظر تأیید است.",
                    notification_type="approval_reminder",
                    priority="urgent",
                    data={"pending_user_id": user_id, "username": username},
                )
                session.add(notification)

            await session.commit()
            logger.info("Sent reminder to %d admin(s) for user %s", len(admins), username)
        except Exception as e:
            logger.warning("Failed to send approval reminder: %s", e)
            await session.rollback()

    return {"reminder_sent": True}

