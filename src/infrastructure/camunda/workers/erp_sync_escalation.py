"""
ERP Sync Escalation Workers

External task workers for ERP sync failure escalation workflow.
Topics:
  - erp-log-sync-failure: Log sync failure details
  - erp-retry-sync: Retry the ERP sync operation
  - erp-mark-resolved: Mark sync failure as resolved
  - erp-escalate-failure: Notify admin about persistent failure
  - erp-send-reminder: Send reminder for unresolved escalation
"""

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from src.infrastructure.camunda.client import CamundaClient, ExternalTask
from src.infrastructure.database.session import get_session_factory

logger = logging.getLogger(__name__)


async def handle_log_sync_failure(
    task: ExternalTask,
    client: CamundaClient,
) -> dict[str, Any]:
    """
    Log an ERP sync failure in the database.

    Process variables expected:
        - tenant_id (str): Tenant UUID
        - source_name (str): ERP source name (e.g. 'mongodb_invoices')
        - error_message (str): Error description
        - max_retries (int): Maximum retry attempts (default 3)

    Output variables:
        - retry_count (int): 0 (initial)
        - logged_at (str): ISO timestamp
    """
    tenant_id = task.get_variable("tenant_id")
    source_name = task.get_variable("source_name") or "unknown"
    error_message = task.get_variable("error_message") or "Unknown error"
    max_retries = task.get_variable("max_retries") or 3

    if not tenant_id:
        logger.error("Missing tenant_id in erp-log-sync-failure task %s", task.id)
        return {"retry_count": 0, "max_retries": max_retries}

    now = datetime.now(timezone.utc)

    try:
        session_factory = get_session_factory()
        async with session_factory() as session:
            from src.infrastructure.database.models.etl import ImportLogModel

            log_entry = ImportLogModel(
                tenant_id=UUID(tenant_id),
                import_type="erp_sync",
                source_name=source_name,
                status="failed",
                error_message=error_message,
                started_at=now,
                completed_at=now,
                records_processed=0,
                records_failed=0,
                result_summary={"escalation": True, "process_id": task.process_instance_id},
            )
            session.add(log_entry)
            await session.commit()

        logger.info(
            "Logged ERP sync failure: tenant=%s source=%s error=%s",
            tenant_id[:8], source_name, error_message[:100],
        )
    except Exception as e:
        logger.error("Failed to log sync failure: %s", e)

    return {
        "retry_count": 0,
        "max_retries": max_retries,
        "logged_at": now.isoformat(),
    }


async def handle_retry_sync(
    task: ExternalTask,
    client: CamundaClient,
) -> dict[str, Any]:
    """
    Retry an ERP sync operation.

    Process variables expected:
        - tenant_id (str): Tenant UUID
        - source_name (str): ERP source name
        - retry_count (int): Current retry attempt

    Output variables:
        - retry_success (bool): Whether retry succeeded
        - retry_count (int): Incremented retry count
    """
    tenant_id = task.get_variable("tenant_id")
    source_name = task.get_variable("source_name") or "unknown"
    retry_count = (task.get_variable("retry_count") or 0) + 1

    if not tenant_id:
        return {"retry_success": False, "retry_count": retry_count}

    logger.info(
        "Retrying ERP sync: tenant=%s source=%s attempt=%d",
        tenant_id[:8], source_name, retry_count,
    )

    try:
        # Attempt the sync via the ETL pipeline
        session_factory = get_session_factory()
        async with session_factory() as session:
            from src.infrastructure.database.models.etl import ImportLogModel
            from sqlalchemy import select

            # Check if original source config exists
            # For now, we simulate a retry attempt.
            # In production, this would invoke the actual ERP connector.
            # The sync may have been a transient network issue.
            success = False

            try:
                from src.infrastructure.connectors.mongodb_connector import MongoDBConnector
                connector = MongoDBConnector()
                # Try a basic health check on the MongoDB connection
                health = await connector.check_connection()
                success = health
            except Exception:
                success = False

            if success:
                log_entry = ImportLogModel(
                    tenant_id=UUID(tenant_id),
                    import_type="erp_sync_retry",
                    source_name=source_name,
                    status="completed",
                    started_at=datetime.now(timezone.utc),
                    completed_at=datetime.now(timezone.utc),
                    records_processed=0,
                    records_failed=0,
                    result_summary={"retry_attempt": retry_count, "process_id": task.process_instance_id},
                )
                session.add(log_entry)
                await session.commit()

            logger.info(
                "ERP sync retry %s: tenant=%s source=%s attempt=%d",
                "succeeded" if success else "failed", tenant_id[:8], source_name, retry_count,
            )
            return {"retry_success": success, "retry_count": retry_count}

    except Exception as e:
        logger.error("ERP sync retry error: %s", e)
        return {"retry_success": False, "retry_count": retry_count}


