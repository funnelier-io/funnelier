"""
Segmentation Module - Domain Entities
RFM Analysis and Customer Segmentation
"""

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from src.core.domain import TenantEntity, RFMSegment


class RFMScore(BaseModel):
    """
    RFM Score for a contact.
    Each component is scored 1-5 (configurable).
    """

    recency: int  # 1-5, based on days since last purchase
    frequency: int  # 1-5, based on number of purchases
    monetary: int  # 1-5, based on total spend

    @property
    def total_score(self) -> int:
        """Sum of R, F, M scores."""
        return self.recency + self.frequency + self.monetary

    @property
    def rfm_string(self) -> str:
        """RFM as string like '555', '421', etc."""
        return f"{self.recency}{self.frequency}{self.monetary}"

    @property
    def segment_score(self) -> float:
        """Weighted score for segment comparison."""
        # Recency is typically most important
        return self.recency * 0.4 + self.frequency * 0.3 + self.monetary * 0.3

    def get_segment(self) -> RFMSegment:
        """Determine segment from RFM score."""
        return RFMSegment.from_rfm_score(self.recency, self.frequency, self.monetary)


class ContactRFMProfile(TenantEntity[UUID]):
    """
    RFM profile for a contact.
    """

    id: UUID = Field(default_factory=uuid4)
    contact_id: UUID
    phone_number: str

    # Raw metrics
    last_purchase_date: datetime | None = None
    days_since_last_purchase: int | None = None
    purchase_count: int = 0
    total_spend: float = 0.0
    average_order_value: float = 0.0

    # RFM Scores (1-5)
    rfm_score: RFMScore | None = None

    # Segment
    segment: RFMSegment | None = None

    # Historical RFM (for trend analysis)
    rfm_history: list[dict[str, Any]] = Field(default_factory=list)
    # Each entry: {date, rfm_string, segment}

    # Calculated fields
    customer_lifetime_value: float = 0.0
    predicted_next_purchase_date: datetime | None = None

    # Engagement metrics (for RFM extension)
    sms_response_rate: float = 0.0
    call_answer_rate: float = 0.0
    engagement_score: int = 0  # 1-5

    def update_rfm(
        self,
        score: RFMScore,
        segment: RFMSegment,
    ) -> None:
        """Update RFM score and track history."""
        now = datetime.utcnow()

        # Track previous score if exists
        if self.rfm_score:
            self.rfm_history.append({
                "date": now.isoformat(),
                "rfm_string": self.rfm_score.rfm_string,
                "segment": self.segment.value if self.segment else None,
            })
            # Keep last 12 entries
            if len(self.rfm_history) > 12:
                self.rfm_history = self.rfm_history[-12:]

        self.rfm_score = score
        self.segment = segment
        self.updated_at = now


class RFMConfig(TenantEntity[UUID]):
    """
    RFM calculation configuration per tenant.
    """

    id: UUID = Field(default_factory=uuid4)

    # Recency thresholds (days)
    recency_thresholds: list[int] = Field(
        default=[14, 30, 60, 90]  # 5=0-14, 4=15-30, 3=31-60, 2=61-90, 1=90+
    )

    # Frequency thresholds (number of purchases)
    frequency_thresholds: list[int] = Field(
        default=[1, 2, 4, 8]  # 5=8+, 4=4-7, 3=2-3, 2=1, 1=0
    )

    # Monetary thresholds (in Rials)
    monetary_thresholds: list[float] = Field(
        default=[100_000_000, 500_000_000, 1_000_000_000, 2_000_000_000]
    )

    # Analysis period (months)
    analysis_period_months: int = 12

    # High value threshold
    high_value_threshold: float = 1_000_000_000  # 1B Rial

    # Recent period (for recency calculation)
    recent_days: int = 14

    def calculate_recency_score(self, days: int | None) -> int:
        """Calculate recency score based on days since last purchase."""
        if days is None:
            return 1

        thresholds = sorted(self.recency_thresholds)
        for i, threshold in enumerate(thresholds):
            if days <= threshold:
                return 5 - i
        return 1

    def calculate_frequency_score(self, count: int) -> int:
        """Calculate frequency score based on purchase count."""
        thresholds = sorted(self.frequency_thresholds)
        # Score 5 for >= highest threshold, down to 2 for >= lowest, 1 for below all
        for i, threshold in enumerate(reversed(thresholds)):
            if count >= threshold:
                return len(thresholds) + 1 - i
        return 1

    def calculate_monetary_score(self, total: float) -> int:
        """Calculate monetary score based on total spend."""
        thresholds = sorted(self.monetary_thresholds)
        # Score 5 for >= highest threshold, down to 2 for >= lowest, 1 for below all
        for i, threshold in enumerate(reversed(thresholds)):
            if total >= threshold:
                return len(thresholds) + 1 - i
        return 1


