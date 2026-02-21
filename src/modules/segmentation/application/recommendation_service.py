"""
Product Recommendation Service

Provides product recommendations based on customer segments,
purchase history, and product catalog.
"""

from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from src.core.domain import RFMSegment

from ..domain import (
    ContactRFMProfile,
    SEGMENT_RECOMMENDATIONS,
    SegmentRecommendationService,
)


class ProductRecommendationService:
    """
    Service for generating product recommendations.
    """

    def __init__(
        self,
        product_repository: Any,
        purchase_history_repository: Any,
        rfm_profile_repository: Any,
    ):
        self._product_repo = product_repository
        self._purchase_repo = purchase_history_repository
        self._rfm_profile_repo = rfm_profile_repository
        self._segment_service = SegmentRecommendationService()

    async def get_recommendations_for_contact(
        self,
        tenant_id: UUID,
        contact_id: UUID,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        """
        Get personalized product recommendations for a contact.
        """
        # Get RFM profile
        profile = await self._rfm_profile_repo.get_by_contact(contact_id)
        if not profile or not profile.segment:
            # Default to general recommendations
            return await self._get_general_recommendations(tenant_id, limit)

        # Get segment-based recommendations
        segment_rec = self._segment_service.get_recommendation(profile.segment)
        recommended_categories = segment_rec.recommended_products

        # Get purchase history
        purchase_history = await self._purchase_repo.get_by_contact(contact_id)

        # Determine recommendation strategy
        if profile.segment in [RFMSegment.CHAMPIONS, RFMSegment.LOYAL]:
            # Upsell and cross-sell
            return await self._get_upsell_recommendations(
                tenant_id=tenant_id,
                purchase_history=purchase_history,
                categories=recommended_categories,
                limit=limit,
            )
        elif profile.segment in [RFMSegment.NEW_CUSTOMERS, RFMSegment.PROMISING]:
            # Entry-level and popular products
            return await self._get_entry_level_recommendations(
                tenant_id=tenant_id,
                categories=recommended_categories,
                limit=limit,
            )
        elif profile.segment in [
            RFMSegment.AT_RISK,
            RFMSegment.CANT_LOSE,
            RFMSegment.ABOUT_TO_SLEEP,
        ]:
            # Win-back with special offers
            return await self._get_winback_recommendations(
                tenant_id=tenant_id,
                purchase_history=purchase_history,
                categories=recommended_categories,
                max_discount=segment_rec.max_discount_percent,
                limit=limit,
            )
        else:
            # Standard recommendations
            return await self._get_category_recommendations(
                tenant_id=tenant_id,
                categories=recommended_categories,
                limit=limit,
            )

    async def _get_general_recommendations(
        self,
        tenant_id: UUID,
        limit: int,
    ) -> list[dict[str, Any]]:
        """
        Get general product recommendations (bestsellers).
        """
        products = await self._product_repo.get_bestsellers(
            tenant_id=tenant_id,
            limit=limit,
        )

        return [
            {
                "product_id": str(p["id"]),
                "name": p["name"],
                "category": p["category"],
                "price": p["price"],
                "recommendation_reason": "محصول پرفروش",
                "discount_percent": 0,
            }
            for p in products
        ]

    async def _get_upsell_recommendations(
        self,
        tenant_id: UUID,
        purchase_history: list[dict[str, Any]],
        categories: list[str],
        limit: int,
    ) -> list[dict[str, Any]]:
        """
        Get upsell recommendations for loyal customers.
        """
        # Get products from purchased categories but higher tier
        purchased_categories = set()
        max_prices = {}

        for purchase in purchase_history:
            cat = purchase.get("product_category")
            price = purchase.get("price", 0)
            if cat:
                purchased_categories.add(cat)
                max_prices[cat] = max(max_prices.get(cat, 0), price)

        recommendations = []

        # Get premium versions of purchased categories
        for cat in purchased_categories:
            if len(recommendations) >= limit:
                break

            products = await self._product_repo.get_by_category(
                tenant_id=tenant_id,
                category=cat,
                min_price=max_prices[cat],
                limit=2,
            )

            for p in products:
                if len(recommendations) >= limit:
                    break
                recommendations.append({
                    "product_id": str(p["id"]),
                    "name": p["name"],
                    "category": p["category"],
                    "price": p["price"],
                    "recommendation_reason": "ارتقا به نسخه بهتر",
                    "discount_percent": 0,
                })

        # Add complementary products
        if len(recommendations) < limit:
            complementary = await self._product_repo.get_complementary(
                tenant_id=tenant_id,
                categories=list(purchased_categories),
                limit=limit - len(recommendations),
            )

            for p in complementary:
                recommendations.append({
                    "product_id": str(p["id"]),
                    "name": p["name"],
                    "category": p["category"],
                    "price": p["price"],
                    "recommendation_reason": "محصول مکمل",
                    "discount_percent": 0,
                })

        return recommendations

    async def _get_entry_level_recommendations(
        self,
        tenant_id: UUID,
        categories: list[str],
        limit: int,
    ) -> list[dict[str, Any]]:
        """
        Get entry-level recommendations for new customers.
        """
        recommendations = []

        # Get entry-level products from recommended categories
        for cat in categories:
            if len(recommendations) >= limit:
                break

            products = await self._product_repo.get_entry_level(
                tenant_id=tenant_id,
                category=cat,
                limit=2,
            )

            for p in products:
                if len(recommendations) >= limit:
                    break
                recommendations.append({
                    "product_id": str(p["id"]),
                    "name": p["name"],
                    "category": p["category"],
                    "price": p["price"],
                    "recommendation_reason": "محصول پیشنهادی برای شروع",
                    "discount_percent": 10,  # Welcome discount
                })

        # Fill with popular products if needed
        if len(recommendations) < limit:
            popular = await self._product_repo.get_popular(
                tenant_id=tenant_id,
                limit=limit - len(recommendations),
            )

            for p in popular:
                recommendations.append({
                    "product_id": str(p["id"]),
                    "name": p["name"],
                    "category": p["category"],
                    "price": p["price"],
                    "recommendation_reason": "محصول محبوب",
                    "discount_percent": 5,
                })

        return recommendations

    async def _get_winback_recommendations(
        self,
        tenant_id: UUID,
        purchase_history: list[dict[str, Any]],
        categories: list[str],
        max_discount: int,
        limit: int,
    ) -> list[dict[str, Any]]:
        """
        Get win-back recommendations for at-risk customers.
        """
        recommendations = []

        # Get previously purchased products (re-purchase opportunity)
        purchased_products = set()
        for purchase in purchase_history:
            pid = purchase.get("product_id")
            if pid:
                purchased_products.add(pid)

        # Offer previously purchased products with discount
        for pid in list(purchased_products)[:2]:
            product = await self._product_repo.get(pid)
            if product:
                recommendations.append({
                    "product_id": str(product["id"]),
                    "name": product["name"],
                    "category": product["category"],
                    "price": product["price"],
                    "recommendation_reason": "سفارش مجدد با تخفیف ویژه",
                    "discount_percent": max_discount,
                })

        # Add bestsellers with discount
        if len(recommendations) < limit:
            bestsellers = await self._product_repo.get_bestsellers(
                tenant_id=tenant_id,
                limit=limit - len(recommendations),
            )

            for p in bestsellers:
                if str(p["id"]) not in purchased_products:
                    recommendations.append({
                        "product_id": str(p["id"]),
                        "name": p["name"],
                        "category": p["category"],
                        "price": p["price"],
                        "recommendation_reason": "پیشنهاد ویژه بازگشت",
                        "discount_percent": max_discount - 5,
                    })

        return recommendations

    async def _get_category_recommendations(
        self,
        tenant_id: UUID,
        categories: list[str],
        limit: int,
    ) -> list[dict[str, Any]]:
        """
        Get standard category-based recommendations.
        """
        recommendations = []

        for cat in categories:
            if len(recommendations) >= limit:
                break

            products = await self._product_repo.get_by_category(
                tenant_id=tenant_id,
                category=cat,
                limit=2,
            )

            for p in products:
                if len(recommendations) >= limit:
                    break
                recommendations.append({
                    "product_id": str(p["id"]),
                    "name": p["name"],
                    "category": p["category"],
                    "price": p["price"],
                    "recommendation_reason": f"پیشنهاد از دسته {cat}",
                    "discount_percent": 0,
                })

        return recommendations

    async def get_segment_product_strategy(
        self,
        segment: RFMSegment,
    ) -> dict[str, Any]:
        """
        Get product strategy for a segment.
        """
        rec = SEGMENT_RECOMMENDATIONS.get(segment)
        if not rec:
            return {}

        return {
            "segment": segment.value,
            "segment_name_fa": rec.segment_name_fa,
            "recommended_product_types": rec.recommended_products,
            "discount_allowed": rec.discount_allowed,
            "max_discount_percent": rec.max_discount_percent,
            "strategy_description": self._get_strategy_description(segment),
        }

    def _get_strategy_description(self, segment: RFMSegment) -> str:
        """
        Get strategy description for segment.
        """
        strategies = {
            RFMSegment.CHAMPIONS: "ارائه محصولات پریمیوم و جدید، بدون نیاز به تخفیف",
            RFMSegment.LOYAL: "فرصت‌های آپسل و کراس‌سل با محصولات مکمل",
            RFMSegment.POTENTIAL_LOYALIST: "معرفی محصولات محبوب با تخفیف‌های تشویقی",
            RFMSegment.NEW_CUSTOMERS: "محصولات entry-level با تخفیف خوش‌آمدگویی",
            RFMSegment.PROMISING: "محصولات با قیمت مناسب و تخفیف متوسط",
            RFMSegment.NEED_ATTENTION: "پرفروش‌ترین‌ها با تخفیف ویژه",
            RFMSegment.ABOUT_TO_SLEEP: "پیشنهادات فوری با تخفیف بالا",
            RFMSegment.AT_RISK: "محصولات قبلاً خریداری‌شده با تخفیف بازگشت",
            RFMSegment.CANT_LOSE: "پیشنهاد VIP با بالاترین تخفیف",
            RFMSegment.HIBERNATING: "محصولات با تخفیف ویژه بازفعال‌سازی",
            RFMSegment.LOST: "آخرین فرصت با حداکثر تخفیف",
        }

        return strategies.get(segment, "استراتژی استاندارد")

    async def get_cross_sell_opportunities(
        self,
        tenant_id: UUID,
    ) -> list[dict[str, Any]]:
        """
        Identify cross-sell opportunities across segments.
        """
        opportunities = []

        # Get segment distribution
        profiles = await self._rfm_profile_repo.get_all_by_tenant(tenant_id)

        # Group by purchased categories
        segment_categories: dict[RFMSegment, set] = {}

        for profile in profiles:
            if not profile.segment:
                continue

            # Get purchase categories for this contact
            purchases = await self._purchase_repo.get_by_contact(profile.contact_id)
            categories = set(p.get("product_category") for p in purchases if p.get("product_category"))

            if profile.segment not in segment_categories:
                segment_categories[profile.segment] = set()
            segment_categories[profile.segment].update(categories)

        # Find cross-sell opportunities
        for segment, categories in segment_categories.items():
            rec = SEGMENT_RECOMMENDATIONS.get(segment)
            if not rec:
                continue

            for rec_cat in rec.recommended_products:
                if rec_cat not in categories:
                    opportunities.append({
                        "segment": segment.value,
                        "segment_name_fa": rec.segment_name_fa,
                        "current_categories": list(categories),
                        "recommended_category": rec_cat,
                        "opportunity_type": "cross_sell",
                        "priority": segment.priority if hasattr(segment, 'priority') else 0,
                    })

        # Sort by priority
        opportunities.sort(key=lambda x: x["priority"], reverse=True)

        return opportunities[:20]

