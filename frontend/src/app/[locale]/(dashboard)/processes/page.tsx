"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { useFormat } from "@/lib/use-format";
import { useApi } from "@/lib/hooks";
import StatCard from "@/components/ui/StatCard";
import DataTable from "@/components/ui/DataTable";

// ─── Types ────────────────────────────────────────────────────────────────────

interface ProcessStats {
  workflow_type: string;
  active: number;
  completed: number;
  failed: number;
  avg_duration_minutes: number;
}

interface ProcessInstance {
  process_id: string;
  business_key: string;
  workflow_type: string;
  current_step: string;
  started_at: string;
  duration_minutes: number;
  is_stale: boolean;
}

interface ProcessSummary {
  stats: ProcessStats[];
  stale_instances: ProcessInstance[];
  total_active: number;
  total_completed: number;
  total_failed: number;
  health_score: number;
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

const WORKFLOW_LABELS: Record<string, string> = {
  campaign_workflow: "فرآیند کمپین",
  user_approval: "تأیید کاربر",
  funnel_journey: "مسیر فانل",
  erp_escalation: "تشدید ERP",
};

const WORKFLOW_ICONS: Record<string, string> = {
  campaign_workflow: "📢",
  user_approval: "✅",
  funnel_journey: "🔀",
  erp_escalation: "⚠️",
};

function healthColor(score: number): string {
  if (score >= 80) return "text-green-600";
  if (score >= 50) return "text-amber-600";
  return "text-red-600";
}

function StatusBadge({ is_stale }: { is_stale: boolean }) {
  return is_stale ? (
    <span className="px-2 py-0.5 text-xs bg-red-100 text-red-700 rounded-full">متوقف</span>
  ) : (
    <span className="px-2 py-0.5 text-xs bg-green-100 text-green-700 rounded-full">فعال</span>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function ProcessesPage() {
  const t = useTranslations("processes");
  const fmt = useFormat();
  const tc = useTranslations("common");

  const summary = useApi<ProcessSummary>("/processes/summary");
  const instances = useApi<{ instances: ProcessInstance[]; total: number }>(
    "/processes/instances?status=active&limit=50"
  );

  const stats = summary.data?.stats || [];
  const stale = summary.data?.stale_instances || [];
  const instanceList = instances.data?.instances || [];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold">{t("title")}</h1>
        <span className="text-sm text-gray-500">{t("subtitle")}</span>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title={t("totalActive")}
          value={fmt.number(summary.data?.total_active)}
          icon="⚙️"
          color="text-blue-600"
          loading={summary.loading}
        />
        <StatCard
          title={t("totalCompleted")}
          value={fmt.number(summary.data?.total_completed)}
          icon="✅"
          color="text-green-600"
          loading={summary.loading}
        />
        <StatCard
          title={t("totalFailed")}
          value={fmt.number(summary.data?.total_failed)}
          icon="❌"
          color="text-red-600"
          loading={summary.loading}
        />
        <StatCard
          title={t("healthScore")}
          value={summary.data ? `${summary.data.health_score}%` : "—"}
          icon="💚"
          color={healthColor(summary.data?.health_score ?? 100)}
          loading={summary.loading}
        />
      </div>

      {/* Workflow Pipeline Cards */}
      <div>
        <h2 className="text-base font-semibold mb-3">{t("workflowBreakdown")}</h2>
        {summary.loading && (
          <p className="text-sm text-gray-400">{tc("loading")}</p>
        )}
        {!summary.loading && stats.length === 0 && (
          <div className="bg-white rounded-xl border p-8 text-center text-gray-400 text-sm">
            {t("noProcesses")}
          </div>
        )}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {stats.map((s) => (
            <div key={s.workflow_type} className="bg-white rounded-xl border p-5 space-y-3">
              <div className="flex items-center gap-2">
                <span className="text-2xl">{WORKFLOW_ICONS[s.workflow_type] || "🔧"}</span>
                <span className="font-semibold text-gray-800">
                  {WORKFLOW_LABELS[s.workflow_type] || s.workflow_type}
                </span>
              </div>

              {/* Progress bars */}
              <div className="space-y-1.5 text-sm">
                <div className="flex justify-between">
                  <span className="text-gray-500">{t("active")}</span>
                  <span className="font-medium text-blue-600">{s.active}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">{t("completed")}</span>
                  <span className="font-medium text-green-600">{s.completed}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">{t("failed")}</span>
                  <span className="font-medium text-red-600">{s.failed}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">{t("avgDuration")}</span>
                  <span className="font-medium">
                    {s.avg_duration_minutes > 0
                      ? `${Math.round(s.avg_duration_minutes)} دقیقه`
                      : "—"}
                  </span>
                </div>
              </div>

              {/* Mini progress bar */}
              {s.active + s.completed + s.failed > 0 && (
                <div className="w-full bg-gray-100 rounded-full h-2 overflow-hidden">
                  {(() => {
                    const total = s.active + s.completed + s.failed;
                    const completedPct = Math.round((s.completed / total) * 100);
                    const failedPct = Math.round((s.failed / total) * 100);
                    return (
                      <div className="flex h-full">
                        <div
                          className="bg-green-500 h-full transition-all"
                          style={{ width: `${completedPct}%` }}
                        />
                        <div
                          className="bg-red-400 h-full transition-all"
                          style={{ width: `${failedPct}%` }}
                        />
                        <div className="bg-blue-400 h-full flex-1" />
                      </div>
                    );
                  })()}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Stale Process Alerts */}
      {stale.length > 0 && (
        <div>
          <h2 className="text-base font-semibold mb-3 text-red-700">
            ⚠️ {t("staleAlerts")} ({stale.length})
          </h2>
          <div className="bg-red-50 rounded-xl border border-red-200 divide-y divide-red-100">
            {stale.map((inst) => (
              <div key={inst.process_id} className="px-5 py-3 flex items-center justify-between gap-4 text-sm">
                <div>
                  <span className="font-mono text-xs text-gray-500 mr-2">{inst.business_key}</span>
                  <span className="text-gray-700">
                    {WORKFLOW_LABELS[inst.workflow_type] || inst.workflow_type}
                  </span>
                  <span className="mx-2 text-gray-400">›</span>
                  <span className="text-gray-600">{inst.current_step}</span>
                </div>
                <div className="flex items-center gap-3 shrink-0">
                  <span className="text-red-500">
                    {Math.round(inst.duration_minutes)} دقیقه
                  </span>
                  <StatusBadge is_stale={inst.is_stale} />
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Active Instance Table */}
      <div>
        <h2 className="text-base font-semibold mb-3">{t("activeInstances")}</h2>
        <DataTable
          columns={[
            { key: "business_key", label: t("businessKey") },
            {
              key: "workflow_type",
              label: t("workflowType"),
              render: (v: string) => WORKFLOW_LABELS[v] || v,
            },
            { key: "current_step", label: t("currentStep") },
            {
              key: "started_at",
              label: t("startedAt"),
              render: (v: string) =>
                v ? new Date(v).toLocaleDateString("fa-IR") : "—",
            },
            {
              key: "duration_minutes",
              label: t("duration"),
              render: (v: number) => `${Math.round(v)} دقیقه`,
            },
            {
              key: "is_stale",
              label: t("status"),
              render: (_: unknown, row: ProcessInstance) => (
                <StatusBadge is_stale={row.is_stale} />
              ),
            },
          ]}
          data={instanceList}
          loading={instances.loading}
          emptyMessage={t("noInstances")}
        />
      </div>
    </div>
  );
}

