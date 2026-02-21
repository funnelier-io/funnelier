"""
Segmentation Module - RFM Service
Business logic for RFM calculation and recommendations
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from src.core.domain import RFMSegment

from .entities import (
    ContactRFMProfile,
    RFMAnalysisResult,
    RFMConfig,
    RFMScore,
    SEGMENT_RECOMMENDATIONS,
    SegmentRecommendation,
    SegmentSummary,
)


class RFMCalculationService:
    """
    Service for calculating RFM scores.
    """

    def __init__(self, config: RFMConfig | None = None):
        self.config = config or RFMConfig(tenant_id=UUID("00000000-0000-0000-0000-000000000000"))

    def calculate_score(
        self,
        days_since_last_purchase: int | None,
        purchase_count: int,
        total_spend: float,
    ) -> RFMScore:
        """
        Calculate RFM score for given metrics.
        """
        r = self.config.calculate_recency_score(days_since_last_purchase)
        f = self.config.calculate_frequency_score(purchase_count)
        m = self.config.calculate_monetary_score(total_spend)

        return RFMScore(recency=r, frequency=f, monetary=m)

    def calculate_profile(
        self,
        tenant_id: UUID,
        contact_id: UUID,
        phone_number: str,
        last_purchase_date: datetime | None,
        purchase_count: int,
        total_spend: float,
        current_date: datetime | None = None,
    ) -> ContactRFMProfile:
        """
        Calculate complete RFM profile for a contact.
        """
        if current_date is None:
            current_date = datetime.utcnow()

        # Calculate days since last purchase
        days_since = None
        if last_purchase_date:
            days_since = (current_date - last_purchase_date).days

        # Calculate RFM score
        rfm_score = self.calculate_score(days_since, purchase_count, total_spend)

        # Determine segment using core RFMSegment
        segment = RFMSegment.from_rfm_score(
            rfm_score.recency, rfm_score.frequency, rfm_score.monetary
        )

        # Calculate AOV
        aov = total_spend / purchase_count if purchase_count > 0 else 0.0

        # Create profile
        profile = ContactRFMProfile(
            tenant_id=tenant_id,
            contact_id=contact_id,
            phone_number=phone_number,
            last_purchase_date=last_purchase_date,
            days_since_last_purchase=days_since,
            purchase_count=purchase_count,
            total_spend=total_spend,
            average_order_value=aov,
            rfm_score=rfm_score,
            segment=segment,
        )

        return profile

    def batch_calculate(
        self,
        contacts_data: list[dict[str, Any]],
        current_date: datetime | None = None,
    ) -> list[ContactRFMProfile]:
        """
        Calculate RFM profiles for multiple contacts.

        contacts_data should contain:
        - tenant_id
        - contact_id
        - phone_number
        - last_purchase_date (optional)
        - purchase_count
        - total_spend
        """
        if current_date is None:
            current_date = datetime.utcnow()

        results = []
        for data in contacts_data:
            profile = self.calculate_profile(
                tenant_id=data["tenant_id"],
                contact_id=data["contact_id"],
                phone_number=data["phone_number"],
                last_purchase_date=data.get("last_purchase_date"),
                purchase_count=data.get("purchase_count", 0),
                total_spend=data.get("total_spend", 0.0),
                current_date=current_date,
            )
            results.append(profile)

        return results

    def analyze_segments(
        self,
        tenant_id: UUID,
        profiles: list[ContactRFMProfile],
        current_date: datetime | None = None,
    ) -> RFMAnalysisResult:
        """
        Perform segment analysis on a list of profiles.
        """
        if current_date is None:
            current_date = datetime.utcnow()

        result = RFMAnalysisResult(
            tenant_id=tenant_id,
            analysis_date=current_date,
            period_months=self.config.analysis_period_months,
            total_contacts_analyzed=len(profiles),
        )

        # Group by segment
        segment_data: dict[RFMSegment, list[ContactRFMProfile]] = {}
        for profile in profiles:
            if profile.segment:
                if profile.segment not in segment_data:
                    segment_data[profile.segment] = []
                segment_data[profile.segment].append(profile)

                if profile.purchase_count > 0:
                    result.contacts_with_purchases += 1
                    result.total_revenue += profile.total_spend

        # Calculate segment summaries
        for segment, segment_profiles in segment_data.items():
            count = len(segment_profiles)
            total_revenue = sum(p.total_spend for p in segment_profiles)
            total_frequency = sum(p.purchase_count for p in segment_profiles)
            total_recency = sum(
                p.days_since_last_purchase or 0 for p in segment_profiles
            )

            summary = SegmentSummary(
                segment=segment,
                contact_count=count,
                percentage_of_total=(count / len(profiles) * 100) if profiles else 0,
                total_revenue=total_revenue,
                average_order_value=total_revenue / total_frequency if total_frequency > 0 else 0,
                average_frequency=total_frequency / count if count > 0 else 0,
                average_recency_days=total_recency / count if count > 0 else 0,
            )
            result.segment_summaries.append(summary)

        # Sort by segment priority
        result.segment_summaries.sort(
            key=lambda s: s.segment.priority if hasattr(s.segment, 'priority') else 0,
            reverse=True,
        )

        # Calculate average CLV
        if result.contacts_with_purchases > 0:
            result.average_clv = result.total_revenue / result.contacts_with_purchases

        return result


class SegmentRecommendationService:
    """
    Service for generating recommendations based on segments.
    """

    def get_recommendation(self, segment: RFMSegment) -> SegmentRecommendation:
        """
        Get marketing recommendation for a segment.
        """
        return SEGMENT_RECOMMENDATIONS.get(
            segment,
            SEGMENT_RECOMMENDATIONS[RFMSegment.NEED_ATTENTION],
        )

    def get_all_recommendations(self) -> dict[RFMSegment, SegmentRecommendation]:
        """
        Get all segment recommendations.
        """
        return SEGMENT_RECOMMENDATIONS

    def get_message_types_for_segment(self, segment: RFMSegment) -> list[str]:
        """
        Get recommended message types for a segment.
        """
        rec = self.get_recommendation(segment)
        return rec.recommended_message_types

    def get_products_for_segment(self, segment: RFMSegment) -> list[str]:
        """
        Get recommended product categories for a segment.
        """
        rec = self.get_recommendation(segment)
        return rec.recommended_products

    def get_channel_priority(self, segment: RFMSegment) -> list[str]:
        """
        Get channel priority for a segment.
        """
        rec = self.get_recommendation(segment)
        return rec.channel_priority

    def get_discount_strategy(self, segment: RFMSegment) -> dict[str, Any]:
        """
        Get discount strategy for a segment.
        """
        rec = self.get_recommendation(segment)
        return {
            "allowed": rec.discount_allowed,
            "max_percent": rec.max_discount_percent,
        }

    def prioritize_contacts(
        self,
        profiles: list[ContactRFMProfile],
    ) -> list[ContactRFMProfile]:
        """
        Sort contacts by marketing priority.
        """
        return sorted(
            profiles,
            key=lambda p: (
                p.segment.priority if p.segment else 0,
                p.rfm_score.segment_score if p.rfm_score else 0,
            ),
            reverse=True,
        )

    def segment_contacts_for_campaign(
        self,
        profiles: list[ContactRFMProfile],
        campaign_type: str,
    ) -> list[ContactRFMProfile]:
        """
        Filter contacts suitable for a campaign type.
        """
        suitable_segments = self._get_segments_for_campaign_type(campaign_type)

        return [
            p for p in profiles
            if p.segment in suitable_segments
        ]

    def _get_segments_for_campaign_type(self, campaign_type: str) -> list[RFMSegment]:
        """
        Get segments suitable for a campaign type.
        """
        campaign_segments = {
            "promotional": [
                RFMSegment.POTENTIAL_LOYALIST,
                RFMSegment.PROMISING,
                RFMSegment.NEW_CUSTOMERS,
            ],
            "retention": [
                RFMSegment.NEED_ATTENTION,
                RFMSegment.ABOUT_TO_SLEEP,
                RFMSegment.AT_RISK,
            ],
            "win_back": [
                RFMSegment.AT_RISK,
                RFMSegment.CANT_LOSE,
                RFMSegment.HIBERNATING,
            ],
            "vip": [
                RFMSegment.CHAMPIONS,
                RFMSegment.LOYAL,
            ],
            "upsell": [
                RFMSegment.LOYAL,
                RFMSegment.POTENTIAL_LOYALIST,
                RFMSegment.CHAMPIONS,
            ],
            "new_product": [
                RFMSegment.CHAMPIONS,
                RFMSegment.LOYAL,
                RFMSegment.POTENTIAL_LOYALIST,
            ],
        }

        return campaign_segments.get(campaign_type, list(RFMSegment))
