"""
Funnel Analytics Application Service

Orchestrates funnel analysis across data sources and provides
unified funnel metrics and insights.
"""

from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from src.core.domain import FunnelStage

from ..domain import (
    ContactFunnelProgress,
    DailyFunnelSnapshot,
    FunnelMetrics,
    FunnelAnalyticsService,
    CohortAnalysis,
    SalespersonMetrics,
)


class FunnelAnalyticsApplicationService:
    """
    Application service for funnel analytics.
    Coordinates data retrieval, calculation, and storage.
    """

    def __init__(
        self,
        contact_repository: Any,  # IContactRepository
        call_log_repository: Any,  # ICallLogRepository
        sms_log_repository: Any,  # ISMSLogRepository
        invoice_repository: Any,  # IInvoiceRepository
        snapshot_repository: Any,  # ISnapshotRepository
    ):
        self._contact_repo = contact_repository
        self._call_log_repo = call_log_repository
        self._sms_log_repo = sms_log_repository
        self._invoice_repo = invoice_repository
        self._snapshot_repo = snapshot_repository
        self._analytics_service = FunnelAnalyticsService()

    async def get_funnel_metrics(
        self,
        tenant_id: UUID,
        start_date: datetime,
        end_date: datetime,
        include_comparison: bool = True,
    ) -> FunnelMetrics:
        """
        Get funnel metrics for a period.
        """
        # Get contact data with stage information
        contacts_data = await self._contact_repo.get_contacts_with_stages(
            tenant_id=tenant_id,
            start_date=start_date,
            end_date=end_date,
        )

        # Get previous period for comparison
        previous_metrics = None
        if include_comparison:
            period_days = (end_date - start_date).days
            prev_start = start_date - timedelta(days=period_days)
            prev_end = start_date

            prev_contacts = await self._contact_repo.get_contacts_with_stages(
                tenant_id=tenant_id,
                start_date=prev_start,
                end_date=prev_end,
            )

            previous_metrics = self._analytics_service.calculate_funnel_metrics(
                tenant_id=tenant_id,
                contacts_data=prev_contacts,
                period_start=prev_start,
                period_end=prev_end,
            )

        # Calculate current period metrics
        metrics = self._analytics_service.calculate_funnel_metrics(
            tenant_id=tenant_id,
            contacts_data=contacts_data,
            period_start=start_date,
            period_end=end_date,
            previous_period_metrics=previous_metrics,
        )

        return metrics

    async def get_funnel_by_source(
        self,
        tenant_id: UUID,
        start_date: datetime,
        end_date: datetime,
    ) -> dict[str, FunnelMetrics]:
        """
        Get funnel metrics broken down by lead source.
        """
        # Get contacts grouped by source
        sources = await self._contact_repo.get_contacts_grouped_by_source(
            tenant_id=tenant_id,
            start_date=start_date,
            end_date=end_date,
        )

        result = {}
        for source_name, contacts_data in sources.items():
            metrics = self._analytics_service.calculate_funnel_metrics(
                tenant_id=tenant_id,
                contacts_data=contacts_data,
                period_start=start_date,
                period_end=end_date,
            )
            result[source_name] = metrics

        return result

    async def get_funnel_by_category(
        self,
        tenant_id: UUID,
        start_date: datetime,
        end_date: datetime,
    ) -> dict[str, FunnelMetrics]:
        """
        Get funnel metrics broken down by lead category.
        """
        categories = await self._contact_repo.get_contacts_grouped_by_category(
            tenant_id=tenant_id,
            start_date=start_date,
            end_date=end_date,
        )

        result = {}
        for category, contacts_data in categories.items():
            metrics = self._analytics_service.calculate_funnel_metrics(
                tenant_id=tenant_id,
                contacts_data=contacts_data,
                period_start=start_date,
                period_end=end_date,
            )
            result[category] = metrics

        return result

    async def get_daily_funnel_trend(
        self,
        tenant_id: UUID,
        start_date: datetime,
        end_date: datetime,
    ) -> list[DailyFunnelSnapshot]:
        """
        Get daily funnel snapshots for trend analysis.
        """
        snapshots = await self._snapshot_repo.get_snapshots(
            tenant_id=tenant_id,
            start_date=start_date,
            end_date=end_date,
        )

        return snapshots

    async def create_daily_snapshot(
        self,
        tenant_id: UUID,
        snapshot_date: datetime | None = None,
    ) -> DailyFunnelSnapshot:
        """
        Create a daily snapshot of funnel state.
        Should be run at end of each day.
        """
        if snapshot_date is None:
            snapshot_date = datetime.utcnow().replace(hour=23, minute=59, second=59)

        # Get stage counts
        stage_counts = await self._contact_repo.get_stage_counts(tenant_id)

        # Get daily new leads
        day_start = snapshot_date.replace(hour=0, minute=0, second=0)
        new_leads = await self._contact_repo.count_new_contacts(
            tenant_id=tenant_id,
            start_date=day_start,
            end_date=snapshot_date,
        )

        # Get daily conversions
        new_conversions = await self._invoice_repo.count_paid_invoices(
            tenant_id=tenant_id,
            start_date=day_start,
            end_date=snapshot_date,
        )

        # Get daily revenue
        daily_revenue = await self._invoice_repo.sum_paid_amount(
            tenant_id=tenant_id,
            start_date=day_start,
            end_date=snapshot_date,
        )

        # Get stage transitions
        transitions = await self._contact_repo.get_stage_transitions(
            tenant_id=tenant_id,
            start_date=day_start,
            end_date=snapshot_date,
        )

        # Calculate conversion rate
        conversion_rate = 0.0
        total_leads = stage_counts.get(FunnelStage.LEAD_ACQUIRED.value, 0)
        total_conversions = stage_counts.get(FunnelStage.PAYMENT_RECEIVED.value, 0)
        if total_leads > 0:
            conversion_rate = total_conversions / total_leads

        # Calculate AOV
        aov = 0
        if new_conversions > 0:
            aov = daily_revenue // new_conversions

        snapshot = DailyFunnelSnapshot(
            tenant_id=tenant_id,
            snapshot_date=snapshot_date,
            stage_counts=stage_counts,
            new_leads=new_leads,
            new_conversions=new_conversions,
            stage_transitions=transitions,
            daily_revenue=daily_revenue,
            conversion_rate=conversion_rate,
            average_order_value=aov,
        )

        # Save snapshot
        await self._snapshot_repo.save(snapshot)

        return snapshot

    async def get_salesperson_performance(
        self,
        tenant_id: UUID,
        start_date: datetime,
        end_date: datetime,
    ) -> list[SalespersonMetrics]:
        """
        Get performance metrics for all salespeople.
        """
        # Get salesperson list
        salespeople = await self._contact_repo.get_salespeople(tenant_id)

        results = []
        for sp in salespeople:
            # Get call metrics
            call_stats = await self._call_log_repo.get_salesperson_stats(
                salesperson_id=sp["id"],
                start_date=start_date,
                end_date=end_date,
            )

            # Get assigned leads
            assigned = await self._contact_repo.count_assigned_leads(
                tenant_id=tenant_id,
                salesperson_id=sp["id"],
                start_date=start_date,
                end_date=end_date,
            )

            # Get conversions
            conversions = await self._invoice_repo.get_salesperson_conversions(
                salesperson_id=sp["id"],
                start_date=start_date,
                end_date=end_date,
            )

            metrics = SalespersonMetrics(
                salesperson_id=sp["id"],
                salesperson_name=sp["name"],
                tenant_id=tenant_id,
                period_start=start_date,
                period_end=end_date,
                total_calls=call_stats.get("total_calls", 0),
                answered_calls=call_stats.get("answered_calls", 0),
                total_call_duration=call_stats.get("total_duration", 0),
                average_call_duration=call_stats.get("avg_duration", 0),
                assigned_leads=assigned,
                contacted_leads=call_stats.get("unique_contacts", 0),
                invoices_created=conversions.get("total_invoices", 0),
                invoices_paid=conversions.get("paid_invoices", 0),
                total_revenue=conversions.get("total_revenue", 0),
            )

            # Calculate rates
            if metrics.assigned_leads > 0:
                metrics.contact_rate = metrics.contacted_leads / metrics.assigned_leads
            if metrics.contacted_leads > 0:
                metrics.conversion_rate = metrics.invoices_paid / metrics.contacted_leads

            results.append(metrics)

        # Calculate rankings
        by_revenue = sorted(results, key=lambda x: x.total_revenue, reverse=True)
        by_conversions = sorted(results, key=lambda x: x.invoices_paid, reverse=True)

        for i, m in enumerate(by_revenue):
            m.rank_by_revenue = i + 1
        for i, m in enumerate(by_conversions):
            m.rank_by_conversions = i + 1

        return results

    async def get_cohort_analysis(
        self,
        tenant_id: UUID,
        cohort_type: str = "weekly",  # weekly, monthly
        num_cohorts: int = 8,
    ) -> list[CohortAnalysis]:
        """
        Perform cohort analysis on lead acquisition.
        """
        now = datetime.utcnow()
        cohorts = []

        for i in range(num_cohorts):
            if cohort_type == "weekly":
                cohort_end = now - timedelta(weeks=i)
                cohort_start = cohort_end - timedelta(weeks=1)
            else:  # monthly
                cohort_end = now - timedelta(days=30 * i)
                cohort_start = cohort_end - timedelta(days=30)

            # Get contacts acquired in this cohort
            contacts = await self._contact_repo.get_contacts_by_acquisition_date(
                tenant_id=tenant_id,
                start_date=cohort_start,
                end_date=cohort_end,
            )

            cohort_size = len(contacts)
            if cohort_size == 0:
                continue

            # Track conversions over time
            conversion_by_period = {}
            revenue_by_period = {}

            for contact in contacts:
                if contact.get("converted_at"):
                    converted_at = contact["converted_at"]
                    days_to_convert = (converted_at - cohort_start).days

                    # Round to week
                    period = (days_to_convert // 7) * 7

                    conversion_by_period[period] = conversion_by_period.get(period, 0) + 1
                    revenue_by_period[period] = (
                        revenue_by_period.get(period, 0) + contact.get("conversion_value", 0)
                    )

            # Calculate cumulative rates
            cumulative = {}
            total_converted = 0
            for period in sorted(conversion_by_period.keys()):
                total_converted += conversion_by_period[period]
                cumulative[period] = total_converted / cohort_size

            cohort = CohortAnalysis(
                cohort_date=cohort_start,
                cohort_size=cohort_size,
                tenant_id=tenant_id,
                conversion_by_period=conversion_by_period,
                cumulative_conversion_rates=cumulative,
                revenue_by_period=revenue_by_period,
            )
            cohorts.append(cohort)

        return cohorts

    async def identify_optimization_opportunities(
        self,
        tenant_id: UUID,
        start_date: datetime,
        end_date: datetime,
    ) -> list[dict[str, Any]]:
        """
        Identify opportunities to optimize the funnel.
        """
        metrics = await self.get_funnel_metrics(
            tenant_id=tenant_id,
            start_date=start_date,
            end_date=end_date,
        )

        opportunities = []

        # Identify bottlenecks
        bottlenecks = self._analytics_service.identify_bottlenecks(metrics)
        for bottleneck in bottlenecks:
            opportunities.append({
                "type": "bottleneck",
                "stage": bottleneck["stage"],
                "severity": bottleneck["severity"],
                "drop_off_rate": bottleneck["drop_off_rate"],
                "recommendation": bottleneck["recommendation"],
            })

        # Check SMS delivery rate
        sms_stats = await self._sms_log_repo.get_delivery_stats(
            tenant_id=tenant_id,
            start_date=start_date,
            end_date=end_date,
        )
        if sms_stats.get("delivery_rate", 1.0) < 0.9:
            opportunities.append({
                "type": "sms_delivery",
                "severity": "warning",
                "current_rate": sms_stats["delivery_rate"],
                "recommendation": "بررسی نرخ تحویل پیامک - ممکن است شماره‌های نامعتبر در لیست باشد",
            })

        # Check call answer rate
        call_stats = await self._call_log_repo.get_overall_stats(
            tenant_id=tenant_id,
            start_date=start_date,
            end_date=end_date,
        )
        if call_stats.get("answer_rate", 1.0) < 0.3:
            opportunities.append({
                "type": "call_answer_rate",
                "severity": "warning",
                "current_rate": call_stats["answer_rate"],
                "recommendation": "نرخ پاسخگویی پایین - بررسی زمان‌بندی تماس‌ها و کیفیت لیدها",
            })

        return opportunities

