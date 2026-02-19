"""
Analytics Module - Funnel Service
Business logic for funnel analysis and metrics calculation
"""

from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from src.core.domain import FunnelStage

from .entities import (
    CohortAnalysis,
    ContactFunnelProgress,
    DailyFunnelSnapshot,
    FunnelMetrics,
    SalespersonMetrics,
)


class FunnelAnalyticsService:
    """
    Service for funnel analysis and metrics calculation.
    """

    def calculate_funnel_metrics(
        self,
        tenant_id: UUID,
        contacts_data: list[dict[str, Any]],
        period_start: datetime,
        period_end: datetime,
        previous_period_metrics: "FunnelMetrics | None" = None,
    ) -> FunnelMetrics:
        """
        Calculate funnel metrics for a period.

        contacts_data should contain for each contact:
        - current_stage
        - is_converted
        - conversion_value
        - days_to_convert
        """
        metrics = FunnelMetrics(
            period_start=period_start,
            period_end=period_end,
            tenant_id=tenant_id,
        )

        # Count contacts in each stage
        for contact in contacts_data:
            stage = contact.get("current_stage", FunnelStage.LEAD_ACQUIRED.value)
            metrics.stage_counts[stage] = metrics.stage_counts.get(stage, 0) + 1

            if contact.get("is_converted"):
                metrics.total_conversions += 1
                metrics.total_revenue += contact.get("conversion_value", 0)

        metrics.total_leads = len(contacts_data)

        # Calculate conversion rates
        metrics.calculate_conversion_rates()

        # Average order value
        if metrics.total_conversions > 0:
            metrics.average_order_value = metrics.total_revenue // metrics.total_conversions

            # Average days to convert
            days_list = [
                c.get("days_to_convert")
                for c in contacts_data
                if c.get("is_converted") and c.get("days_to_convert") is not None
            ]
            if days_list:
                metrics.average_days_to_convert = sum(days_list) / len(days_list)

        # Compare with previous period
        if previous_period_metrics:
            if previous_period_metrics.total_leads > 0:
                metrics.leads_change_percent = (
                    (metrics.total_leads - previous_period_metrics.total_leads)
                    / previous_period_metrics.total_leads
                    * 100
                )

            if previous_period_metrics.total_conversions > 0:
                metrics.conversions_change_percent = (
                    (metrics.total_conversions - previous_period_metrics.total_conversions)
                    / previous_period_metrics.total_conversions
                    * 100
                )

            if previous_period_metrics.total_revenue > 0:
                metrics.revenue_change_percent = (
                    (metrics.total_revenue - previous_period_metrics.total_revenue)
                    / previous_period_metrics.total_revenue
                    * 100
                )

        return metrics

    def calculate_stage_flow(
        self,
        stage_transitions: list[dict[str, Any]],
    ) -> dict[str, dict[str, int]]:
        """
        Calculate flow between stages.

        stage_transitions should contain:
        - from_stage
        - to_stage
        - count
        """
        flow = {}
        for transition in stage_transitions:
            from_stage = transition["from_stage"]
            to_stage = transition["to_stage"]
            count = transition["count"]

            if from_stage not in flow:
                flow[from_stage] = {}
            flow[from_stage][to_stage] = count

        return flow

    def calculate_drop_off_rates(
        self,
        metrics: FunnelMetrics,
    ) -> dict[str, float]:
        """
        Calculate drop-off rates at each stage.
        """
        stages = FunnelStage.get_order()
        drop_offs = {}

        for i in range(len(stages) - 1):
            current = stages[i]
            next_stage = stages[i + 1]

            current_count = metrics.stage_counts.get(current.value, 0)
            next_count = metrics.stage_counts.get(next_stage.value, 0)

            if current_count > 0:
                drop_off = (current_count - next_count) / current_count
            else:
                drop_off = 0.0

            drop_offs[f"{current.value}_drop_off"] = drop_off

        return drop_offs

    def identify_bottlenecks(
        self,
        metrics: FunnelMetrics,
        threshold: float = 0.5,
    ) -> list[dict[str, Any]]:
        """
        Identify bottlenecks in the funnel.
        A bottleneck is a stage with drop-off rate above threshold.
        """
        drop_offs = self.calculate_drop_off_rates(metrics)
        bottlenecks = []

        for stage, drop_off in drop_offs.items():
            if drop_off >= threshold:
                stage_name = stage.replace("_drop_off", "")
                bottlenecks.append({
                    "stage": stage_name,
                    "drop_off_rate": drop_off,
                    "severity": "critical" if drop_off >= 0.7 else "warning",
                    "recommendation": self._get_bottleneck_recommendation(stage_name),
                })

        return bottlenecks

    def _get_bottleneck_recommendation(self, stage: str) -> str:
        """Get recommendation for addressing a bottleneck."""
        recommendations = {
            "lead_acquired": "بررسی کیفیت لیدها و منابع جذب",
            "sms_sent": "بررسی نرخ تحویل پیامک و محتوای پیام",
            "sms_delivered": "بهبود call to action در پیامک‌ها",
            "call_attempted": "افزایش تعداد تماس‌ها و بهبود زمان‌بندی",
            "call_answered": "بهبود کیفیت مکالمات و آموزش تیم فروش",
            "invoice_issued": "بررسی قیمت‌گذاری و پیشنهادات",
        }
        return recommendations.get(stage, "نیاز به بررسی بیشتر")


