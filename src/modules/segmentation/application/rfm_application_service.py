"""
RFM Application Service

Orchestrates RFM analysis, profile management, and segment-based actions.
"""

from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from src.core.domain import RFMSegment

from ..domain import (
    ContactRFMProfile,
    RFMAnalysisResult,
    RFMConfig,
    RFMCalculationService,
    SegmentRecommendationService,
    SEGMENT_RECOMMENDATIONS,
)


class RFMApplicationService:
    """
    Application service for RFM analysis and management.
    """

    def __init__(
        self,
        contact_repository: Any,
        invoice_repository: Any,
        payment_repository: Any,
        rfm_profile_repository: Any,
        config_repository: Any,
    ):
        self._contact_repo = contact_repository
        self._invoice_repo = invoice_repository
        self._payment_repo = payment_repository
        self._rfm_profile_repo = rfm_profile_repository
        self._config_repo = config_repository
        self._recommendation_service = SegmentRecommendationService()

    async def get_rfm_config(self, tenant_id: UUID) -> RFMConfig:
        """
        Get RFM configuration for tenant.
        """
        config = await self._config_repo.get_by_tenant(tenant_id)
        if not config:
            # Return default config
            config = RFMConfig(tenant_id=tenant_id)
        return config

    async def update_rfm_config(
        self,
        tenant_id: UUID,
        config_data: dict[str, Any],
    ) -> RFMConfig:
        """
        Update RFM configuration for tenant.
        """
        config = await self.get_rfm_config(tenant_id)

        if "recency_thresholds" in config_data:
            config.recency_thresholds = config_data["recency_thresholds"]
        if "frequency_thresholds" in config_data:
            config.frequency_thresholds = config_data["frequency_thresholds"]
        if "monetary_thresholds" in config_data:
            config.monetary_thresholds = config_data["monetary_thresholds"]
        if "analysis_period_months" in config_data:
            config.analysis_period_months = config_data["analysis_period_months"]
        if "high_value_threshold" in config_data:
            config.high_value_threshold = config_data["high_value_threshold"]
        if "recent_days" in config_data:
            config.recent_days = config_data["recent_days"]

        await self._config_repo.save(config)
        return config

    async def calculate_contact_rfm(
        self,
        tenant_id: UUID,
        contact_id: UUID,
    ) -> ContactRFMProfile:
        """
        Calculate RFM for a single contact.
        """
        config = await self.get_rfm_config(tenant_id)
        calc_service = RFMCalculationService(config)

        # Get contact info
        contact = await self._contact_repo.get(contact_id)
        if not contact:
            raise ValueError(f"Contact not found: {contact_id}")

        # Get purchase history
        purchases = await self._payment_repo.get_by_phone(
            phone_number=contact["phone_number"],
            tenant_id=tenant_id,
        )

        # Calculate metrics
        purchase_count = len([p for p in purchases if p.get("is_successful")])
        total_spend = sum(
            p.get("amount", 0) for p in purchases if p.get("is_successful")
        )
        last_purchase_date = None
        if purchases:
            successful = [p for p in purchases if p.get("is_successful")]
            if successful:
                dates = [p.get("paid_at") for p in successful if p.get("paid_at")]
                if dates:
                    last_purchase_date = max(dates)

        # Calculate profile
        profile = calc_service.calculate_profile(
            tenant_id=tenant_id,
            contact_id=contact_id,
            phone_number=contact["phone_number"],
            last_purchase_date=last_purchase_date,
            purchase_count=purchase_count,
            total_spend=total_spend,
        )

        # Save profile
        await self._rfm_profile_repo.save(profile)

        return profile

    async def run_batch_rfm_calculation(
        self,
        tenant_id: UUID,
        limit: int | None = None,
    ) -> RFMAnalysisResult:
        """
        Calculate RFM for all contacts with purchase history.
        """
        config = await self.get_rfm_config(tenant_id)
        calc_service = RFMCalculationService(config)

        # Get contacts with purchase data
        period_start = datetime.utcnow() - timedelta(
            days=config.analysis_period_months * 30
        )

        contacts_data = await self._get_contacts_purchase_data(
            tenant_id=tenant_id,
            period_start=period_start,
            limit=limit,
        )

        # Calculate RFM for all contacts
        profiles = calc_service.batch_calculate(contacts_data)

        # Save profiles
        for profile in profiles:
            await self._rfm_profile_repo.save(profile)

        # Analyze segments
        result = calc_service.analyze_segments(
            tenant_id=tenant_id,
            profiles=profiles,
        )

        return result

    async def _get_contacts_purchase_data(
        self,
        tenant_id: UUID,
        period_start: datetime,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        Get contact data with purchase metrics.
        """
        # Get all payments in the period
        payments = await self._payment_repo.get_by_period(
            tenant_id=tenant_id,
            start_date=period_start,
            end_date=datetime.utcnow(),
        )

        # Aggregate by phone number
        phone_data: dict[str, dict[str, Any]] = {}

        for payment in payments:
            if not payment.get("is_successful"):
                continue

            phone = payment.get("phone_number")
            if not phone:
                continue

            if phone not in phone_data:
                phone_data[phone] = {
                    "tenant_id": tenant_id,
                    "phone_number": phone,
                    "purchase_count": 0,
                    "total_spend": 0.0,
                    "last_purchase_date": None,
                }

            phone_data[phone]["purchase_count"] += 1
            phone_data[phone]["total_spend"] += payment.get("amount", 0)

            paid_at = payment.get("paid_at")
            if paid_at:
                if (
                    phone_data[phone]["last_purchase_date"] is None
                    or paid_at > phone_data[phone]["last_purchase_date"]
                ):
                    phone_data[phone]["last_purchase_date"] = paid_at

        # Get contact IDs
        result = []
        for phone, data in phone_data.items():
            contact = await self._contact_repo.get_by_phone(phone, tenant_id)
            if contact:
                data["contact_id"] = contact["id"]
                result.append(data)

        if limit:
            result = result[:limit]

        return result

    async def get_segment_distribution(
        self,
        tenant_id: UUID,
    ) -> dict[str, int]:
        """
        Get current segment distribution for tenant.
        """
        profiles = await self._rfm_profile_repo.get_all_by_tenant(tenant_id)

        distribution: dict[str, int] = {}
        for segment in RFMSegment:
            distribution[segment.value] = 0

        for profile in profiles:
            if profile.segment:
                distribution[profile.segment.value] = (
                    distribution.get(profile.segment.value, 0) + 1
                )

        return distribution

    async def get_contacts_by_segment(
        self,
        tenant_id: UUID,
        segment: RFMSegment,
        limit: int = 100,
        offset: int = 0,
    ) -> list[ContactRFMProfile]:
        """
        Get contacts in a specific segment.
        """
        return await self._rfm_profile_repo.get_by_segment(
            tenant_id=tenant_id,
            segment=segment,
            limit=limit,
            offset=offset,
        )

    async def get_segment_recommendations(
        self,
        segment: RFMSegment,
    ) -> dict[str, Any]:
        """
        Get marketing recommendations for a segment.
        """
        rec = self._recommendation_service.get_recommendation(segment)
        return {
            "segment": segment.value,
            "segment_name_fa": rec.segment_name_fa,
            "description_fa": rec.description_fa,
            "recommended_message_types": rec.recommended_message_types,
            "recommended_products": rec.recommended_products,
            "contact_frequency": rec.contact_frequency,
            "channel_priority": rec.channel_priority,
            "discount_allowed": rec.discount_allowed,
            "max_discount_percent": rec.max_discount_percent,
        }

    async def get_high_priority_contacts(
        self,
        tenant_id: UUID,
        limit: int = 50,
    ) -> list[ContactRFMProfile]:
        """
        Get contacts prioritized for marketing action.
        """
        # Get profiles from high-priority segments
        priority_segments = [
            RFMSegment.CANT_LOSE,  # Urgent - high value at risk
            RFMSegment.AT_RISK,  # Need immediate attention
            RFMSegment.CHAMPIONS,  # Best customers
            RFMSegment.LOYAL,  # Valuable customers
        ]

        all_profiles = []
        for segment in priority_segments:
            profiles = await self._rfm_profile_repo.get_by_segment(
                tenant_id=tenant_id,
                segment=segment,
                limit=limit,
            )
            all_profiles.extend(profiles)

        # Sort by priority and value
        prioritized = self._recommendation_service.prioritize_contacts(all_profiles)

        return prioritized[:limit]

    async def get_contacts_for_campaign(
        self,
        tenant_id: UUID,
        campaign_type: str,
        limit: int = 1000,
    ) -> list[ContactRFMProfile]:
        """
        Get contacts suitable for a specific campaign type.
        """
        # Get all profiles
        profiles = await self._rfm_profile_repo.get_all_by_tenant(tenant_id)

        # Filter by campaign type
        suitable = self._recommendation_service.segment_contacts_for_campaign(
            profiles=profiles,
            campaign_type=campaign_type,
        )

        return suitable[:limit]

    async def get_segment_migration_report(
        self,
        tenant_id: UUID,
        months: int = 1,
    ) -> dict[str, Any]:
        """
        Get report on segment migrations over time.
        """
        # Get profiles with history
        profiles = await self._rfm_profile_repo.get_all_by_tenant(tenant_id)

        migrations: dict[str, dict[str, int]] = {}
        improved = 0
        declined = 0
        unchanged = 0

        for profile in profiles:
            if not profile.rfm_history:
                unchanged += 1
                continue

            # Get previous segment
            prev_entry = profile.rfm_history[-1]
            prev_segment = prev_entry.get("segment")
            current_segment = profile.segment.value if profile.segment else None

            if prev_segment == current_segment:
                unchanged += 1
            else:
                key = f"{prev_segment}_to_{current_segment}"
                migrations[key] = migrations.get(key, 0) + 1

                # Determine if improved or declined
                prev_priority = SEGMENT_RECOMMENDATIONS.get(
                    RFMSegment(prev_segment), None
                )
                curr_priority = SEGMENT_RECOMMENDATIONS.get(
                    profile.segment, None
                ) if profile.segment else None

                if prev_priority and curr_priority:
                    if profile.segment.priority > RFMSegment(prev_segment).priority:
                        improved += 1
                    else:
                        declined += 1

        return {
            "period_months": months,
            "total_contacts": len(profiles),
            "improved": improved,
            "declined": declined,
            "unchanged": unchanged,
            "migrations": migrations,
        }
