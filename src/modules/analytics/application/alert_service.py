"""
Alert Service

Monitors metrics and triggers alerts based on configured rules.
Supports notifications via SMS, email, and webhooks.
"""

from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

import httpx

from ..domain import AlertRule, AlertInstance


class AlertService:
    """
    Service for monitoring metrics and triggering alerts.
    """

    def __init__(
        self,
        alert_rule_repository: Any,
        alert_instance_repository: Any,
        sms_service: Any,
        email_service: Any,
    ):
        self._rule_repo = alert_rule_repository
        self._instance_repo = alert_instance_repository
        self._sms_service = sms_service
        self._email_service = email_service

    async def check_all_rules(
        self,
        tenant_id: UUID,
        metrics: dict[str, float],
    ) -> list[AlertInstance]:
        """
        Check all active alert rules against current metrics.
        """
        rules = await self._rule_repo.get_active_rules(tenant_id)
        triggered_alerts = []

        for rule in rules:
            if self._should_trigger(rule, metrics):
                alert = await self._trigger_alert(rule, metrics)
                triggered_alerts.append(alert)

        return triggered_alerts

    async def check_conversion_rate_alert(
        self,
        tenant_id: UUID,
        current_rate: float,
        threshold: float = 0.05,
    ) -> AlertInstance | None:
        """
        Check if conversion rate has dropped below threshold.
        """
        rule = AlertRule(
            tenant_id=tenant_id,
            name="Conversion Rate Alert",
            metric_name="conversion_rate",
            condition="below",
            threshold_value=threshold,
            severity="critical",
        )

        metrics = {"conversion_rate": current_rate}

        if self._should_trigger(rule, metrics):
            return await self._trigger_alert(rule, metrics)

        return None

    async def check_daily_leads_alert(
        self,
        tenant_id: UUID,
        today_leads: int,
        avg_leads: float,
        threshold_percent: float = -30.0,
    ) -> AlertInstance | None:
        """
        Check if daily leads have dropped significantly.
        """
        if avg_leads == 0:
            return None

        change_percent = ((today_leads - avg_leads) / avg_leads) * 100

        if change_percent <= threshold_percent:
            rule = AlertRule(
                tenant_id=tenant_id,
                name="Daily Leads Drop Alert",
                metric_name="daily_leads_change",
                condition="below",
                threshold_value=threshold_percent,
                severity="warning",
            )

            return await self._trigger_alert(
                rule,
                {
                    "daily_leads_change": change_percent,
                    "today_leads": today_leads,
                    "avg_leads": avg_leads,
                },
            )

        return None

    async def check_sms_delivery_alert(
        self,
        tenant_id: UUID,
        delivery_rate: float,
        threshold: float = 0.85,
    ) -> AlertInstance | None:
        """
        Check if SMS delivery rate has dropped.
        """
        if delivery_rate < threshold:
            rule = AlertRule(
                tenant_id=tenant_id,
                name="SMS Delivery Rate Alert",
                metric_name="sms_delivery_rate",
                condition="below",
                threshold_value=threshold,
                severity="warning",
            )

            return await self._trigger_alert(
                rule,
                {"sms_delivery_rate": delivery_rate},
            )

        return None

    async def check_call_answer_rate_alert(
        self,
        tenant_id: UUID,
        answer_rate: float,
        threshold: float = 0.25,
    ) -> AlertInstance | None:
        """
        Check if call answer rate is too low.
        """
        if answer_rate < threshold:
            rule = AlertRule(
                tenant_id=tenant_id,
                name="Call Answer Rate Alert",
                metric_name="call_answer_rate",
                condition="below",
                threshold_value=threshold,
                severity="warning",
            )

            return await self._trigger_alert(
                rule,
                {"call_answer_rate": answer_rate},
            )

        return None

    def _should_trigger(
        self,
        rule: AlertRule,
        metrics: dict[str, float],
    ) -> bool:
        """
        Check if a rule should be triggered.
        """
        metric_value = metrics.get(rule.metric_name)
        if metric_value is None:
            return False

        if rule.condition == "above":
            return metric_value > rule.threshold_value
        elif rule.condition == "below":
            return metric_value < rule.threshold_value
        elif rule.condition == "equals":
            return metric_value == rule.threshold_value
        elif rule.condition == "change_percent":
            # For change_percent, we need previous value too
            prev_key = f"{rule.metric_name}_previous"
            prev_value = metrics.get(prev_key)
            if prev_value is None or prev_value == 0:
                return False
            change = ((metric_value - prev_value) / prev_value) * 100
            return abs(change) >= rule.threshold_value

        return False

    async def _trigger_alert(
        self,
        rule: AlertRule,
        metrics: dict[str, float],
    ) -> AlertInstance:
        """
        Trigger an alert and send notifications.
        """
        metric_value = metrics.get(rule.metric_name, 0)

        # Create alert instance
        alert = AlertInstance(
            tenant_id=rule.tenant_id,
            rule_id=rule.id,
            rule_name=rule.name,
            metric_name=rule.metric_name,
            metric_value=metric_value,
            threshold_value=rule.threshold_value,
            severity=rule.severity,
            message=self._generate_alert_message(rule, metric_value),
        )

        # Save alert instance
        await self._instance_repo.save(alert)

        # Update rule's last triggered time
        rule.last_triggered_at = datetime.utcnow()
        rule.trigger_count += 1
        await self._rule_repo.update(rule)

        # Send notifications
        await self._send_notifications(alert, rule)

        return alert

    def _generate_alert_message(
        self,
        rule: AlertRule,
        metric_value: float,
    ) -> str:
        """
        Generate alert message in Persian.
        """
        messages = {
            "conversion_rate": f"هشدار: نرخ تبدیل به {metric_value:.1%} کاهش یافته است (حد مجاز: {rule.threshold_value:.1%})",
            "daily_leads_change": f"هشدار: تعداد لیدهای امروز {metric_value:.1f}% نسبت به میانگین کاهش یافته است",
            "sms_delivery_rate": f"هشدار: نرخ تحویل پیامک به {metric_value:.1%} کاهش یافته است",
            "call_answer_rate": f"هشدار: نرخ پاسخگویی تماس به {metric_value:.1%} کاهش یافته است",
        }

        return messages.get(
            rule.metric_name,
            f"هشدار: {rule.metric_name} = {metric_value} (حد: {rule.threshold_value})",
        )

    async def _send_notifications(
        self,
        alert: AlertInstance,
        rule: AlertRule,
    ) -> None:
        """
        Send notifications through configured channels.
        """
        notifications_sent = []

        for channel in rule.notification_channels:
            try:
                if channel == "sms" and rule.recipient_phones:
                    for phone in rule.recipient_phones:
                        await self._sms_service.send(
                            phone=phone,
                            message=alert.message,
                        )
                        notifications_sent.append({
                            "channel": "sms",
                            "recipient": phone,
                            "sent_at": datetime.utcnow().isoformat(),
                            "status": "sent",
                        })

                elif channel == "email" and rule.recipient_emails:
                    for email in rule.recipient_emails:
                        await self._email_service.send(
                            to=email,
                            subject=f"[{alert.severity.upper()}] {rule.name}",
                            body=alert.message,
                        )
                        notifications_sent.append({
                            "channel": "email",
                            "recipient": email,
                            "sent_at": datetime.utcnow().isoformat(),
                            "status": "sent",
                        })

                elif channel == "webhook" and rule.webhook_url:
                    async with httpx.AsyncClient() as client:
                        await client.post(
                            rule.webhook_url,
                            json={
                                "alert_id": str(alert.id),
                                "rule_name": alert.rule_name,
                                "severity": alert.severity,
                                "message": alert.message,
                                "metric_name": alert.metric_name,
                                "metric_value": alert.metric_value,
                                "triggered_at": alert.triggered_at.isoformat(),
                            },
                            timeout=10.0,
                        )
                        notifications_sent.append({
                            "channel": "webhook",
                            "recipient": rule.webhook_url,
                            "sent_at": datetime.utcnow().isoformat(),
                            "status": "sent",
                        })

            except Exception as e:
                notifications_sent.append({
                    "channel": channel,
                    "sent_at": datetime.utcnow().isoformat(),
                    "status": "failed",
                    "error": str(e),
                })

        # Update alert with notification status
        alert.notifications_sent = notifications_sent
        await self._instance_repo.update(alert)

    async def acknowledge_alert(
        self,
        alert_id: UUID,
        acknowledged_by: UUID,
    ) -> AlertInstance:
        """
        Acknowledge an alert.
        """
        alert = await self._instance_repo.get(alert_id)
        if alert:
            alert.is_acknowledged = True
            alert.acknowledged_at = datetime.utcnow()
            alert.acknowledged_by = acknowledged_by
            await self._instance_repo.update(alert)

        return alert

    async def get_active_alerts(
        self,
        tenant_id: UUID,
        severity: str | None = None,
        limit: int = 50,
    ) -> list[AlertInstance]:
        """
        Get active (unacknowledged) alerts.
        """
        return await self._instance_repo.get_unacknowledged(
            tenant_id=tenant_id,
            severity=severity,
            limit=limit,
        )

    async def get_alert_history(
        self,
        tenant_id: UUID,
        start_date: datetime,
        end_date: datetime,
        severity: str | None = None,
    ) -> list[AlertInstance]:
        """
        Get alert history for a period.
        """
        return await self._instance_repo.get_by_date_range(
            tenant_id=tenant_id,
            start_date=start_date,
            end_date=end_date,
            severity=severity,
        )

