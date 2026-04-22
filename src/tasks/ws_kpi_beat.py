"""
Celery Beat Task — KPI Snapshot WebSocket Push (Phase 40)

Every 30 seconds this task queries live KPIs for each active tenant and
publishes a kpi_snapshot WSMessage to the Redis channel ws:{tenant_id}.
The FastAPI WebSocket endpoint subscribes and broadcasts to dashboard clients.
"""

from __future__ import annotations

import json
import logging

from src.infrastructure.messaging.celery_app import celery_app

logger = logging.getLogger(__name__)

WS_KPI_CHANNEL_PREFIX = "ws:"


@celery_app.task(name="tasks.push_kpi_snapshots", bind=True)
def push_kpi_snapshots(self):
    """Publish KPI snapshots for all active tenants."""
    import asyncio
    try:
        asyncio.run(_async_push_kpi_snapshots())
    except Exception as exc:
        logger.warning("push_kpi_snapshots failed: %s", exc)


async def _async_push_kpi_snapshots():
    from sqlalchemy import select, func
    from src.infrastructure.database.session import get_session_factory
    from src.infrastructure.database.models.tenants import TenantModel
    from src.infrastructure.database.models.leads import ContactModel
    from src.infrastructure.database.models.campaigns import CampaignModel
    from src.infrastructure.database.models.communications import SMSLogModel
    from src.api.ws_events import make_kpi_snapshot

    factory = get_session_factory()
    async with factory() as session:
        # Get all active tenants
        tenants_stmt = select(TenantModel.id).where(TenantModel.is_active == True)
        result = await session.execute(tenants_stmt)
        tenant_ids = [row[0] for row in result.all()]

        for tenant_id in tenant_ids:
            try:
                kpis = await _gather_kpis(session, tenant_id)
                msg = make_kpi_snapshot(tenant_id, kpis)
                await _publish_to_redis(str(tenant_id), msg.serialize())
            except Exception as exc:
                logger.debug("KPI push failed for tenant %s: %s", tenant_id, exc)


async def _gather_kpis(session, tenant_id):
    from sqlalchemy import select, func
    from src.infrastructure.database.models.leads import ContactModel
    from src.infrastructure.database.models.campaigns import CampaignModel
    from src.infrastructure.database.models.communications import SMSLogModel
    from datetime import date

    today = date.today()

    # Total contacts
    contacts_stmt = (
        select(func.count(ContactModel.id))
        .where(ContactModel.tenant_id == tenant_id)
        .where(ContactModel.is_active == True)
    )
    total_contacts = (await session.execute(contacts_stmt)).scalar() or 0

    # Active campaigns
    campaigns_stmt = (
        select(func.count(CampaignModel.id))
        .where(CampaignModel.tenant_id == tenant_id)
        .where(CampaignModel.status.in_(["sending", "running", "tracking"]))
    )
    active_campaigns = (await session.execute(campaigns_stmt)).scalar() or 0

    # SMS sent today
    from sqlalchemy import cast, Date
    sms_stmt = (
        select(func.count(SMSLogModel.id))
        .where(SMSLogModel.tenant_id == tenant_id)
        .where(cast(SMSLogModel.created_at, Date) == today)
    )
    sms_today = (await session.execute(sms_stmt)).scalar() or 0

    return {
        "total_contacts": total_contacts,
        "active_campaigns": active_campaigns,
        "sms_sent_today": sms_today,
    }


async def _publish_to_redis(tenant_id: str, message: str):
    import redis.asyncio as redis
    from src.core.config import settings

    channel = f"{WS_KPI_CHANNEL_PREFIX}{tenant_id}"
    r = redis.from_url(settings.redis_url, decode_responses=True)
    try:
        await r.publish(channel, message)
    finally:
        await r.aclose()

