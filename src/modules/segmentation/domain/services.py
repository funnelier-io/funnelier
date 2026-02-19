"""
Segmentation Module - RFM Service
Business logic for RFM calculation and recommendations
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from src.core.domain import RFMSegment

from .entities import (
    ContactRFMScore,
    ProductRecommendation,
    RFMConfig,
    SegmentDefinition,
    SegmentStats,
    TemplateRecommendation,
)


class RFMCalculationService:
    """
    Service for calculating RFM scores.
    """

    def __init__(self, config: RFMConfig):
        self.config = config

    def calculate_score(
        self,
        tenant_id: UUID,
        contact_id: UUID,
        phone_number: str,
        last_purchase_date: datetime | None,
        total_purchases: int,
        total_spend: int,
        first_purchase_date: datetime | None = None,
        current_date: datetime | None = None,
    ) -> ContactRFMScore:
        """
        Calculate RFM score for a contact.
        """
        if current_date is None:
            current_date = datetime.utcnow()

        score = ContactRFMScore(
            tenant_id=tenant_id,
            contact_id=contact_id,
            phone_number=phone_number,
            last_purchase_date=last_purchase_date,
            first_purchase_date=first_purchase_date,
            total_purchases=total_purchases,
            total_spend=total_spend,
        )

        score.calculate(self.config, current_date)
        return score

    def batch_calculate(
        self,
        contacts_data: list[dict[str, Any]],
        current_date: datetime | None = None,
    ) -> list[ContactRFMScore]:
        """
        Calculate RFM scores for multiple contacts.

        contacts_data should contain:
        - tenant_id
        - contact_id
        - phone_number
        - last_purchase_date
        - total_purchases
        - total_spend
        - first_purchase_date (optional)
        """
        if current_date is None:
            current_date = datetime.utcnow()

        results = []
        for data in contacts_data:
            score = self.calculate_score(
                tenant_id=data["tenant_id"],
                contact_id=data["contact_id"],
                phone_number=data["phone_number"],
                last_purchase_date=data.get("last_purchase_date"),
                total_purchases=data.get("total_purchases", 0),
                total_spend=data.get("total_spend", 0),
                first_purchase_date=data.get("first_purchase_date"),
                current_date=current_date,
            )
            results.append(score)

        return results


class SegmentRecommendationService:
    """
    Service for generating recommendations based on segments.
    """

    # Default recommendations per segment
    SEGMENT_ACTIONS = {
        RFMSegment.CHAMPIONS: {
            "action": "Reward loyalty, exclusive offers, ask for referrals",
            "sms_categories": ["vip", "exclusive", "referral"],
            "product_strategy": "premium",
            "urgency": "low",
        },
        RFMSegment.LOYAL: {
            "action": "Upsell higher value products, loyalty programs",
            "sms_categories": ["upsell", "loyalty", "new_product"],
            "product_strategy": "upsell",
            "urgency": "low",
        },
        RFMSegment.POTENTIAL_LOYALIST: {
            "action": "Engage more, offer membership benefits",
            "sms_categories": ["engagement", "membership", "discount"],
            "product_strategy": "cross_sell",
            "urgency": "medium",
        },
        RFMSegment.NEW_CUSTOMERS: {
            "action": "Welcome sequence, onboarding, build relationship",
            "sms_categories": ["welcome", "onboarding", "first_purchase"],
            "product_strategy": "entry_level",
            "urgency": "high",
        },
        RFMSegment.PROMISING: {
            "action": "Create brand awareness, offer trials",
            "sms_categories": ["awareness", "trial", "introduction"],
            "product_strategy": "popular",
            "urgency": "medium",
        },
        RFMSegment.NEED_ATTENTION: {
            "action": "Limited time offers, reactivate interest",
            "sms_categories": ["limited_offer", "reminder", "discount"],
            "product_strategy": "best_sellers",
            "urgency": "high",
        },
        RFMSegment.ABOUT_TO_SLEEP: {
            "action": "Win-back campaigns, personalized offers",
            "sms_categories": ["winback", "personal", "special_offer"],
            "product_strategy": "previously_purchased",
            "urgency": "high",
        },
        RFMSegment.AT_RISK: {
            "action": "Urgent reactivation, personal outreach",
            "sms_categories": ["urgent", "personal", "vip_comeback"],
            "product_strategy": "high_margin",
            "urgency": "critical",
        },
        RFMSegment.CANT_LOSE: {
            "action": "Aggressive win-back, survey for feedback",
            "sms_categories": ["survey", "feedback", "exclusive_comeback"],
            "product_strategy": "premium",
            "urgency": "critical",
        },
        RFMSegment.HIBERNATING: {
            "action": "Cost-effective reactivation attempts",
            "sms_categories": ["reactivation", "bulk_discount"],
            "product_strategy": "clearance",
            "urgency": "low",
        },
        RFMSegment.LOST: {
            "action": "Final win-back attempt or remove from active list",
            "sms_categories": ["final_attempt", "unsubscribe"],
            "product_strategy": "none",
            "urgency": "low",
        },
    }

    def get_action_for_segment(self, segment: RFMSegment) -> dict[str, Any]:
        """Get recommended action for a segment."""
        return self.SEGMENT_ACTIONS.get(segment, {})

    def get_template_categories_for_segment(
        self,
        segment: RFMSegment,
    ) -> list[str]:
        """Get recommended SMS template categories for a segment."""
        action = self.SEGMENT_ACTIONS.get(segment, {})
        return action.get("sms_categories", [])

    def get_product_strategy_for_segment(
        self,
        segment: RFMSegment,
    ) -> str:
        """Get product recommendation strategy for a segment."""
        action = self.SEGMENT_ACTIONS.get(segment, {})
        return action.get("product_strategy", "popular")

    def get_urgency_for_segment(self, segment: RFMSegment) -> str:
        """Get action urgency for a segment."""
        action = self.SEGMENT_ACTIONS.get(segment, {})
        return action.get("urgency", "medium")

    def recommend_products(
        self,
        segment: RFMSegment,
        available_products: list[dict[str, Any]],
        purchase_history: list[dict[str, Any]] | None = None,
        limit: int = 5,
    ) -> list[ProductRecommendation]:
        """
        Recommend products for a segment.

        Products should have: id, name, category, price, tags
        Purchase history should have: product_id, quantity, date
        """
        strategy = self.get_product_strategy_for_segment(segment)
        recommendations = []

        for product in available_products[:limit]:
            score = self._calculate_product_score(
                product,
                strategy,
                segment,
                purchase_history,
            )
            if score > 0:
                recommendations.append(
                    ProductRecommendation(
                        segment=segment.value,
                        product_id=product["id"],
                        product_name=product["name"],
                        product_category=product.get("category", ""),
                        score=score,
                        reason=self._get_recommendation_reason(strategy, segment),
                    )
                )

        # Sort by score descending
        recommendations.sort(key=lambda x: x.score, reverse=True)
        return recommendations[:limit]

    def _calculate_product_score(
        self,
        product: dict[str, Any],
        strategy: str,
        segment: RFMSegment,
        purchase_history: list[dict[str, Any]] | None,
    ) -> float:
        """Calculate recommendation score for a product."""
        base_score = 1.0

        # Strategy-based scoring
        if strategy == "premium":
            # Higher price = higher score for premium strategy
            price = product.get("price", 0)
            if price > 500_000_000:  # 500M+
                base_score *= 2.0
            elif price > 100_000_000:  # 100M+
                base_score *= 1.5
        elif strategy == "entry_level":
            # Lower price = higher score
            price = product.get("price", 0)
            if price < 50_000_000:  # < 50M
                base_score *= 2.0
            elif price < 100_000_000:  # < 100M
                base_score *= 1.5
        elif strategy == "previously_purchased":
            # Boost if in purchase history
            if purchase_history:
                product_id = str(product.get("id"))
                for purchase in purchase_history:
                    if str(purchase.get("product_id")) == product_id:
                        base_score *= 2.5
                        break

        # Segment tag matching
        product_tags = product.get("tags", [])
        recommended_segments = product.get("recommended_segments", [])
        if segment.value in recommended_segments:
            base_score *= 1.5

        return base_score

    def _get_recommendation_reason(
        self,
        strategy: str,
        segment: RFMSegment,
    ) -> str:
        """Get human-readable reason for recommendation."""
        reasons = {
            "premium": "محصول ممتاز برای مشتریان VIP",
            "upsell": "ارتقاء از محصولات قبلی",
            "cross_sell": "مکمل خریدهای قبلی",
            "entry_level": "مناسب برای شروع",
            "popular": "پرفروش‌ترین محصولات",
            "best_sellers": "محصولات محبوب",
            "previously_purchased": "بر اساس خریدهای قبلی",
            "high_margin": "پیشنهاد ویژه",
            "clearance": "تخفیف ویژه",
            "none": "",
        }
        return reasons.get(strategy, "پیشنهاد شده")