class SegmentRecommendation(BaseModel):
    """
    Marketing recommendation for a segment.
    """

    segment: RFMSegment
    segment_name_fa: str  # Persian name
    description_fa: str  # Persian description

    # Recommended actions
    recommended_message_types: list[str]  # promotional, retention, etc.
    recommended_products: list[str]  # Product category suggestions
    contact_frequency: str  # high, medium, low
    channel_priority: list[str]  # ["sms", "call", "email"]

    # Template suggestions
    suggested_templates: list[str] = Field(default_factory=list)

    # Discount strategy
    discount_allowed: bool = False
    max_discount_percent: int = 0


# Default segment recommendations
SEGMENT_RECOMMENDATIONS: dict[RFMSegment, SegmentRecommendation] = {
    RFMSegment.CHAMPIONS: SegmentRecommendation(
        segment=RFMSegment.CHAMPIONS,
        segment_name_fa="قهرمانان",
        description_fa="بهترین مشتریان - خرید اخیر و مکرر با ارزش بالا",
        recommended_message_types=["exclusive", "new_product", "vip"],
        recommended_products=["premium", "new_arrivals"],
        contact_frequency="high",
        channel_priority=["sms", "call"],
        discount_allowed=False,
        max_discount_percent=0,
    ),
    RFMSegment.LOYAL: SegmentRecommendation(
        segment=RFMSegment.LOYAL,
        segment_name_fa="وفادار",
        description_fa="مشتریان وفادار با خرید مکرر",
        recommended_message_types=["loyalty", "referral", "upsell"],
        recommended_products=["complementary", "upgrades"],
        contact_frequency="high",
        channel_priority=["sms", "call"],
        discount_allowed=True,
        max_discount_percent=5,
    ),
    RFMSegment.POTENTIAL_LOYALIST: SegmentRecommendation(
        segment=RFMSegment.POTENTIAL_LOYALIST,
        segment_name_fa="وفادار بالقوه",
        description_fa="مشتریان اخیر با پتانسیل تبدیل به وفادار",
        recommended_message_types=["engagement", "product_info", "incentive"],
        recommended_products=["popular", "value"],
        contact_frequency="medium",
        channel_priority=["sms", "call"],
        discount_allowed=True,
        max_discount_percent=10,
    ),
    RFMSegment.NEW_CUSTOMERS: SegmentRecommendation(
        segment=RFMSegment.NEW_CUSTOMERS,
        segment_name_fa="مشتریان جدید",
        description_fa="خریداران جدید - نیاز به onboarding",
        recommended_message_types=["welcome", "how_to", "support"],
        recommended_products=["entry_level", "popular"],
        contact_frequency="high",
        channel_priority=["sms", "call"],
        discount_allowed=True,
        max_discount_percent=15,
    ),
    RFMSegment.PROMISING: SegmentRecommendation(
        segment=RFMSegment.PROMISING,
        segment_name_fa="امیدوارکننده",
        description_fa="مشتریان اخیر با پتانسیل رشد",
        recommended_message_types=["promotional", "product_info"],
        recommended_products=["value", "popular"],
        contact_frequency="medium",
        channel_priority=["sms"],
        discount_allowed=True,
        max_discount_percent=10,
    ),
    RFMSegment.NEED_ATTENTION: SegmentRecommendation(
        segment=RFMSegment.NEED_ATTENTION,
        segment_name_fa="نیازمند توجه",
        description_fa="مشتریانی که قبلاً فعال بودند ولی کم شده‌اند",
        recommended_message_types=["reactivation", "special_offer"],
        recommended_products=["bestsellers", "discounted"],
        contact_frequency="medium",
        channel_priority=["sms", "call"],
        discount_allowed=True,
        max_discount_percent=15,
    ),
    RFMSegment.ABOUT_TO_SLEEP: SegmentRecommendation(
        segment=RFMSegment.ABOUT_TO_SLEEP,
        segment_name_fa="در آستانه خواب",
        description_fa="مشتریانی که در حال از دست رفتن هستند",
        recommended_message_types=["urgency", "limited_offer"],
        recommended_products=["discounted", "clearance"],
        contact_frequency="low",
        channel_priority=["sms"],
        discount_allowed=True,
        max_discount_percent=20,
    ),
    RFMSegment.AT_RISK: SegmentRecommendation(
        segment=RFMSegment.AT_RISK,
        segment_name_fa="در خطر",
        description_fa="مشتریان قبلاً خوب که دارند از دست می‌روند",
        recommended_message_types=["win_back", "personal_offer"],
        recommended_products=["premium", "bestsellers"],
        contact_frequency="high",
        channel_priority=["call", "sms"],
        discount_allowed=True,
        max_discount_percent=20,
    ),
    RFMSegment.CANT_LOSE: SegmentRecommendation(
        segment=RFMSegment.CANT_LOSE,
        segment_name_fa="نباید از دست برود",
        description_fa="مشتریان با ارزش بالا که دارند می‌روند - فوری",
        recommended_message_types=["urgent_win_back", "vip_offer", "personal_call"],
        recommended_products=["premium", "exclusive"],
        contact_frequency="high",
        channel_priority=["call", "sms"],
        discount_allowed=True,
        max_discount_percent=25,
    ),
    RFMSegment.HIBERNATING: SegmentRecommendation(
        segment=RFMSegment.HIBERNATING,
        segment_name_fa="خواب",
        description_fa="مشتریان غیرفعال",
        recommended_message_types=["reactivation", "survey"],
        recommended_products=["clearance", "value"],
        contact_frequency="low",
        channel_priority=["sms"],
        discount_allowed=True,
        max_discount_percent=25,
    ),
    RFMSegment.LOST: SegmentRecommendation(
        segment=RFMSegment.LOST,
        segment_name_fa="از دست رفته",
        description_fa="مشتریانی که مدت زیادی غیرفعال بوده‌اند",
        recommended_message_types=["last_chance", "survey"],
        recommended_products=["clearance"],
        contact_frequency="low",
        channel_priority=["sms"],
        discount_allowed=True,
        max_discount_percent=30,
    ),
}


class SegmentSummary(BaseModel):
    """
    Summary statistics for a segment.
    """

    segment: RFMSegment
    contact_count: int = 0
    percentage_of_total: float = 0.0
    total_revenue: float = 0.0
    average_order_value: float = 0.0
    average_frequency: float = 0.0
    average_recency_days: float = 0.0


class RFMAnalysisResult(BaseModel):
    """
    Complete RFM analysis result.
    """

    tenant_id: UUID
    analysis_date: datetime
    period_months: int

    # Overall stats
    total_contacts_analyzed: int = 0
    contacts_with_purchases: int = 0

    # Segment distribution
    segment_summaries: list[SegmentSummary] = Field(default_factory=list)

    # Top metrics
    total_revenue: float = 0.0
    average_clv: float = 0.0

    # Trends
    segment_changes: dict[str, int] = Field(default_factory=dict)
    # e.g., {"champions_growth": 5, "lost_decrease": -10}

