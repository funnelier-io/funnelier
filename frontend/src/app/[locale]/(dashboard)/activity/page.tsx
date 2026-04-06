"use client";

import { useState, useMemo } from "react";
import { useTranslations } from "next-intl";
import { useApi } from "@/lib/hooks";
import StatCard from "@/components/ui/StatCard";
import DataTable from "@/components/ui/DataTable";

interface AuditEntry {
  id: string;
  user_id: string;
  user_name: string;
  user_role: string;
  action: string;
  resource_type: string;
  resource_id: string | null;
  description: string;
  changes: Record<string, { old: unknown; new: unknown }> | null;
  ip_address: string | null;
  created_at: string;
}

interface AuditListResponse {
  items: AuditEntry[];
  total: number;
  offset: number;
  limit: number;
}

interface AuditStats {
  total_entries: number;
  user_activity: { user_id: string; user_name: string; action_count: number; last_action: string | null }[];
  action_breakdown: { action: string; count: number }[];
}

const ACTION_ICONS: Record<string, string> = {
  create: "➕",
  update: "✏️",
  delete: "🗑️",
  login: "🔐",
  logout: "🚪",
  import: "📂",
  export: "📥",
  approve: "✅",
  reject: "❌",
  activate: "🟢",
  deactivate: "🔴",
  role_change: "🔑",
  password_reset: "🔒",
  sync: "🔄",
  send_sms: "💬",
  campaign_start: "🚀",
};

const ACTION_COLORS: Record<string, string> = {
  create: "bg-green-50 text-green-700",
  update: "bg-blue-50 text-blue-700",
  delete: "bg-red-50 text-red-700",
  login: "bg-indigo-50 text-indigo-700",
  approve: "bg-emerald-50 text-emerald-700",
  reject: "bg-red-50 text-red-600",
  deactivate: "bg-amber-50 text-amber-700",
  activate: "bg-green-50 text-green-700",
};

