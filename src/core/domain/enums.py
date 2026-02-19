"""
Core Domain - Enumerations
Shared enums used across bounded contexts
"""

from enum import Enum


class FunnelStage(str, Enum):
    """
    Standard funnel stages.
    Can be extended per tenant.
    """

    LEAD_ACQUIRED = "lead_acquired"
    SMS_SENT = "sms_sent"
    SMS_DELIVERED = "sms_delivered"
    CALL_ATTEMPTED = "call_attempted"
    CALL_ANSWERED = "call_answered"  # >= 90 seconds
    INVOICE_ISSUED = "invoice_issued"
    PAYMENT_RECEIVED = "payment_received"

    @classmethod
    def get_order(cls) -> list["FunnelStage"]:
        """Get stages in funnel order."""
        return [
            cls.LEAD_ACQUIRED,
            cls.SMS_SENT,
            cls.SMS_DELIVERED,
            cls.CALL_ATTEMPTED,
            cls.CALL_ANSWERED,
            cls.INVOICE_ISSUED,
            cls.PAYMENT_RECEIVED,
        ]

    @property
    def stage_number(self) -> int:
        """Get the numeric position of this stage."""
        return self.get_order().index(self) + 1


class CallType(str, Enum):
    """Types of phone calls."""

    INCOMING = "incoming"
    OUTGOING = "outgoing"
    MISSED = "missed"


class CallSource(str, Enum):
    """Source of call logs."""

    MOBILE = "mobile"
    VOIP = "voip"


class SMSStatus(str, Enum):
    """SMS delivery status."""

    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    BLOCKED = "blocked"
    UNKNOWN = "unknown"


class SMSDirection(str, Enum):
    """SMS direction."""

    OUTBOUND = "outbound"
    INBOUND = "inbound"


class InvoiceStatus(str, Enum):
    """Invoice status."""

    DRAFT = "draft"
    ISSUED = "issued"
    PARTIAL_PAID = "partial_paid"
    PAID = "paid"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class PaymentStatus(str, Enum):
    """Payment status."""

    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"


class RFMSegment(str, Enum):
    """
    RFM Customer Segments.
    Based on RFM score patterns.
    """

    CHAMPIONS = "champions"
    LOYAL = "loyal"
    POTENTIAL_LOYALIST = "potential_loyalist"
    NEW_CUSTOMERS = "new_customers"
    PROMISING = "promising"
    NEED_ATTENTION = "need_attention"
    ABOUT_TO_SLEEP = "about_to_sleep"
    AT_RISK = "at_risk"
    CANT_LOSE = "cant_lose"
    HIBERNATING = "hibernating"
    LOST = "lost"

    @classmethod
    def from_rfm_score(cls, r: int, f: int, m: int) -> "RFMSegment":
        """
        Determine segment from RFM scores (1-5 each).
        """
        score = r * 100 + f * 10 + m

        # Champions: Best in all dimensions
        if score >= 544:
            return cls.CHAMPIONS

        # Loyal: High frequency and monetary
        if f >= 4 and m >= 4:
            return cls.LOYAL

        # Potential Loyalist: Recent, moderate frequency
        if r >= 4 and f >= 2:
            return cls.POTENTIAL_LOYALIST

        # New Customers: Very recent, low frequency
        if r >= 4 and f == 1:
            return cls.NEW_CUSTOMERS

        # Promising: Moderate recency, low frequency
        if r >= 3 and f <= 2:
            return cls.PROMISING

        # Need Attention: Average across board
        if r == 3 and f == 3:
            return cls.NEED_ATTENTION

        # At Risk: High value but not recent
        if r <= 2 and (f >= 4 or m >= 4):
            return cls.AT_RISK

        # Can't Lose: Was high value, now at risk
        if r <= 2 and f >= 3 and m >= 3:
            return cls.CANT_LOSE

        # About to Sleep: Below average, slipping
        if r == 2 and f <= 3:
            return cls.ABOUT_TO_SLEEP

        # Hibernating: Low engagement
        if r == 1 and f <= 2:
            return cls.HIBERNATING

        # Lost: Lowest scores
        return cls.LOST

    @property
    def recommended_action(self) -> str:
        """Get recommended action for this segment."""
        actions = {
            self.CHAMPIONS: "Reward loyalty, exclusive offers, ask for referrals",
            self.LOYAL: "Upsell higher value products, loyalty programs",
            self.POTENTIAL_LOYALIST: "Engage more, offer membership benefits",
            self.NEW_CUSTOMERS: "Welcome sequence, onboarding, build relationship",
            self.PROMISING: "Create brand awareness, offer trials",
            self.NEED_ATTENTION: "Limited time offers, reactivate interest",
            self.ABOUT_TO_SLEEP: "Win-back campaigns, personalized offers",
            self.AT_RISK: "Urgent reactivation, personal outreach",
            self.CANT_LOSE: "Aggressive win-back, survey for feedback",
            self.HIBERNATING: "Cost-effective reactivation attempts",
            self.LOST: "Final win-back attempt or remove from active list",
        }
        return actions.get(self, "Review and analyze")

    @property
    def priority(self) -> int:
        """Get priority score (higher = more important to act on)."""
        priorities = {
            self.CHAMPIONS: 10,
            self.AT_RISK: 9,
            self.CANT_LOSE: 9,
            self.LOYAL: 8,
            self.POTENTIAL_LOYALIST: 7,
            self.NEW_CUSTOMERS: 6,
            self.NEED_ATTENTION: 5,
            self.ABOUT_TO_SLEEP: 4,
            self.PROMISING: 3,
            self.HIBERNATING: 2,
            self.LOST: 1,
        }
        return priorities.get(self, 0)


class LeadSource(str, Enum):
    """Source types for leads."""

    FILE_IMPORT = "file_import"
    API = "api"
    MANUAL = "manual"
    WEBSITE = "website"
    REFERRAL = "referral"
    EXHIBITION = "exhibition"
    SOCIAL_MEDIA = "social_media"


class CampaignStatus(str, Enum):
    """Campaign status."""

    DRAFT = "draft"
    SCHEDULED = "scheduled"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class AlertSeverity(str, Enum):
    """Alert severity levels."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AlertType(str, Enum):
    """Types of alerts."""

    CONVERSION_DROP = "conversion_drop"
    CONVERSION_SPIKE = "conversion_spike"
    SEGMENT_MIGRATION = "segment_migration"
    CAMPAIGN_PERFORMANCE = "campaign_performance"
    DATA_QUALITY = "data_quality"
    SYSTEM_ERROR = "system_error"
    THRESHOLD_BREACH = "threshold_breach"


class DataSourceType(str, Enum):
    """Types of data source connectors."""

    CSV_FILE = "csv_file"
    EXCEL_FILE = "excel_file"
    JSON_FILE = "json_file"
    MONGODB = "mongodb"
    POSTGRESQL = "postgresql"
    MYSQL = "mysql"
    REST_API = "rest_api"
    WEBHOOK = "webhook"


class ETLJobStatus(str, Enum):
    """ETL job execution status."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

