"""
WebSocket Event Types and Messages (Phase 40)

All WS events pushed from Celery beat → Redis pub/sub → dashboard clients.
"""

from __future__ import annotations

import json
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class WSEventType(str, Enum):
    KPI_SNAPSHOT = "kpi_snapshot"
    NEW_LEAD = "new_lead"
    STAGE_CHANGE = "stage_change"
    SMS_SENT = "sms_sent"
    CAMPAIGN_COMPLETE = "campaign_complete"


class WSMessage(BaseModel):
    type: WSEventType
    tenant_id: str
    payload: dict[str, Any] = Field(default_factory=dict)
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())

    def serialize(self) -> str:
        return self.model_dump_json()


def make_kpi_snapshot(tenant_id: UUID | str, kpis: dict) -> WSMessage:
    return WSMessage(type=WSEventType.KPI_SNAPSHOT, tenant_id=str(tenant_id), payload=kpis)


def make_new_lead(tenant_id: UUID | str, contact_id: str, name: str) -> WSMessage:
    return WSMessage(
        type=WSEventType.NEW_LEAD,
        tenant_id=str(tenant_id),
        payload={"contact_id": contact_id, "name": name},
    )


def make_stage_change(tenant_id: UUID | str, contact_id: str, stage: str) -> WSMessage:
    return WSMessage(
        type=WSEventType.STAGE_CHANGE,
        tenant_id=str(tenant_id),
        payload={"contact_id": contact_id, "stage": stage},
    )


def make_sms_sent(tenant_id: UUID | str, campaign_id: str, count: int) -> WSMessage:
    return WSMessage(
        type=WSEventType.SMS_SENT,
        tenant_id=str(tenant_id),
        payload={"campaign_id": campaign_id, "count": count},
    )


def make_campaign_complete(tenant_id: UUID | str, campaign_id: str, name: str) -> WSMessage:
    return WSMessage(
        type=WSEventType.CAMPAIGN_COMPLETE,
        tenant_id=str(tenant_id),
        payload={"campaign_id": campaign_id, "name": name},
    )