class CohortAnalysisService:
    """
    Service for cohort analysis.
    """

    def calculate_cohort(
        self,
        tenant_id: UUID,
        contacts_data: list[dict[str, Any]],
        cohort_date: datetime,
        periods: list[int] = None,  # Days since acquisition
    ) -> CohortAnalysis:
        """
        Calculate cohort analysis for contacts acquired on a specific date.

        contacts_data should contain:
        - acquired_at
        - converted_at
        - conversion_value
        """
        if periods is None:
            periods = [0, 7, 14, 21, 28, 60, 90]

        cohort = CohortAnalysis(
            cohort_date=cohort_date,
            cohort_size=len(contacts_data),
            tenant_id=tenant_id,
        )

        for period in periods:
            period_end = cohort_date + timedelta(days=period)
            conversions = 0
            revenue = 0

            for contact in contacts_data:
                converted_at = contact.get("converted_at")
                if converted_at and converted_at <= period_end:
                    conversions += 1
                    revenue += contact.get("conversion_value", 0)

            cohort.conversion_by_period[period] = conversions
            cohort.revenue_by_period[period] = revenue

            if cohort.cohort_size > 0:
                cohort.cumulative_conversion_rates[period] = (
                    conversions / cohort.cohort_size
                )

        return cohort

    def compare_cohorts(
        self,
        cohorts: list[CohortAnalysis],
        period: int,
    ) -> dict[str, Any]:
        """
        Compare multiple cohorts at a specific period.
        """
        comparison = {
            "period": period,
            "cohorts": [],
            "best_cohort": None,
            "worst_cohort": None,
            "average_conversion_rate": 0.0,
        }

        rates = []
        for cohort in cohorts:
            rate = cohort.cumulative_conversion_rates.get(period, 0)
            comparison["cohorts"].append({
                "date": cohort.cohort_date.isoformat(),
                "size": cohort.cohort_size,
                "conversions": cohort.conversion_by_period.get(period, 0),
                "conversion_rate": rate,
                "revenue": cohort.revenue_by_period.get(period, 0),
            })
            rates.append(rate)

        if rates:
            comparison["average_conversion_rate"] = sum(rates) / len(rates)
            comparison["best_cohort"] = max(
                comparison["cohorts"],
                key=lambda x: x["conversion_rate"],
            )
            comparison["worst_cohort"] = min(
                comparison["cohorts"],
                key=lambda x: x["conversion_rate"],
            )

        return comparison


class SalespersonAnalyticsService:
    """
    Service for salesperson performance analysis.
    """

    def calculate_metrics(
        self,
        tenant_id: UUID,
        salesperson_id: UUID,
        salesperson_name: str,
        activities: dict[str, Any],
        period_start: datetime,
        period_end: datetime,
    ) -> SalespersonMetrics:
        """
        Calculate metrics for a salesperson.

        activities should contain:
        - calls: list of call records
        - leads: list of assigned leads
        - invoices: list of invoices
        """
        metrics = SalespersonMetrics(
            salesperson_id=salesperson_id,
            salesperson_name=salesperson_name,
            tenant_id=tenant_id,
            period_start=period_start,
            period_end=period_end,
        )

        # Call metrics
        calls = activities.get("calls", [])
        metrics.total_calls = len(calls)
        metrics.answered_calls = sum(
            1 for c in calls
            if c.get("is_successful")
        )
        metrics.total_call_duration = sum(
            c.get("duration_seconds", 0) for c in calls
        )
        if metrics.total_calls > 0:
            metrics.average_call_duration = (
                metrics.total_call_duration // metrics.total_calls
            )

        # Lead metrics
        leads = activities.get("leads", [])
        metrics.assigned_leads = len(leads)
        metrics.contacted_leads = sum(
            1 for l in leads
            if l.get("total_calls", 0) > 0
        )

        # Conversion metrics
        invoices = activities.get("invoices", [])
        metrics.invoices_created = len(invoices)
        metrics.invoices_paid = sum(
            1 for i in invoices
            if i.get("status") == "paid"
        )
        metrics.total_revenue = sum(
            i.get("total_amount", 0)
            for i in invoices
            if i.get("status") == "paid"
        )

        # Rates
        if metrics.assigned_leads > 0:
            metrics.contact_rate = metrics.contacted_leads / metrics.assigned_leads
        if metrics.contacted_leads > 0:
            metrics.conversion_rate = metrics.invoices_paid / metrics.contacted_leads

        return metrics

    def rank_salespersons(
        self,
        metrics_list: list[SalespersonMetrics],
    ) -> list[SalespersonMetrics]:
        """
        Rank salespersons by performance.
        """
        # Rank by revenue
        by_revenue = sorted(
            metrics_list,
            key=lambda x: x.total_revenue,
            reverse=True,
        )
        for i, m in enumerate(by_revenue):
            m.rank_by_revenue = i + 1

        # Rank by conversions
        by_conversions = sorted(
            metrics_list,
            key=lambda x: x.invoices_paid,
            reverse=True,
        )
        for i, m in enumerate(by_conversions):
            m.rank_by_conversions = i + 1

        return metrics_list