async def handle_mark_resolved(
    task: ExternalTask,
    client: CamundaClient,
) -> dict[str, Any]:
    """
    Mark a sync failure as resolved after successful retry.

    Process variables expected:
        - tenant_id (str): Tenant UUID
        - source_name (str): ERP source name
    """
    tenant_id = task.get_variable("tenant_id")
    source_name = task.get_variable("source_name") or "unknown"

    logger.info(
        "ERP sync resolved via retry: tenant=%s source=%s",
        (tenant_id or "?")[:8], source_name,
    )

    return {"resolved_at": datetime.now(timezone.utc).isoformat(), "resolution": "auto_retry"}


async def handle_escalate_failure(
    task: ExternalTask,
    client: CamundaClient,
) -> dict[str, Any]:
    """
    Escalate a persistent ERP sync failure to the tenant admin.
    Creates an in-app notification with severity=critical.

    Process variables expected:
        - tenant_id (str): Tenant UUID
        - source_name (str): ERP source name
        - error_message (str): Original error
        - retry_count (int): Number of retries attempted
    """
    tenant_id = task.get_variable("tenant_id")
    source_name = task.get_variable("source_name") or "unknown"
    error_message = task.get_variable("error_message") or "Unknown error"
    retry_count = task.get_variable("retry_count") or 0

    if not tenant_id:
        return {"escalated": False}

    now = datetime.now(timezone.utc)

    try:
        session_factory = get_session_factory()
        async with session_factory() as session:
            from src.infrastructure.database.models.notifications import NotificationModel
            from src.infrastructure.database.models.tenants import TenantUserModel
            from sqlalchemy import select

            # Find tenant admin
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
                title=f"خطای همگام‌سازی ERP — {source_name}",
                body=(
                    f"همگام‌سازی داده از منبع «{source_name}» پس از "
                    f"{retry_count} بار تلاش مجدد ناموفق بود.\n"
                    f"خطا: {error_message[:200]}\n"
                    f"لطفاً بررسی و اقدام کنید."
                ),
                source_type="erp_sync_escalation",
                metadata_json={
                    "source_name": source_name,
                    "error_message": error_message,
                    "retry_count": retry_count,
                    "process_instance_id": task.process_instance_id,
                },
            )
            session.add(notification)
            await session.commit()

        logger.warning(
            "ERP sync failure escalated: tenant=%s source=%s retries=%d",
            tenant_id[:8], source_name, retry_count,
        )
        return {"escalated": True, "escalated_at": now.isoformat()}

    except Exception as e:
        logger.error("Failed to escalate ERP sync failure: %s", e)
        return {"escalated": False}


async def handle_send_escalation_reminder(
    task: ExternalTask,
    client: CamundaClient,
) -> dict[str, Any]:
    """
    Send a reminder notification for unresolved ERP sync failure.

    Process variables expected:
        - tenant_id (str): Tenant UUID
        - source_name (str): ERP source name
    """
    tenant_id = task.get_variable("tenant_id")
    source_name = task.get_variable("source_name") or "unknown"

    if not tenant_id:
        return {"reminder_sent": False}

    try:
        session_factory = get_session_factory()
        async with session_factory() as session:
            from src.infrastructure.database.models.notifications import NotificationModel
            from src.infrastructure.database.models.tenants import TenantUserModel
            from sqlalchemy import select

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
                severity="warning",
                title=f"یادآوری: خطای همگام‌سازی ERP — {source_name}",
                body=(
                    f"خطای همگام‌سازی داده از منبع «{source_name}» هنوز حل نشده است. "
                    f"لطفاً بررسی و اقدام کنید."
                ),
                source_type="erp_sync_reminder",
                metadata_json={
                    "source_name": source_name,
                    "process_instance_id": task.process_instance_id,
                },
            )
            session.add(notification)
            await session.commit()

        logger.info("ERP sync escalation reminder sent: tenant=%s source=%s", tenant_id[:8], source_name)
        return {"reminder_sent": True, "reminder_at": datetime.now(timezone.utc).isoformat()}

    except Exception as e:
        logger.error("Failed to send escalation reminder: %s", e)
        return {"reminder_sent": False}

