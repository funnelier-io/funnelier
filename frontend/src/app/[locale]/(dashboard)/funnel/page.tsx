"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { useApi } from "@/lib/hooks";
import StatCard from "@/components/ui/StatCard";
import FunnelBarChart from "@/components/charts/FunnelBarChart";
import TrendLineChart from "@/components/charts/TrendLineChart";
import DataTable from "@/components/ui/DataTable";
import DateRangePicker from "@/components/ui/DateRangePicker";
import { fmtNum, fmtPercent, fmtPercentRaw, fmtCurrency } from "@/lib/utils";
import { STAGE_LABELS } from "@/lib/constants";
import type { FunnelMetrics, FunnelTrend, ConversionRate } from "@/types/analytics";

function daysAgo(n: number): string {
  const d = new Date();
  d.setDate(d.getDate() - n);
  return d.toISOString().split("T")[0];
}

export default function FunnelPage() {
  const t = useTranslations("funnel");
  const tc = useTranslations("common");
  const [startDate, setStartDate] = useState(() => daysAgo(30));
  const [endDate, setEndDate] = useState(() => new Date().toISOString().split("T")[0]);

  const dateQuery = `start_date=${startDate}&end_date=${endDate}`;
  const funnel = useApi<FunnelMetrics>(`/analytics/funnel?${dateQuery}`);
  const trend = useApi<FunnelTrend>(`/analytics/funnel/trend?${dateQuery}`);

  const conversionColumns = [
    {
      key: "from_stage",
      header: t("fromStage"),
      render: (r: ConversionRate) => (
        <span className="text-gray-700">
          {STAGE_LABELS[r.from_stage] || r.from_stage}
        </span>
      ),
    },
    {
      key: "to_stage",
      header: t("toStage"),
      render: (r: ConversionRate) => (
        <span className="text-gray-700">
          {STAGE_LABELS[r.to_stage] || r.to_stage}
        </span>
      ),
    },
    {
      key: "rate",
      header: t("conversionRate"),
      render: (r: ConversionRate) => {
        const pct = r.rate * 100;
        return (
          <div className="flex items-center gap-2">
            <div className="w-24 bg-gray-200 rounded-full h-2">
              <div
                className="bg-blue-500 h-2 rounded-full transition-all"
                style={{ width: `${Math.min(pct, 100)}%` }}
              />
            </div>
            <span className="text-sm font-medium">{fmtPercent(r.rate)}</span>
          </div>
        );
      },
    },
  ];

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <h1 className="text-xl font-bold">{t("title")}</h1>
        <DateRangePicker
          startDate={startDate}
          endDate={endDate}
          onChange={(s, e) => { setStartDate(s); setEndDate(e); }}
        />
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title={t("totalLeads")}
          value={fmtNum(funnel.data?.total_leads)}
          icon="📋"
          color="text-blue-600"
          change={funnel.data?.leads_change_percent}
        />
        <StatCard
          title={t("overallConversionRate")}
          value={fmtPercent(funnel.data?.overall_conversion_rate)}
          icon="📈"
          color="text-green-600"
        />
        <StatCard
          title={t("avgDaysToConvert")}
          value={fmtNum(funnel.data?.average_days_to_convert)}
          icon="⏱️"
          color="text-amber-600"
        />
        <StatCard
          title={t("totalRevenue")}
          value={fmtCurrency(funnel.data?.total_revenue)}
          icon="💰"
          color="text-purple-600"
          change={funnel.data?.revenue_change_percent}
        />
      </div>

      {/* Funnel Chart */}
      <div className="bg-white rounded-lg shadow p-5">
        <h2 className="text-sm font-semibold text-gray-700 mb-4">
          {t("funnelChart")}
        </h2>
        {funnel.data?.stage_counts ? (
          <FunnelBarChart data={funnel.data.stage_counts} />
        ) : (
          <div className="h-[280px] flex items-center justify-center text-gray-400 text-sm">
            {funnel.isLoading ? tc("loading") : tc("noData")}
          </div>
        )}
      </div>

      {/* Stage counts detail */}
      {funnel.data?.stage_counts && (
        <div className="bg-white rounded-lg shadow p-5">
          <h2 className="text-sm font-semibold text-gray-700 mb-4">
            {t("stageDetails")}
          </h2>
          <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-3">
            {funnel.data.stage_counts.map((s) => (
              <div
                key={s.stage}
                className="text-center p-3 bg-gray-50 rounded-lg"
              >
                <div className="text-xs text-gray-400 mb-1">
                  {STAGE_LABELS[s.stage] || s.stage}
                </div>
                <div className="text-lg font-bold text-gray-800">
                  {fmtNum(s.count)}
                </div>
                <div className="text-xs text-gray-400">
                  {fmtPercentRaw(s.percentage)}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Conversion Rates */}
      <div className="bg-white rounded-lg shadow p-5">
        <h2 className="text-sm font-semibold text-gray-700 mb-4">
          {t("conversionBetweenStages")}
        </h2>
        <DataTable
          columns={conversionColumns}
          data={funnel.data?.conversion_rates || []}
          isLoading={funnel.isLoading}
        />
      </div>

      {/* Trend Chart */}
      <div className="bg-white rounded-lg shadow p-5">
        <h2 className="text-sm font-semibold text-gray-700 mb-4">
          {t("dailyTrend")}
        </h2>
        {trend.data?.snapshots ? (
          <TrendLineChart data={trend.data.snapshots} />
        ) : (
          <div className="h-[300px] flex items-center justify-center text-gray-400 text-sm">
            {trend.isLoading ? tc("loading") : tc("noData")}
          </div>
        )}
      </div>
    </div>
  );
}

