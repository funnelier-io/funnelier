"use client";

import Link from "next/link";
import { useApi } from "@/lib/hooks";
import StatCard from "@/components/ui/StatCard";
import FunnelBarChart from "@/components/charts/FunnelBarChart";
import RFMDoughnutChart from "@/components/charts/RFMDoughnutChart";
import TrendLineChart from "@/components/charts/TrendLineChart";
import { fmtNum, fmtPercent, fmtCurrency } from "@/lib/utils";
import { SEVERITY_CONFIG } from "@/lib/constants";
import type { FunnelMetrics, FunnelTrend, DailyReport, OptimizationResponse } from "@/types/analytics";
import type { SegmentDistribution } from "@/types/segments";
import type { AlertListResponse } from "@/types/alerts";

export default function DashboardPage() {
  const funnel = useApi<FunnelMetrics>("/analytics/funnel");
  const trend = useApi<FunnelTrend>("/analytics/funnel/trend");
  const daily = useApi<DailyReport>("/analytics/reports/daily");
  const segments = useApi<SegmentDistribution>("/segments/distribution");
  const optimization = useApi<OptimizationResponse>("/analytics/optimization");
  const alerts = useApi<AlertListResponse>("/analytics/alerts?limit=5");

  const isLoading = funnel.isLoading || trend.isLoading || daily.isLoading || segments.isLoading;

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="text-gray-400 text-sm">در حال بارگذاری داشبورد...</div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-bold">داشبورد</h1>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="کل سرنخ‌ها"
          value={fmtNum(funnel.data?.total_leads)}
          icon="📋"
          color="text-blue-600"
          change={funnel.data?.leads_change_percent}
        />
        <StatCard
          title="تبدیل‌ها"
          value={fmtNum(funnel.data?.total_conversions)}
          icon="✅"
          color="text-green-600"
          change={funnel.data?.conversions_change_percent}
        />
        <StatCard
          title="درآمد"
          value={fmtCurrency(funnel.data?.total_revenue)}
          icon="💰"
          color="text-amber-600"
          change={funnel.data?.revenue_change_percent}
        />
        <StatCard
          title="نرخ تبدیل"
          value={fmtPercent(funnel.data?.overall_conversion_rate)}
          icon="📈"
          color="text-purple-600"
          subtitle={
            funnel.data?.average_days_to_convert
              ? `میانگین ${fmtNum(funnel.data.average_days_to_convert)} روز`
              : undefined
          }
        />
      </div>

      {/* Daily Report Cards */}
      {daily.data && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard
            title="سرنخ امروز"
            value={fmtNum(daily.data.leads.today)}
            icon="📥"
            color="text-blue-500"
            change={daily.data.leads.change_percent}
          />
          <StatCard
            title="پیامک ارسالی امروز"
            value={fmtNum(daily.data.sms.sent_today)}
            icon="💬"
            color="text-purple-500"
            subtitle={`نرخ تحویل: ${fmtPercent(daily.data.sms.delivery_rate)}`}
          />
          <StatCard
            title="تماس‌های امروز"
            value={fmtNum(daily.data.calls.total_today)}
            icon="📞"
            color="text-amber-500"
            subtitle={`نرخ پاسخ: ${fmtPercent(daily.data.calls.answer_rate)}`}
          />
          <StatCard
            title="درآمد امروز"
            value={fmtCurrency(daily.data.revenue.today)}
            icon="💵"
            color="text-green-500"
          />
        </div>
      )}

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Funnel Chart */}
        <div className="bg-white rounded-lg shadow p-5">
          <h2 className="text-sm font-semibold text-gray-700 mb-4">
            فانل فروش
          </h2>
          {funnel.data?.stage_counts ? (
            <FunnelBarChart data={funnel.data.stage_counts} />
          ) : (
            <div className="h-[280px] flex items-center justify-center text-gray-400 text-sm">
              داده‌ای موجود نیست
            </div>
          )}
        </div>

        {/* RFM Distribution */}
        <div className="bg-white rounded-lg shadow p-5">
          <h2 className="text-sm font-semibold text-gray-700 mb-4">
            توزیع بخش‌بندی RFM
          </h2>
          {segments.data?.segments ? (
            <RFMDoughnutChart data={segments.data.segments} />
          ) : (
            <div className="h-[280px] flex items-center justify-center text-gray-400 text-sm">
              داده‌ای موجود نیست
            </div>
          )}
        </div>
      </div>

      {/* Trend Chart */}
      <div className="bg-white rounded-lg shadow p-5">
        <h2 className="text-sm font-semibold text-gray-700 mb-4">
          روند هفتگی
        </h2>
        {trend.data?.snapshots ? (
          <TrendLineChart data={trend.data.snapshots} />
        ) : (
          <div className="h-[300px] flex items-center justify-center text-gray-400 text-sm">
            داده‌ای موجود نیست
          </div>
        )}
      </div>

      {/* Optimization Insights & Recent Alerts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Optimization Opportunities */}
        <div className="bg-white rounded-lg shadow p-5">
          <h2 className="text-sm font-semibold text-gray-700 mb-4">
            💡 فرصت‌های بهینه‌سازی
          </h2>
          {optimization.data?.opportunities &&
          optimization.data.opportunities.length > 0 ? (
            <div className="space-y-3">
              {optimization.data.opportunities.slice(0, 5).map((opp, i) => {
                const cfg =
                  SEVERITY_CONFIG[opp.severity] || SEVERITY_CONFIG.info;
                return (
                  <div
                    key={i}
                    className={`${cfg.bg} rounded-lg p-3 flex items-start gap-2`}
                  >
                    <span className="text-sm shrink-0">{cfg.icon}</span>
                    <div className="flex-1 min-w-0">
                      <div className={`text-xs font-medium ${cfg.color}`}>
                        {opp.type === "bottleneck"
                          ? "گلوگاه"
                          : opp.type === "improvement"
                            ? "فرصت بهبود"
                            : opp.type}
                      </div>
                      <div className="text-sm text-gray-700 mt-0.5">
                        {opp.recommendation}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="text-center text-gray-400 text-sm py-6">
              فرصت بهینه‌سازی شناسایی نشده 🎉
            </div>
          )}
        </div>

        {/* Recent Alerts */}
        <div className="bg-white rounded-lg shadow p-5">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-semibold text-gray-700">
              🔔 هشدارهای اخیر
            </h2>
            {alerts.data && alerts.data.unacknowledged_count > 0 && (
              <Link
                href="/alerts"
                className="text-xs text-blue-600 hover:text-blue-800"
              >
                مشاهده همه ({fmtNum(alerts.data.unacknowledged_count)})
              </Link>
            )}
          </div>
          {alerts.data?.alerts && alerts.data.alerts.length > 0 ? (
            <div className="space-y-2">
              {alerts.data.alerts.slice(0, 5).map((alert) => {
                const cfg =
                  SEVERITY_CONFIG[alert.severity] || SEVERITY_CONFIG.info;
                return (
                  <div
                    key={alert.id}
                    className={`flex items-center gap-2 p-2 rounded-lg ${cfg.bg}`}
                  >
                    <span className="text-sm">{cfg.icon}</span>
                    <div className="flex-1 min-w-0">
                      <div className="text-xs font-medium truncate">
                        {alert.rule_name}
                      </div>
                      <div className="text-xs text-gray-500 truncate">
                        {alert.message}
                      </div>
                    </div>
                    {!alert.is_acknowledged && (
                      <span className="shrink-0 text-xs bg-amber-200 text-amber-800 px-1.5 py-0.5 rounded">
                        جدید
                      </span>
                    )}
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="text-center text-gray-400 text-sm py-6">
              هشداری وجود ندارد
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