export default function ActivityPage() {
  const t = useTranslations("audit");

  const [filterAction, setFilterAction] = useState("");
  const [filterResource, setFilterResource] = useState("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(0);
  const limit = 50;

  // Build query string
  const queryParts: string[] = [`offset=${page * limit}`, `limit=${limit}`];
  if (filterAction) queryParts.push(`action=${filterAction}`);
  if (filterResource) queryParts.push(`resource_type=${filterResource}`);
  if (search) queryParts.push(`search=${encodeURIComponent(search)}`);
  const queryStr = queryParts.join("&");

  const { data: logs, isLoading } = useApi<AuditListResponse>(`/audit?${queryStr}`);
  const { data: stats } = useApi<AuditStats>("/audit/stats?days=30");

  const entries = logs?.items ?? [];
  const total = logs?.total ?? 0;
  const totalPages = Math.ceil(total / limit);

  // KPIs
  const totalEntries = stats?.total_entries ?? 0;
  const activeUsersCount = stats?.user_activity?.length ?? 0;
  const topAction = stats?.action_breakdown?.[0];

  const actionKeys = [
    "create", "update", "delete", "login", "logout", "import", "export",
    "approve", "reject", "activate", "deactivate", "role_change", "password_reset", "sync", "send_sms",
  ];
  const resourceKeys = [
    "user", "contact", "campaign", "invoice", "import_job", "report", "sms_log", "call_log", "data_source", "setting",
  ];

  const actionLabel = (a: string) => {
    const key = `action${a.split("_").map((w) => w[0].toUpperCase() + w.slice(1)).join("")}`;
    try { return t(key as Parameters<typeof t>[0]); } catch { return a; }
  };

  const resourceLabel = (r: string) => {
    const key = `resource${r.split("_").map((w) => w[0].toUpperCase() + w.slice(1)).join("")}`;
    try { return t(key as Parameters<typeof t>[0]); } catch { return r; }
  };

  const [expandedId, setExpandedId] = useState<string | null>(null);

  const columns = [
    {
      key: "user",
      header: t("colUser"),
      render: (e: AuditEntry) => (
        <div>
          <div className="font-medium text-sm">{e.user_name}</div>
          <div className="text-xs text-gray-400">{e.user_role}</div>
        </div>
      ),
    },
    {
      key: "action",
      header: t("colAction"),
      render: (e: AuditEntry) => (
        <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${ACTION_COLORS[e.action] ?? "bg-gray-50 text-gray-600"}`}>
          <span>{ACTION_ICONS[e.action] ?? "•"}</span>
          {actionLabel(e.action)}
        </span>
      ),
    },
    {
      key: "resource",
      header: t("colResource"),
      render: (e: AuditEntry) => (
        <div>
          <div className="text-sm">{resourceLabel(e.resource_type)}</div>
          {e.resource_id && (
            <div className="text-xs text-gray-400 font-mono truncate max-w-[120px]" title={e.resource_id}>
              {e.resource_id.slice(0, 8)}…
            </div>
          )}
        </div>
      ),
    },
    {
      key: "description",
      header: t("colDescription"),
      render: (e: AuditEntry) => (
        <div>
          <div className="text-sm text-gray-700 max-w-xs truncate" title={e.description}>{e.description}</div>
          {e.changes && (
            <button
              onClick={(ev) => { ev.stopPropagation(); setExpandedId(expandedId === e.id ? null : e.id); }}
              className="text-xs text-blue-500 hover:text-blue-700 mt-0.5"
            >
              {t("viewChanges")}
            </button>
          )}
          {expandedId === e.id && e.changes && (
            <div className="mt-2 p-2 bg-gray-50 rounded text-xs space-y-1 max-w-xs">
              {Object.entries(e.changes).map(([field, change]) => (
                <div key={field}>
                  <span className="font-medium">{field}:</span>{" "}
                  <span className="text-red-500 line-through">{String(change.old ?? "—")}</span>{" → "}
                  <span className="text-green-600">{String(change.new ?? "—")}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      ),
    },
    {
      key: "ip",
      header: t("colIP"),
      render: (e: AuditEntry) => (
        <span className="text-xs text-gray-400 font-mono">{e.ip_address ?? "—"}</span>
      ),
    },
    {
      key: "date",
      header: t("colDate"),
      render: (e: AuditEntry) => (
        <div className="text-xs text-gray-500">
          <div>{new Date(e.created_at).toLocaleDateString("fa-IR")}</div>
          <div>{new Date(e.created_at).toLocaleTimeString("fa-IR", { hour: "2-digit", minute: "2-digit", second: "2-digit" })}</div>
        </div>
      ),
    },
  ];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">{t("title")}</h1>
        <p className="text-sm text-gray-500 mt-1">{t("subtitle")}</p>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard title={t("totalEntries")} value={String(totalEntries)} icon="📜" />
        <StatCard title={t("activeUsers")} value={String(activeUsersCount)} icon="👤" />
        <StatCard title={t("todayActions")} value={String(entries.length)} icon="⚡" />
        <StatCard
          title={t("topAction")}
          value={topAction ? `${actionLabel(topAction.action)} (${topAction.count})` : "—"}
          icon="🏆"
        />
      </div>

      {/* Stats panels */}
      {stats && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* User activity */}
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-4">
            <h3 className="text-sm font-semibold text-gray-700 mb-3">{t("userActivity")}</h3>
            {stats.user_activity.length === 0 ? (
              <p className="text-sm text-gray-400">{t("noEntries")}</p>
            ) : (
              <div className="space-y-2">
                {stats.user_activity.slice(0, 8).map((ua) => (
                  <div key={ua.user_id} className="flex items-center justify-between">
                    <span className="text-sm font-medium text-gray-700">{ua.user_name}</span>
                    <div className="text-xs text-gray-500">
                      {ua.action_count} {t("actions")}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Action breakdown */}
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-4">
            <h3 className="text-sm font-semibold text-gray-700 mb-3">{t("actionBreakdown")}</h3>
            {stats.action_breakdown.length === 0 ? (
              <p className="text-sm text-gray-400">{t("noEntries")}</p>
            ) : (
              <div className="space-y-2">
                {stats.action_breakdown.slice(0, 10).map((ab) => {
                  const maxCount = stats.action_breakdown[0]?.count ?? 1;
                  return (
                    <div key={ab.action} className="flex items-center gap-3">
                      <span className="text-sm w-28 shrink-0">
                        {ACTION_ICONS[ab.action] ?? "•"} {actionLabel(ab.action)}
                      </span>
                      <div className="flex-1 bg-gray-100 rounded-full h-2">
                        <div
                          className="bg-blue-500 h-2 rounded-full transition-all"
                          style={{ width: `${(ab.count / maxCount) * 100}%` }}
                        />
                      </div>
                      <span className="text-xs text-gray-500 w-8 text-end">{ab.count}</span>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3">
        <input
          type="text"
          placeholder={t("searchPlaceholder")}
          value={search}
          onChange={(e) => { setSearch(e.target.value); setPage(0); }}
          className="border border-gray-200 rounded-lg px-3 py-2 text-sm w-72 focus:ring-2 focus:ring-blue-200 outline-none"
        />
        <select
          value={filterAction}
          onChange={(e) => { setFilterAction(e.target.value); setPage(0); }}
          className="border border-gray-200 rounded-lg px-3 py-2 text-sm bg-white"
        >
          <option value="">{t("allActions")}</option>
          {actionKeys.map((a) => (
            <option key={a} value={a}>{actionLabel(a)}</option>
          ))}
        </select>
        <select
          value={filterResource}
          onChange={(e) => { setFilterResource(e.target.value); setPage(0); }}
          className="border border-gray-200 rounded-lg px-3 py-2 text-sm bg-white"
        >
          <option value="">{t("allResources")}</option>
          {resourceKeys.map((r) => (
            <option key={r} value={r}>{resourceLabel(r)}</option>
          ))}
        </select>
      </div>

      {/* Table */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-4">
        <DataTable
          columns={columns}
          data={entries}
          isLoading={isLoading}
          emptyMessage={t("noEntries")}
        />

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="flex items-center justify-center gap-2 mt-4 pt-4 border-t border-gray-100">
            <button
              onClick={() => setPage(Math.max(0, page - 1))}
              disabled={page === 0}
              className="px-3 py-1 text-sm rounded border border-gray-200 hover:bg-gray-50 disabled:opacity-30"
            >
              ←
            </button>
            <span className="text-sm text-gray-500">
              {page + 1} / {totalPages}
            </span>
            <button
              onClick={() => setPage(Math.min(totalPages - 1, page + 1))}
              disabled={page >= totalPages - 1}
              className="px-3 py-1 text-sm rounded border border-gray-200 hover:bg-gray-50 disabled:opacity-30"
            >
              →
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

