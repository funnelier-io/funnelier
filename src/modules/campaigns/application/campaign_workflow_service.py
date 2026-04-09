"""
Campaign Workflow Service

Application service that orchestrates campaign lifecycle through Camunda BPMS
when enabled, with graceful fallback to direct status updates when disabled.
"""

import logging
from datetime import datetime
from typing import Any
from uuid import UUID

from src.infrastructure.camunda.client import (
    CamundaClient,
    CamundaConnectionError,
    CamundaError,
)
from src.modules.campaigns.infrastructure.repositories import CampaignRepository

logger = logging.getLogger(__name__)


class CampaignWorkflowService:
    """
    Manages campaign lifecycle via Camunda BPMS with fallback.

    When Camunda is enabled and reachable:
      - start: starts a Camunda process instance
      - pause: suspends the process instance
      - resume: activates the suspended instance
      - cancel: deletes the process instance

    When Camunda is disabled or unreachable:
      - Falls back to direct DB status updates (same as Phase 11 behaviour)
    """

    def __init__(
        self,
        camunda_client: CamundaClient,
        repo: CampaignRepository,
    ):
        self._camunda = camunda_client
        self._repo = repo

    # ── Start ────────────────────────────────────────────────────────────

    async def start_campaign(
        self,
        campaign_id: UUID,
        tenant_id: UUID,
    ) -> Any:
        """
        Start a campaign lifecycle.  Returns the updated CampaignModel.

        Tries Camunda first; falls back to legacy on any failure.
        """
        model = await self._repo.get_model(campaign_id)
        if not model:
            return None

        process_instance_id: str | None = None

        if self._camunda.enabled:
            try:
                instance = await self._camunda.start_process(
                    process_key="campaign_lifecycle",
                    business_key=str(campaign_id),
                    variables={
                        "campaign_id": str(campaign_id),
                        "tenant_id": str(tenant_id),
                        "campaign_name": model.name,
                        "campaign_type": model.campaign_type or "sms",
                    },
                    tenant_id=str(tenant_id),
                )
                process_instance_id = instance.id
                logger.info(
                    "Campaign %s started via Camunda (process=%s)",
                    campaign_id, process_instance_id,
                )
            except (CamundaConnectionError, CamundaError) as e:
                logger.warning(
                    "Camunda unavailable for campaign %s — falling back: %s",
                    campaign_id, e,
                )

        # Update DB regardless
        extra: dict[str, Any] = {"started_at": datetime.utcnow()}
        if process_instance_id:
            extra["process_instance_id"] = process_instance_id

        updated = await self._repo.update_status(campaign_id, "running", **extra)
        return updated

    # ── Pause ────────────────────────────────────────────────────────────

    async def pause_campaign(self, campaign_id: UUID) -> Any:
        """Pause a running campaign.  Returns updated CampaignModel."""
        model = await self._repo.get_model(campaign_id)
        if not model:
            return None

        if self._camunda.enabled and model.process_instance_id:
            try:
                await self._camunda.suspend_process_instance(model.process_instance_id)
                logger.info(
                    "Campaign %s suspended in Camunda (process=%s)",
                    campaign_id, model.process_instance_id,
                )
            except (CamundaConnectionError, CamundaError) as e:
                logger.warning(
                    "Camunda suspend failed for campaign %s — updating DB only: %s",
                    campaign_id, e,
                )

        updated = await self._repo.update_status(campaign_id, "paused")
        return updated

    # ── Resume ───────────────────────────────────────────────────────────

    async def resume_campaign(self, campaign_id: UUID) -> Any:
        """Resume a paused campaign.  Returns updated CampaignModel."""
        model = await self._repo.get_model(campaign_id)
        if not model:
            return None

        if self._camunda.enabled and model.process_instance_id:
            try:
                await self._camunda.activate_process_instance(model.process_instance_id)
                logger.info(
                    "Campaign %s activated in Camunda (process=%s)",
                    campaign_id, model.process_instance_id,
                )
            except (CamundaConnectionError, CamundaError) as e:
                logger.warning(
                    "Camunda activate failed for campaign %s — updating DB only: %s",
                    campaign_id, e,
                )

        updated = await self._repo.update_status(campaign_id, "running")
        return updated

    # ── Cancel ───────────────────────────────────────────────────────────

    async def cancel_campaign(self, campaign_id: UUID) -> Any:
        """Cancel a campaign.  Returns updated CampaignModel."""
        model = await self._repo.get_model(campaign_id)
        if not model:
            return None

        if self._camunda.enabled and model.process_instance_id:
            try:
                await self._camunda.delete_process_instance(
                    model.process_instance_id,
                    reason=f"Campaign {campaign_id} cancelled by user",
                )
                logger.info(
                    "Campaign %s cancelled in Camunda (process=%s)",
                    campaign_id, model.process_instance_id,
                )
            except (CamundaConnectionError, CamundaError) as e:
                logger.warning(
                    "Camunda cancel failed for campaign %s — updating DB only: %s",
                    campaign_id, e,
                )

        updated = await self._repo.update_status(campaign_id, "cancelled")
        return updated

