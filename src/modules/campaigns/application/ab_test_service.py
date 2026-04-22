"""
Campaigns Application Service — A/B Test Operations
"""

from __future__ import annotations

import random
from uuid import UUID

from sqlalchemy import select, update as sa_update
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.database.models.campaigns import CampaignModel, CampaignRecipientModel
from src.modules.campaigns.domain.ab_test import (
    ABTestConfig,
    ABTestVariant,
    WinnerCriteria,
    compute_winner,
)


class ABTestService:
    """Manages A/B test lifecycle for a campaign."""

    def __init__(self, session: AsyncSession, tenant_id: UUID):
        self._session = session
        self._tenant_id = tenant_id

    # ── Launch ──────────────────────────────────────────────────────────────

    async def launch(
        self, campaign_id: UUID, config: ABTestConfig
    ) -> dict:
        """
        Split campaign recipients into two variant groups and persist the
        variant configuration on the campaign record.
        """
        # Load campaign
        stmt = (
            select(CampaignModel)
            .where(CampaignModel.tenant_id == self._tenant_id)
            .where(CampaignModel.id == campaign_id)
        )
        result = await self._session.execute(stmt)
        campaign = result.scalar_one_or_none()
        if not campaign:
            raise ValueError(f"Campaign {campaign_id} not found")

        # Load recipients
        rec_stmt = (
            select(CampaignRecipientModel)
            .where(CampaignRecipientModel.campaign_id == campaign_id)
        )
        rec_result = await self._session.execute(rec_stmt)
        recipients = rec_result.scalars().all()

        # Shuffle + split
        shuffled = list(recipients)
        random.shuffle(shuffled)
        split_at = max(1, int(len(shuffled) * config.split_percent / 100))
        group_a = shuffled[:split_at]
        group_b = shuffled[split_at:]

        # Stamp variant_name on recipients
        for r in group_a:
            r.metadata_ = {**(r.metadata_ or {}), "ab_variant": "A"}
        for r in group_b:
            r.metadata_ = {**(r.metadata_ or {}), "ab_variant": "B"}

        # Persist A/B config on campaign
        ab_data = {
            "message_a": config.message_a,
            "message_b": config.message_b,
            "split_percent": config.split_percent,
            "winner_criteria": config.winner_criteria,
            "min_sample_size": config.min_sample_size,
            "sent_a": 0, "sent_b": 0,
            "opens_a": 0, "opens_b": 0,
            "conversions_a": 0, "conversions_b": 0,
            "winner": None,
        }
        campaign.is_ab_test = True
        campaign.metadata_ = {**(campaign.metadata_ or {}), "ab_test": ab_data}

        await self._session.flush()

        return {
            "campaign_id": str(campaign_id),
            "group_a_size": len(group_a),
            "group_b_size": len(group_b),
        }

    # ── Record Event ────────────────────────────────────────────────────────

    async def record_event(
        self,
        campaign_id: UUID,
        variant: str,
        event_type: str,  # "sent" | "open" | "conversion"
    ) -> None:
        """Increment counters for a variant event."""
        stmt = (
            select(CampaignModel)
            .where(CampaignModel.tenant_id == self._tenant_id)
            .where(CampaignModel.id == campaign_id)
        )
        result = await self._session.execute(stmt)
        campaign = result.scalar_one_or_none()
        if not campaign:
            return

        meta = campaign.metadata_ or {}
        ab = meta.get("ab_test", {})
        key = f"{event_type}_{variant.lower()}"
        ab[key] = ab.get(key, 0) + 1
        meta["ab_test"] = ab
        campaign.metadata_ = meta
        await self._session.flush()

    # ── Get Live Results ────────────────────────────────────────────────────

    async def get_results(self, campaign_id: UUID) -> dict:
        """Return live A/B metrics for a campaign."""
        stmt = (
            select(CampaignModel)
            .where(CampaignModel.tenant_id == self._tenant_id)
            .where(CampaignModel.id == campaign_id)
        )
        result = await self._session.execute(stmt)
        campaign = result.scalar_one_or_none()
        if not campaign or not campaign.is_ab_test:
            return {"error": "not an A/B test campaign"}

        ab = (campaign.metadata_ or {}).get("ab_test", {})

        def rate(opens: int, sent: int) -> float:
            return round(opens / sent, 4) if sent else 0.0

        sent_a = ab.get("sent_a", 0)
        sent_b = ab.get("sent_b", 0)
        opens_a = ab.get("opens_a", 0)
        opens_b = ab.get("opens_b", 0)
        conv_a = ab.get("conversions_a", 0)
        conv_b = ab.get("conversions_b", 0)

        va = ABTestVariant(
            campaign_id=campaign_id, variant_name="A",
            message_content=ab.get("message_a", ""),
            split_percent=ab.get("split_percent", 50),
            total_sent=sent_a, total_opens=opens_a, total_conversions=conv_a,
        )
        vb = ABTestVariant(
            campaign_id=campaign_id, variant_name="B",
            message_content=ab.get("message_b", ""),
            split_percent=100 - ab.get("split_percent", 50),
            total_sent=sent_b, total_opens=opens_b, total_conversions=conv_b,
        )

        criteria: WinnerCriteria = ab.get("winner_criteria", "open_rate")
        winner = compute_winner(va, vb, criteria, ab.get("min_sample_size", 50))

        return {
            "campaign_id": str(campaign_id),
            "winner_criteria": criteria,
            "winner": winner,
            "variant_a": {
                "sent": sent_a, "opens": opens_a, "conversions": conv_a,
                "open_rate": rate(opens_a, sent_a),
                "conversion_rate": rate(conv_a, sent_a),
                "message": ab.get("message_a", ""),
            },
            "variant_b": {
                "sent": sent_b, "opens": opens_b, "conversions": conv_b,
                "open_rate": rate(opens_b, sent_b),
                "conversion_rate": rate(conv_b, sent_b),
                "message": ab.get("message_b", ""),
            },
        }

    # ── Promote Winner ──────────────────────────────────────────────────────

    async def promote_winner(self, campaign_id: UUID, winner: str) -> dict:
        """Set campaign message_content to the winning variant's message."""
        stmt = (
            select(CampaignModel)
            .where(CampaignModel.tenant_id == self._tenant_id)
            .where(CampaignModel.id == campaign_id)
        )
        result = await self._session.execute(stmt)
        campaign = result.scalar_one_or_none()
        if not campaign:
            raise ValueError(f"Campaign {campaign_id} not found")

        ab = (campaign.metadata_ or {}).get("ab_test", {})
        winning_message = ab.get(f"message_{winner.lower()}", campaign.message_content)
        campaign.message_content = winning_message

        ab["winner"] = winner
        meta = campaign.metadata_ or {}
        meta["ab_test"] = ab
        campaign.metadata_ = meta
        await self._session.flush()

        return {"campaign_id": str(campaign_id), "winner": winner, "message": winning_message}

