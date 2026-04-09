"use client";

import { useTranslations } from "next-intl";
import { useFormat } from "@/lib/use-format";
import { useApi } from "@/lib/hooks";
import StatCard from "@/components/ui/StatCard";
import DataTable from "@/components/ui/DataTable";

import type { TeamPerformance, SalespersonPerformance } from "@/types/team";

export default function TeamPage() {
  const t = useTranslations("team");
  const fmt = useFormat();
  const team = useApi<TeamPerformance>("/team/performance");

  const columns = [
    {
      key: "salesperson_name",
      header: t("colName"),
      render: (s: SalespersonPerformance) => (
        <span className="font-medium">{s.salesperson_name}</span>
      ),
    },
    {
      key: "total_calls",
      header: t("colCalls"),
      render: (s: SalespersonPerformance) => fmt.number(s.metrics.total_calls),
    },
    {
      key: "answer_rate",
      header: t("colAnswerRate"),
      render: (s: SalespersonPerformance) => (
        <div className="flex items-center gap-2">
          <div className="w-16 bg-gray-200 rounded-full h-1.5">
            <div
              className="bg-green-500 h-1.5 rounded-full"
              style={{ width: `${Math.min(s.metrics.answer_rate * 100, 100)}%` }}
            />
          </div>
          <span className="text-xs">{fmt.percent(s.metrics.answer_rate)}</span>
        </div>
      ),
    },
    {
      key: "success_rate",
      header: t("colSuccessRate"),
      render: (s: SalespersonPerformance) => (
        <div className="flex items-center gap-2">
          <div className="w-16 bg-gray-200 rounded-full h-1.5">
            <div
              className="bg-blue-500 h-1.5 rounded-full"
              style={{ width: `${Math.min(s.metrics.success_rate * 100, 100)}%` }}
            />
          </div>
          <span className="text-xs">{fmt.percent(s.metrics.success_rate)}</span>
        </div>
      ),
    },
    {
      key: "assigned_leads",
      header: t("colLeads"),
      render: (s: SalespersonPerformance) => fmt.number(s.metrics.assigned_leads),
    },
    {
      key: "contact_rate",
      header: t("colContactRate"),
      render: (s: SalespersonPerformance) => fmt.percent(s.metrics.contact_rate),
    },
    {
      key: "conversion_rate",
      header: t("colConversionRate"),
      render: (s: SalespersonPerformance) => (
        <span className={s.metrics.conversion_rate > 0 ? "text-green-600 font-semibold" : ""}>
          {fmt.percent(s.metrics.conversion_rate)}
        </span>
      ),
    },
    {
      key: "total_revenue",
      header: t("colRevenue"),
      render: (s: SalespersonPerformance) => fmt.currency(s.metrics.total_revenue),
    },
    {
      key: "rank",
      header: t("colRank"),
      render: (s: SalespersonPerformance) => {
        const rank = s.rank_by_revenue || s.rank_by_conversions || s.rank_by_calls;
        if (!rank) return "—";
        const medals = ["🥇", "🥈", "🥉"];
        return rank <= 3 ? medals[rank - 1] : fmt.number(rank);
      },
    },
  ];

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-bold">{t("title")}</h1>

      {/* Team Summary */}
      {team.data?.total_metrics && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard
            title={t("totalCalls")}
            value={fmt.number(team.data.total_metrics.total_calls)}
            icon="📞"
            color="text-blue-600"
            subtitle={t("answered", { count: fmt.number(team.data.total_metrics.answered_calls) })}
          />
          <StatCard
            title={t("answerRate")}
            value={fmt.percent(team.data.total_metrics.answer_rate)}
            icon="📈"
            color="text-green-600"
            subtitle={t("successful", { rate: fmt.percent(team.data.total_metrics.success_rate) })}
          />
          <StatCard
            title={t("totalRevenue")}
            value={fmt.currency(team.data.total_metrics.total_revenue)}
            icon="💰"
            color="text-amber-600"
            subtitle={t("avgDeal", { amount: fmt.currency(team.data.total_metrics.average_deal_size) })}
          />
          <StatCard
            title={t("conversionRate")}
            value={fmt.percent(team.data.total_metrics.conversion_rate)}
            icon="🎯"
            color="text-purple-600"
            subtitle={t("invoicesPaid", { invoices: fmt.number(team.data.total_metrics.invoices_created), paid: fmt.number(team.data.total_metrics.invoices_paid) })}
          />
        </div>
      )}

      {/* Performance Table */}
      <div className="bg-white rounded-lg shadow p-5">
        <h2 className="text-sm font-semibold text-gray-700 mb-4">
          {t("performanceTable")}
        </h2>

        <DataTable
          columns={columns}
          data={team.data?.by_salesperson || []}
          isLoading={team.isLoading}
          emptyMessage={t("noTeamData")}
        />
      </div>

      {/* Top Performers & Needs Improvement */}
      {team.data && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {team.data.top_performers?.length > 0 && (
            <div className="bg-white rounded-lg shadow p-5">
              <h2 className="text-sm font-semibold text-green-700 mb-3">
                {t("topPerformers")}
              </h2>
              <div className="space-y-2">
                {team.data.top_performers.map((p, i) => (
                  <div key={i} className="flex items-center justify-between p-2 rounded bg-green-50 text-sm">
                    <span>{(p as Record<string, string>).name || t("salesperson", { index: i + 1 })}</span>
                    <span className="text-green-700 font-semibold">{(p as Record<string, string>).metric || ""}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {team.data.improvement_needed?.length > 0 && (
            <div className="bg-white rounded-lg shadow p-5">
              <h2 className="text-sm font-semibold text-amber-700 mb-3">
                {t("needsImprovement")}
              </h2>
              <div className="space-y-2">
                {team.data.improvement_needed.map((p, i) => (
                  <div key={i} className="flex items-center justify-between p-2 rounded bg-amber-50 text-sm">
                    <span>{(p as Record<string, string>).name || t("salesperson", { index: i + 1 })}</span>
                    <span className="text-amber-700">{(p as Record<string, string>).suggestion || ""}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

