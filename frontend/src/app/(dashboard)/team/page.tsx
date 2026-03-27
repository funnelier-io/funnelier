"use client";

import { useApi } from "@/lib/hooks";
import StatCard from "@/components/ui/StatCard";
import DataTable from "@/components/ui/DataTable";
import { fmtNum, fmtPercent, fmtCurrency } from "@/lib/utils";
import type { TeamPerformance, SalespersonPerformance } from "@/types/team";

export default function TeamPage() {
  const team = useApi<TeamPerformance>("/team/performance");

  const columns = [
    {
      key: "salesperson_name",
      header: "نام",
      render: (s: SalespersonPerformance) => (
        <span className="font-medium">{s.salesperson_name}</span>
      ),
    },
    {
      key: "total_calls",
      header: "تماس‌ها",
      render: (s: SalespersonPerformance) => fmtNum(s.metrics.total_calls),
    },
    {
      key: "answer_rate",
      header: "نرخ پاسخ",
      render: (s: SalespersonPerformance) => (
        <div className="flex items-center gap-2">
          <div className="w-16 bg-gray-200 rounded-full h-1.5">
            <div
              className="bg-green-500 h-1.5 rounded-full"
              style={{ width: `${Math.min(s.metrics.answer_rate * 100, 100)}%` }}
            />
          </div>
          <span className="text-xs">{fmtPercent(s.metrics.answer_rate)}</span>
        </div>
      ),
    },
    {
      key: "success_rate",
      header: "نرخ موفقیت",
      render: (s: SalespersonPerformance) => (
        <div className="flex items-center gap-2">
          <div className="w-16 bg-gray-200 rounded-full h-1.5">
            <div
              className="bg-blue-500 h-1.5 rounded-full"
              style={{ width: `${Math.min(s.metrics.success_rate * 100, 100)}%` }}
            />
          </div>
          <span className="text-xs">{fmtPercent(s.metrics.success_rate)}</span>
        </div>
      ),
    },
    {
      key: "assigned_leads",
      header: "سرنخ‌ها",
      render: (s: SalespersonPerformance) => fmtNum(s.metrics.assigned_leads),
    },
    {
      key: "contact_rate",
      header: "نرخ تماس",
      render: (s: SalespersonPerformance) => fmtPercent(s.metrics.contact_rate),
    },
    {
      key: "conversion_rate",
      header: "نرخ تبدیل",
      render: (s: SalespersonPerformance) => (
        <span className={s.metrics.conversion_rate > 0 ? "text-green-600 font-semibold" : ""}>
          {fmtPercent(s.metrics.conversion_rate)}
        </span>
      ),
    },
    {
      key: "total_revenue",
      header: "درآمد",
      render: (s: SalespersonPerformance) => fmtCurrency(s.metrics.total_revenue),
    },
    {
      key: "rank",
      header: "رتبه",
      render: (s: SalespersonPerformance) => {
        const rank = s.rank_by_revenue || s.rank_by_conversions || s.rank_by_calls;
        if (!rank) return "—";
        const medals = ["🥇", "🥈", "🥉"];
        return rank <= 3 ? medals[rank - 1] : fmtNum(rank);
      },
    },
  ];

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-bold">تیم فروش</h1>

      {/* Team Summary */}
      {team.data?.total_metrics && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard
            title="کل تماس‌ها"
            value={fmtNum(team.data.total_metrics.total_calls)}
            icon="📞"
            color="text-blue-600"
            subtitle={`پاسخ: ${fmtNum(team.data.total_metrics.answered_calls)}`}
          />
          <StatCard
            title="نرخ پاسخ"
            value={fmtPercent(team.data.total_metrics.answer_rate)}
            icon="📈"
            color="text-green-600"
            subtitle={`موفق: ${fmtPercent(team.data.total_metrics.success_rate)}`}
          />
          <StatCard
            title="درآمد کل"
            value={fmtCurrency(team.data.total_metrics.total_revenue)}
            icon="💰"
            color="text-amber-600"
            subtitle={`میانگین معامله: ${fmtCurrency(team.data.total_metrics.average_deal_size)}`}
          />
          <StatCard
            title="نرخ تبدیل"
            value={fmtPercent(team.data.total_metrics.conversion_rate)}
            icon="🎯"
            color="text-purple-600"
            subtitle={`فاکتور: ${fmtNum(team.data.total_metrics.invoices_created)} | پرداخت: ${fmtNum(team.data.total_metrics.invoices_paid)}`}
          />
        </div>
      )}

      {/* Performance Table */}
      <div className="bg-white rounded-lg shadow p-5">
        <h2 className="text-sm font-semibold text-gray-700 mb-4">
          عملکرد فروشندگان
        </h2>

        <DataTable
          columns={columns}
          data={team.data?.by_salesperson || []}
          isLoading={team.isLoading}
          emptyMessage="اطلاعات تیم فروش موجود نیست"
        />
      </div>

      {/* Top Performers & Needs Improvement */}
      {team.data && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {team.data.top_performers?.length > 0 && (
            <div className="bg-white rounded-lg shadow p-5">
              <h2 className="text-sm font-semibold text-green-700 mb-3">
                🏆 برترین‌ها
              </h2>
              <div className="space-y-2">
                {team.data.top_performers.map((p, i) => (
                  <div
                    key={i}
                    className="flex items-center justify-between p-2 rounded bg-green-50 text-sm"
                  >
                    <span>{(p as Record<string, string>).name || `فروشنده ${i + 1}`}</span>
                    <span className="text-green-700 font-semibold">
                      {(p as Record<string, string>).metric || ""}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {team.data.improvement_needed?.length > 0 && (
            <div className="bg-white rounded-lg shadow p-5">
              <h2 className="text-sm font-semibold text-amber-700 mb-3">
                ⚠️ نیاز به بهبود
              </h2>
              <div className="space-y-2">
                {team.data.improvement_needed.map((p, i) => (
                  <div
                    key={i}
                    className="flex items-center justify-between p-2 rounded bg-amber-50 text-sm"
                  >
                    <span>{(p as Record<string, string>).name || `فروشنده ${i + 1}`}</span>
                    <span className="text-amber-700">
                      {(p as Record<string, string>).suggestion || ""}
                    </span>
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

