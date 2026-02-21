"""
Reporting Service

Generates comprehensive reports for funnel analytics,
SMS campaigns, and sales performance.
"""

from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from src.core.domain import FunnelStage


class ReportingService:
    """
    Service for generating analytics reports.
    """

    def __init__(
        self,
        contact_repository: Any,
        call_log_repository: Any,
        sms_log_repository: Any,
        invoice_repository: Any,
    ):
        self._contact_repo = contact_repository
        self._call_log_repo = call_log_repository
        self._sms_log_repo = sms_log_repository
        self._invoice_repo = invoice_repository

    async def generate_daily_report(
        self,
        tenant_id: UUID,
        report_date: datetime | None = None,
    ) -> dict[str, Any]:
        """
        Generate daily summary report.
        """
        if report_date is None:
            report_date = datetime.utcnow()

        day_start = report_date.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = report_date.replace(hour=23, minute=59, second=59, microsecond=999999)

        # Yesterday for comparison
        yesterday_start = day_start - timedelta(days=1)
        yesterday_end = day_end - timedelta(days=1)

        report = {
            "report_date": report_date.isoformat(),
            "tenant_id": str(tenant_id),
            "generated_at": datetime.utcnow().isoformat(),
        }

        # New leads
        new_leads_today = await self._contact_repo.count_new_contacts(
            tenant_id=tenant_id,
            start_date=day_start,
            end_date=day_end,
        )
        new_leads_yesterday = await self._contact_repo.count_new_contacts(
            tenant_id=tenant_id,
            start_date=yesterday_start,
            end_date=yesterday_end,
        )
        report["leads"] = {
            "today": new_leads_today,
            "yesterday": new_leads_yesterday,
            "change": new_leads_today - new_leads_yesterday,
            "change_percent": self._calc_change_percent(new_leads_today, new_leads_yesterday),
        }

        # SMS sent
        sms_today = await self._sms_log_repo.count_sent(
            tenant_id=tenant_id,
            start_date=day_start,
            end_date=day_end,
        )
        sms_yesterday = await self._sms_log_repo.count_sent(
            tenant_id=tenant_id,
            start_date=yesterday_start,
            end_date=yesterday_end,
        )
        sms_delivered = await self._sms_log_repo.count_delivered(
            tenant_id=tenant_id,
            start_date=day_start,
            end_date=day_end,
        )
        report["sms"] = {
            "sent_today": sms_today,
            "sent_yesterday": sms_yesterday,
            "delivered_today": sms_delivered,
            "delivery_rate": sms_delivered / sms_today if sms_today > 0 else 0,
            "change": sms_today - sms_yesterday,
        }

        # Calls
        calls_today = await self._call_log_repo.get_daily_stats(
            tenant_id=tenant_id,
            date=day_start,
        )
        calls_yesterday = await self._call_log_repo.get_daily_stats(
            tenant_id=tenant_id,
            date=yesterday_start,
        )
        report["calls"] = {
            "total_today": calls_today.get("total", 0),
            "answered_today": calls_today.get("answered", 0),
            "successful_today": calls_today.get("successful", 0),
            "total_yesterday": calls_yesterday.get("total", 0),
            "answer_rate": (
                calls_today.get("answered", 0) / calls_today.get("total", 1)
                if calls_today.get("total", 0) > 0 else 0
            ),
            "success_rate": (
                calls_today.get("successful", 0) / calls_today.get("total", 1)
                if calls_today.get("total", 0) > 0 else 0
            ),
        }

        # Revenue
        revenue_today = await self._invoice_repo.sum_paid_amount(
            tenant_id=tenant_id,
            start_date=day_start,
            end_date=day_end,
        )
        revenue_yesterday = await self._invoice_repo.sum_paid_amount(
            tenant_id=tenant_id,
            start_date=yesterday_start,
            end_date=yesterday_end,
        )
        conversions_today = await self._invoice_repo.count_paid_invoices(
            tenant_id=tenant_id,
            start_date=day_start,
            end_date=day_end,
        )
        report["revenue"] = {
            "today": revenue_today,
            "yesterday": revenue_yesterday,
            "change": revenue_today - revenue_yesterday,
            "change_percent": self._calc_change_percent(revenue_today, revenue_yesterday),
            "conversions": conversions_today,
            "aov": revenue_today // conversions_today if conversions_today > 0 else 0,
        }

        return report

    async def generate_weekly_report(
        self,
        tenant_id: UUID,
        week_end: datetime | None = None,
    ) -> dict[str, Any]:
        """
        Generate weekly summary report.
        """
        if week_end is None:
            week_end = datetime.utcnow()

        week_start = week_end - timedelta(days=7)
        prev_week_start = week_start - timedelta(days=7)
        prev_week_end = week_start

        report = {
            "report_period": {
                "start": week_start.isoformat(),
                "end": week_end.isoformat(),
            },
            "tenant_id": str(tenant_id),
            "generated_at": datetime.utcnow().isoformat(),
        }

        # This week metrics
        leads_this_week = await self._contact_repo.count_new_contacts(
            tenant_id=tenant_id,
            start_date=week_start,
            end_date=week_end,
        )
        leads_prev_week = await self._contact_repo.count_new_contacts(
            tenant_id=tenant_id,
            start_date=prev_week_start,
            end_date=prev_week_end,
        )

        sms_this_week = await self._sms_log_repo.count_sent(
            tenant_id=tenant_id,
            start_date=week_start,
            end_date=week_end,
        )
        sms_delivered = await self._sms_log_repo.count_delivered(
            tenant_id=tenant_id,
            start_date=week_start,
            end_date=week_end,
        )

        calls_this_week = await self._call_log_repo.count_calls(
            tenant_id=tenant_id,
            start_date=week_start,
            end_date=week_end,
        )
        calls_answered = await self._call_log_repo.count_answered(
            tenant_id=tenant_id,
            start_date=week_start,
            end_date=week_end,
        )
        calls_successful = await self._call_log_repo.count_successful(
            tenant_id=tenant_id,
            start_date=week_start,
            end_date=week_end,
        )

        revenue_this_week = await self._invoice_repo.sum_paid_amount(
            tenant_id=tenant_id,
            start_date=week_start,
            end_date=week_end,
        )
        revenue_prev_week = await self._invoice_repo.sum_paid_amount(
            tenant_id=tenant_id,
            start_date=prev_week_start,
            end_date=prev_week_end,
        )
        conversions = await self._invoice_repo.count_paid_invoices(
            tenant_id=tenant_id,
            start_date=week_start,
            end_date=week_end,
        )

        report["summary"] = {
            "leads": {
                "this_week": leads_this_week,
                "prev_week": leads_prev_week,
                "change_percent": self._calc_change_percent(leads_this_week, leads_prev_week),
            },
            "sms": {
                "sent": sms_this_week,
                "delivered": sms_delivered,
                "delivery_rate": sms_delivered / sms_this_week if sms_this_week > 0 else 0,
            },
            "calls": {
                "total": calls_this_week,
                "answered": calls_answered,
                "successful": calls_successful,
                "answer_rate": calls_answered / calls_this_week if calls_this_week > 0 else 0,
                "success_rate": calls_successful / calls_this_week if calls_this_week > 0 else 0,
            },
            "revenue": {
                "this_week": revenue_this_week,
                "prev_week": revenue_prev_week,
                "change_percent": self._calc_change_percent(revenue_this_week, revenue_prev_week),
                "conversions": conversions,
                "aov": revenue_this_week // conversions if conversions > 0 else 0,
            },
        }

        # Funnel conversion rate
        if leads_this_week > 0:
            report["summary"]["overall_conversion_rate"] = conversions / leads_this_week
        else:
            report["summary"]["overall_conversion_rate"] = 0

        return report

    async def generate_salesperson_report(
        self,
        tenant_id: UUID,
        salesperson_id: UUID,
        start_date: datetime,
        end_date: datetime,
    ) -> dict[str, Any]:
        """
        Generate detailed report for a salesperson.
        """
        # Get call statistics
        call_stats = await self._call_log_repo.get_salesperson_stats(
            salesperson_id=salesperson_id,
            start_date=start_date,
            end_date=end_date,
        )

        # Get daily breakdown
        daily_calls = await self._call_log_repo.get_salesperson_daily_breakdown(
            salesperson_id=salesperson_id,
            start_date=start_date,
            end_date=end_date,
        )

        # Get conversion stats
        conversion_stats = await self._invoice_repo.get_salesperson_conversions(
            salesperson_id=salesperson_id,
            start_date=start_date,
            end_date=end_date,
        )

        # Get assigned leads
        assigned_leads = await self._contact_repo.count_assigned_leads(
            tenant_id=tenant_id,
            salesperson_id=salesperson_id,
            start_date=start_date,
            end_date=end_date,
        )

        report = {
            "salesperson_id": str(salesperson_id),
            "tenant_id": str(tenant_id),
            "period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
            },
            "calls": {
                "total": call_stats.get("total_calls", 0),
                "answered": call_stats.get("answered_calls", 0),
                "successful": call_stats.get("successful_calls", 0),
                "unique_contacts": call_stats.get("unique_contacts", 0),
                "total_duration_seconds": call_stats.get("total_duration", 0),
                "avg_duration_seconds": call_stats.get("avg_duration", 0),
                "answer_rate": call_stats.get("answer_rate", 0),
                "success_rate": call_stats.get("success_rate", 0),
            },
            "leads": {
                "assigned": assigned_leads,
                "contacted": call_stats.get("unique_contacts", 0),
                "contact_rate": (
                    call_stats.get("unique_contacts", 0) / assigned_leads
                    if assigned_leads > 0 else 0
                ),
            },
            "conversions": {
                "invoices_created": conversion_stats.get("total_invoices", 0),
                "invoices_paid": conversion_stats.get("paid_invoices", 0),
                "total_revenue": conversion_stats.get("total_revenue", 0),
                "avg_order_value": conversion_stats.get("avg_order_value", 0),
                "conversion_rate": (
                    conversion_stats.get("paid_invoices", 0) / call_stats.get("unique_contacts", 1)
                    if call_stats.get("unique_contacts", 0) > 0 else 0
                ),
            },
            "daily_breakdown": daily_calls,
        }

        return report

    async def generate_campaign_report(
        self,
        tenant_id: UUID,
        campaign_id: UUID,
    ) -> dict[str, Any]:
        """
        Generate report for an SMS campaign.
        """
        # Get campaign SMS stats
        sms_stats = await self._sms_log_repo.get_campaign_stats(campaign_id)

        # Get conversion stats (contacts who received campaign SMS and converted)
        conversion_stats = await self._invoice_repo.get_campaign_conversions(campaign_id)

        report = {
            "campaign_id": str(campaign_id),
            "tenant_id": str(tenant_id),
            "sms": {
                "total_sent": sms_stats.get("total_sent", 0),
                "delivered": sms_stats.get("delivered", 0),
                "failed": sms_stats.get("failed", 0),
                "pending": sms_stats.get("pending", 0),
                "delivery_rate": sms_stats.get("delivery_rate", 0),
                "total_cost": sms_stats.get("total_cost", 0),
            },
            "conversions": {
                "total": conversion_stats.get("total", 0),
                "revenue": conversion_stats.get("revenue", 0),
                "conversion_rate": (
                    conversion_stats.get("total", 0) / sms_stats.get("delivered", 1)
                    if sms_stats.get("delivered", 0) > 0 else 0
                ),
            },
            "roi": self._calculate_roi(
                cost=sms_stats.get("total_cost", 0),
                revenue=conversion_stats.get("revenue", 0),
            ),
        }

        return report

    async def generate_source_performance_report(
        self,
        tenant_id: UUID,
        start_date: datetime,
        end_date: datetime,
    ) -> list[dict[str, Any]]:
        """
        Generate performance report for each lead source.
        """
        sources = await self._contact_repo.get_lead_sources(tenant_id)
        reports = []

        for source in sources:
            source_name = source["name"]

            # Get contacts from this source
            contacts = await self._contact_repo.get_contacts_by_source(
                tenant_id=tenant_id,
                source_name=source_name,
                start_date=start_date,
                end_date=end_date,
            )

            total_leads = len(contacts)
            if total_leads == 0:
                continue

            # Count conversions
            converted = sum(1 for c in contacts if c.get("is_converted"))
            revenue = sum(c.get("conversion_value", 0) for c in contacts if c.get("is_converted"))

            reports.append({
                "source_name": source_name,
                "total_leads": total_leads,
                "converted": converted,
                "conversion_rate": converted / total_leads,
                "revenue": revenue,
                "avg_value": revenue // converted if converted > 0 else 0,
                "cost_per_lead": source.get("cost_per_lead", 0),
                "roi": self._calculate_roi(
                    cost=source.get("cost_per_lead", 0) * total_leads,
                    revenue=revenue,
                ),
            })

        # Sort by conversion rate
        reports.sort(key=lambda x: x["conversion_rate"], reverse=True)

        return reports

    def _calc_change_percent(self, current: float, previous: float) -> float:
        """Calculate percentage change."""
        if previous == 0:
            return 100.0 if current > 0 else 0.0
        return ((current - previous) / previous) * 100

    def _calculate_roi(self, cost: float, revenue: float) -> float:
        """Calculate return on investment."""
        if cost == 0:
            return 0.0
        return ((revenue - cost) / cost) * 100

