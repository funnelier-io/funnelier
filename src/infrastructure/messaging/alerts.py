"""
Alerts and Notifications Module

Provides alert rules, threshold monitoring, and notification delivery.
"""

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4
from enum import Enum
from dataclasses import dataclass, field


class AlertSeverity(Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AlertType(Enum):
    """Types of alerts."""
    CONVERSION_DROP = "conversion_drop"
    DELIVERY_RATE_LOW = "delivery_rate_low"
    CALL_ANSWER_RATE_LOW = "call_answer_rate_low"
    REVENUE_TARGET_MISS = "revenue_target_miss"
    SEGMENT_MIGRATION = "segment_migration"
    HIGH_VALUE_CUSTOMER_AT_RISK = "high_value_customer_at_risk"
    QUOTA_WARNING = "quota_warning"
    SYSTEM_ERROR = "system_error"
    CUSTOM = "custom"


class NotificationChannel(Enum):
    """Notification delivery channels."""
    EMAIL = "email"
    SMS = "sms"
    WEBHOOK = "webhook"
    DASHBOARD = "dashboard"
    TELEGRAM = "telegram"


@dataclass
class AlertRule:
    """Alert rule configuration."""
    id: UUID = field(default_factory=uuid4)
    tenant_id: UUID | None = None
    name: str = ""
    description: str | None = None
    alert_type: AlertType = AlertType.CUSTOM
    is_active: bool = True

    # Conditions
    metric: str = ""  # e.g., "conversion_rate", "delivery_rate"
    operator: str = "lt"  # lt, gt, eq, lte, gte
    threshold: float = 0.0
    comparison_period: str = "day"  # day, week, month

    # Notification settings
    severity: AlertSeverity = AlertSeverity.WARNING
    channels: list[NotificationChannel] = field(default_factory=list)
    recipients: list[str] = field(default_factory=list)
    cooldown_minutes: int = 60  # Minimum time between same alerts

    # Metadata
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime | None = None
    last_triggered_at: datetime | None = None


@dataclass
class Alert:
    """Generated alert instance."""
    id: UUID = field(default_factory=uuid4)
    tenant_id: UUID | None = None
    rule_id: UUID | None = None
    alert_type: AlertType = AlertType.CUSTOM
    severity: AlertSeverity = AlertSeverity.WARNING

    title: str = ""
    message: str = ""
    details: dict[str, Any] = field(default_factory=dict)

    # Status
    is_read: bool = False
    is_resolved: bool = False
    resolved_at: datetime | None = None
    resolved_by: UUID | None = None

    # Timing
    triggered_at: datetime = field(default_factory=datetime.utcnow)
    acknowledged_at: datetime | None = None


class AlertRuleEvaluator:
    """Evaluates alert rules against current metrics."""

    def __init__(self, metrics_provider: Any = None):
        self._metrics_provider = metrics_provider

    def evaluate(
        self,
        rule: AlertRule,
        current_value: float,
        previous_value: float | None = None,
    ) -> Alert | None:
        """
        Evaluate a rule and generate an alert if conditions are met.
        """
        should_alert = False

        # Compare current value against threshold
        if rule.operator == "lt":
            should_alert = current_value < rule.threshold
        elif rule.operator == "gt":
            should_alert = current_value > rule.threshold
        elif rule.operator == "eq":
            should_alert = current_value == rule.threshold
        elif rule.operator == "lte":
            should_alert = current_value <= rule.threshold
        elif rule.operator == "gte":
            should_alert = current_value >= rule.threshold
        elif rule.operator == "drop" and previous_value is not None:
            # Check for percentage drop
            if previous_value > 0:
                drop_percent = ((previous_value - current_value) / previous_value) * 100
                should_alert = drop_percent >= rule.threshold

        if not should_alert:
            return None

        # Check cooldown
        if rule.last_triggered_at:
            cooldown_elapsed = (datetime.utcnow() - rule.last_triggered_at).total_seconds() / 60
            if cooldown_elapsed < rule.cooldown_minutes:
                return None

        # Generate alert
        alert = Alert(
            tenant_id=rule.tenant_id,
            rule_id=rule.id,
            alert_type=rule.alert_type,
            severity=rule.severity,
            title=self._generate_title(rule, current_value),
            message=self._generate_message(rule, current_value, previous_value),
            details={
                "metric": rule.metric,
                "threshold": rule.threshold,
                "current_value": current_value,
                "previous_value": previous_value,
                "operator": rule.operator,
            },
        )

        return alert

    def _generate_title(self, rule: AlertRule, current_value: float) -> str:
        """Generate alert title."""
        titles = {
            AlertType.CONVERSION_DROP: "کاهش نرخ تبدیل",
            AlertType.DELIVERY_RATE_LOW: "نرخ تحویل پیامک پایین",
            AlertType.CALL_ANSWER_RATE_LOW: "نرخ پاسخگویی تماس پایین",
            AlertType.REVENUE_TARGET_MISS: "عدم دستیابی به هدف درآمد",
            AlertType.SEGMENT_MIGRATION: "مهاجرت مشتریان به بخش در خطر",
            AlertType.HIGH_VALUE_CUSTOMER_AT_RISK: "مشتری با ارزش در خطر ریزش",
            AlertType.QUOTA_WARNING: "هشدار سقف استفاده",
            AlertType.SYSTEM_ERROR: "خطای سیستمی",
        }
        return titles.get(rule.alert_type, rule.name)

    def _generate_message(
        self,
        rule: AlertRule,
        current_value: float,
        previous_value: float | None,
    ) -> str:
        """Generate alert message."""
        messages = {
            AlertType.CONVERSION_DROP: f"نرخ تبدیل به {current_value:.1%} کاهش یافته است (آستانه: {rule.threshold:.1%})",
            AlertType.DELIVERY_RATE_LOW: f"نرخ تحویل پیامک {current_value:.1%} است که کمتر از حد مجاز {rule.threshold:.1%} می‌باشد",
            AlertType.CALL_ANSWER_RATE_LOW: f"نرخ پاسخگویی تماس {current_value:.1%} است",
            AlertType.REVENUE_TARGET_MISS: f"درآمد فعلی {current_value:,.0f} ریال از هدف {rule.threshold:,.0f} ریال کمتر است",
            AlertType.HIGH_VALUE_CUSTOMER_AT_RISK: "یک مشتری با ارزش بالا به بخش 'در خطر' منتقل شده است",
        }

        if rule.alert_type in messages:
            return messages[rule.alert_type]

        return f"{rule.metric}: مقدار فعلی {current_value} (آستانه: {rule.threshold})"


class NotificationService:
    """Service for delivering notifications."""

    def __init__(
        self,
        email_sender: Any = None,
        sms_sender: Any = None,
        webhook_client: Any = None,
    ):
        self._email_sender = email_sender
        self._sms_sender = sms_sender
        self._webhook_client = webhook_client

    async def send_alert(
        self,
        alert: Alert,
        channels: list[NotificationChannel],
        recipients: list[str],
    ) -> dict[str, bool]:
        """
        Send alert via specified channels.
        Returns dict of channel -> success status.
        """
        results = {}

        for channel in channels:
            try:
                if channel == NotificationChannel.EMAIL:
                    success = await self._send_email(alert, recipients)
                elif channel == NotificationChannel.SMS:
                    success = await self._send_sms(alert, recipients)
                elif channel == NotificationChannel.WEBHOOK:
                    success = await self._send_webhook(alert, recipients)
                elif channel == NotificationChannel.DASHBOARD:
                    success = True  # Dashboard alerts are always stored
                else:
                    success = False

                results[channel.value] = success
            except Exception as e:
                results[channel.value] = False
                print(f"Failed to send alert via {channel.value}: {e}")

        return results

    async def _send_email(self, alert: Alert, recipients: list[str]) -> bool:
        """Send alert via email."""
        if not self._email_sender:
            return False

        subject = f"[{alert.severity.value.upper()}] {alert.title}"
        body = f"""
        {alert.message}

        جزئیات:
        - نوع: {alert.alert_type.value}
        - زمان: {alert.triggered_at.strftime('%Y-%m-%d %H:%M:%S')}

        برای مشاهده جزئیات بیشتر به داشبورد مراجعه کنید.
        """

        # Send email implementation
        return True

    async def _send_sms(self, alert: Alert, recipients: list[str]) -> bool:
        """Send alert via SMS."""
        if not self._sms_sender:
            return False

        message = f"[{alert.severity.value}] {alert.title}: {alert.message}"

        # Truncate if too long
        if len(message) > 140:
            message = message[:137] + "..."

        # Send SMS implementation
        return True

    async def _send_webhook(self, alert: Alert, endpoints: list[str]) -> bool:
        """Send alert via webhook."""
        if not self._webhook_client:
            return False

        payload = {
            "alert_id": str(alert.id),
            "type": alert.alert_type.value,
            "severity": alert.severity.value,
            "title": alert.title,
            "message": alert.message,
            "details": alert.details,
            "triggered_at": alert.triggered_at.isoformat(),
        }

        # Send webhook implementation
        return True


# Default alert rules for new tenants
DEFAULT_ALERT_RULES = [
    AlertRule(
        name="کاهش نرخ تبدیل",
        alert_type=AlertType.CONVERSION_DROP,
        metric="conversion_rate",
        operator="drop",
        threshold=20.0,  # 20% drop
        comparison_period="week",
        severity=AlertSeverity.WARNING,
        channels=[NotificationChannel.DASHBOARD, NotificationChannel.EMAIL],
    ),
    AlertRule(
        name="نرخ تحویل پیامک پایین",
        alert_type=AlertType.DELIVERY_RATE_LOW,
        metric="sms_delivery_rate",
        operator="lt",
        threshold=0.85,  # 85%
        comparison_period="day",
        severity=AlertSeverity.WARNING,
        channels=[NotificationChannel.DASHBOARD],
    ),
    AlertRule(
        name="نرخ پاسخگویی تماس پایین",
        alert_type=AlertType.CALL_ANSWER_RATE_LOW,
        metric="call_answer_rate",
        operator="lt",
        threshold=0.30,  # 30%
        comparison_period="day",
        severity=AlertSeverity.INFO,
        channels=[NotificationChannel.DASHBOARD],
    ),
    AlertRule(
        name="مشتری با ارزش در خطر",
        alert_type=AlertType.HIGH_VALUE_CUSTOMER_AT_RISK,
        metric="high_value_at_risk_count",
        operator="gt",
        threshold=0,  # Any high-value customer at risk
        comparison_period="day",
        severity=AlertSeverity.CRITICAL,
        channels=[NotificationChannel.DASHBOARD, NotificationChannel.EMAIL, NotificationChannel.SMS],
    ),
]

