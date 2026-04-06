"""
Kavenegar Delivery Webhook

Receives delivery status callbacks from Kavenegar SMS gateway.
No JWT auth required — validated via shared secret query parameter.
"""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request

logger = logging.getLogger(__name__)

webhook_router = APIRouter(tags=["webhooks"])


@webhook_router.post("/webhooks/kavenegar/delivery")
async def kavenegar_delivery_webhook(
    request: Request,
    secret: str = Query(default="", alias="secret"),
):
    """
    Receive Kavenegar delivery status webhook.

    Kavenegar POSTs form-encoded or JSON body with fields:
        messageid, status, statustext, receptor, sender, message, date

    Secured via a shared secret query parameter (?secret=...).
    """
    from src.core.config import get_settings

    settings = get_settings()
    expected_secret = settings.kavenegar.webhook_secret

    # Validate shared secret
    if expected_secret and secret != expected_secret:
        raise HTTPException(status_code=403, detail="Invalid webhook secret")

    # Parse body (Kavenegar sends form-encoded or JSON)
    content_type = request.headers.get("content-type", "")
    if "json" in content_type:
        data = await request.json()
    else:
        form = await request.form()
        data = dict(form)

    message_id = str(data.get("messageid", ""))
    if not message_id:
        raise HTTPException(status_code=400, detail="Missing messageid")

    logger.info(
        "Kavenegar webhook: messageid=%s status=%s statustext=%s",
        message_id,
        data.get("status"),
        data.get("statustext"),
    )

    # Process the delivery status update
    try:
        await _process_delivery_update(data)
    except Exception as exc:
        logger.exception("Error processing Kavenegar webhook: %s", exc)
        # Return 200 anyway so Kavenegar doesn't retry endlessly
        return {"status": "error", "detail": str(exc)}

    return {"status": "ok"}


async def _process_delivery_update(data: dict[str, Any]) -> None:
    """Update SMS log record with delivery status from webhook."""
    from src.infrastructure.connectors.sms.kavenegar_provider import (
        KavenegarProvider,
        KAVENEGAR_STATUS_MAP,
    )
    from src.core.interfaces.messaging import MessageStatus
    from src.infrastructure.database.session import get_session_factory
    from src.modules.communications.infrastructure.repositories import SMSLogRepository
    from uuid import UUID

    # Parse webhook payload
    provider = KavenegarProvider.__new__(KavenegarProvider)
    status_result = provider.parse_webhook_payload(data)

    session_factory = get_session_factory()
    # Use default tenant for webhook processing
    default_tenant_id = UUID("00000000-0000-0000-0000-000000000001")

    async with session_factory() as session:
        repo = SMSLogRepository(session, default_tenant_id)

        # Find the SMS log by provider message ID
        sms_log = await repo.get_by_provider_id(status_result.message_id)
        if not sms_log:
            logger.warning("Webhook: SMS log not found for messageid=%s", status_result.message_id)
            return

        # Update status
        if status_result.status == MessageStatus.DELIVERED:
            sms_log.mark_delivered()
        elif status_result.status == MessageStatus.FAILED:
            sms_log.mark_failed(status_result.error_message or "Delivery failed (webhook)")

        await repo.update(sms_log)
        await session.commit()

    logger.info(
        "Webhook: Updated SMS %s → %s",
        status_result.message_id,
        status_result.status.value,
    )

