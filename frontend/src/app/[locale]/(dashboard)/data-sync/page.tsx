"use client";

import { useState, useCallback } from "react";
import { useTranslations } from "next-intl";
import { useApi } from "@/lib/hooks";
import { apiPost, apiPut, apiDelete } from "@/lib/api-client";
import StatCard from "@/components/ui/StatCard";
import DataTable from "@/components/ui/DataTable";
import EmptyState from "@/components/ui/EmptyState";
import ErrorAlert from "@/components/ui/ErrorAlert";
import { fmtDate, fmtNum, toPersianNum } from "@/lib/utils";
import type {
  DataSource,
  DataSourceListResponse,
  SyncLog,
  SyncHistoryResponse,
  ConnectorInfo,
  ConnectionTestResult,
  SyncResult,
  DedupStrategy,
} from "@/types/erp-sync";

/* ─── Source type icons & colors ──────────────────────────────────── */

const SOURCE_ICONS: Record<string, string> = {
  mock: "🧪",
  mongodb: "🍃",
  odoo: "🏢",
};

const SYNC_STATUS_COLORS: Record<string, string> = {
  success: "bg-green-50 text-green-700",
  failed: "bg-red-50 text-red-700",
  running: "bg-blue-50 text-blue-700",
  pending: "bg-yellow-50 text-yellow-700",
};

/* ═══════════════════════════════════════════════════════════════════ */

export default function DataSyncPage() {
  const t = useTranslations("dataSync");
  const tc = useTranslations("common");

  const [tab, setTab] = useState<"sources" | "history" | "connectors">("sources");
  const [showForm, setShowForm] = useState(false);
  const [editingSource, setEditingSource] = useState<DataSource | null>(null);
  const [actionMessage, setActionMessage] = useState<{ ok: boolean; text: string } | null>(null);

  /* ── API Data ────────────────────────────────────────────────────── */

  const sources = useApi<DataSourceListResponse>("/sales/erp/sources");
  const history = useApi<SyncHistoryResponse>("/sales/erp/sync-history");
  const connectors = useApi<ConnectorInfo[]>("/sales/erp/connectors");
  const dedupStrategies = useApi<{ strategies: DedupStrategy[] }>("/sales/erp/dedup-strategies");

  const sourceList = sources.data?.sources ?? [];
  const historyLogs = history.data?.logs ?? [];
  const connectorList = connectors.data ?? [];
  const strategyList = dedupStrategies.data?.strategies ?? [];

  /* ── KPI calculations ────────────────────────────────────────────── */

  const totalSources = sourceList.length;
  const activeSources = sourceList.filter((s) => s.is_active && s.sync_enabled).length;
  const totalSynced = sourceList.reduce((sum, s) => sum + s.last_sync_records, 0);
  const latestSync = sourceList
    .filter((s) => s.last_sync_at)
    .sort((a, b) => new Date(b.last_sync_at!).getTime() - new Date(a.last_sync_at!).getTime())[0];

  /* ── Actions ─────────────────────────────────────────────────────── */

  const [testingId, setTestingId] = useState<string | null>(null);
  const [syncingId, setSyncingId] = useState<string | null>(null);

  const handleTestConnection = useCallback(async (sourceId: string) => {
    setTestingId(sourceId);
    setActionMessage(null);
    try {
      const res = await apiPost<ConnectionTestResult>(`/sales/erp/sources/${sourceId}/test`);
      if (res.ok && res.data.success) {
        setActionMessage({ ok: true, text: `${t("testSuccess")}: ${res.data.message}` });
      } else {
        setActionMessage({ ok: false, text: `${t("testFailed")}: ${res.data?.message || "Unknown error"}` });
      }
    } catch {
      setActionMessage({ ok: false, text: t("testFailed") });
    }
    setTestingId(null);
  }, [t]);

  const handleTriggerSync = useCallback(async (sourceId: string) => {
    setSyncingId(sourceId);
    setActionMessage(null);
    try {
      const res = await apiPost<SyncResult>(`/sales/erp/sources/${sourceId}/sync`, { full_sync: true });
      if (res.ok && res.data.success) {
        setActionMessage({
          ok: true,
          text: `${t("syncSuccess")} — ${t("syncResult", {
            created: res.data.records_created,
            updated: res.data.records_updated,
            failed: res.data.records_failed,
          })}`,
        });
        sources.refetch();
        history.refetch();
      } else {
        const errorMsg = res.data?.errors?.join(", ") || "Unknown error";
        setActionMessage({ ok: false, text: `${t("syncFailed")}: ${errorMsg}` });
      }
    } catch {
      setActionMessage({ ok: false, text: t("syncFailed") });
    }
    setSyncingId(null);
  }, [t, sources, history]);

  const handleDeleteSource = useCallback(async (sourceId: string) => {
    if (!confirm(t("deleteConfirm"))) return;
    try {
      const res = await apiDelete(`/sales/erp/sources/${sourceId}`);
      if (res.ok) {
        sources.refetch();
        history.refetch();
      }
    } catch {
      // ignore
    }
  }, [t, sources, history]);

  const handleSaveSchedule = useCallback(async (sourceId: string, intervalMinutes: number, enabled: boolean) => {
    try {
      await apiPut(`/sales/erp/sources/${sourceId}/schedule`, {
        sync_interval_minutes: intervalMinutes,
        sync_enabled: enabled,
      });
      sources.refetch();
    } catch {
      // ignore
    }
  }, [sources]);

  /* ── Source form callbacks ────────────────────────────────────────── */

  const handleOpenCreate = () => {
    setEditingSource(null);
    setShowForm(true);
  };

  const handleOpenEdit = (src: DataSource) => {
    setEditingSource(src);
    setShowForm(true);
  };

  const handleFormClose = () => {
    setShowForm(false);
    setEditingSource(null);
  };

  const handleFormSubmit = async (data: FormData_) => {
    if (editingSource) {
      await apiPut(`/sales/erp/sources/${editingSource.id}`, data);
    } else {
      await apiPost("/sales/erp/sources", data);
    }
    setShowForm(false);
    setEditingSource(null);
    sources.refetch();
  };

  /* ── Table columns ───────────────────────────────────────────────── */

  const sourceColumns = [
    {
      key: "type",
      header: t("sourceType"),
      render: (s: DataSource) => (
        <span className="text-lg" title={s.source_type}>{SOURCE_ICONS[s.source_type] || "📦"}</span>
      ),
    },
    {
      key: "name",
      header: t("sourceName"),
      render: (s: DataSource) => (
        <div>
          <span className="font-medium text-sm">{s.name}</span>
          <span className="block text-xs text-gray-400">{s.source_type}</span>
        </div>
      ),
    },
    {
      key: "status",
      header: t("sourceStatus"),
      render: (s: DataSource) => (
        <div className="flex items-center gap-2">
          <span className={`inline-block w-2 h-2 rounded-full ${s.is_active ? "bg-green-500" : "bg-gray-300"}`} />
          <span className="text-xs">{s.is_active ? t("active") : t("inactive")}</span>
          {s.sync_enabled && (
            <span className="text-xs bg-blue-50 text-blue-700 px-1.5 py-0.5 rounded">
              {t("every")} {toPersianNum(s.sync_interval_minutes)} {t("minutes")}
            </span>
          )}
        </div>
      ),
    },
    {
      key: "last_sync",
      header: t("lastSync"),
      render: (s: DataSource) => (
        <div>
          {s.last_sync_at ? (
            <>
              <span className="text-xs">{fmtDate(s.last_sync_at)}</span>
              {s.last_sync_status && (
                <span className={`block mt-0.5 text-xs px-1.5 py-0.5 rounded-full inline-block ${SYNC_STATUS_COLORS[s.last_sync_status] || "bg-gray-50"}`}>
                  {t(`status${s.last_sync_status.charAt(0).toUpperCase() + s.last_sync_status.slice(1)}` as Parameters<typeof t>[0])}
                </span>
              )}
            </>
          ) : (
            <span className="text-xs text-gray-400">{t("never")}</span>
          )}
        </div>
      ),
    },
    {
      key: "records",
      header: t("records"),
      render: (s: DataSource) => (
        <span className="text-sm font-medium">{fmtNum(s.last_sync_records)}</span>
      ),
    },
    {
      key: "actions",
      header: t("actions"),
      render: (s: DataSource) => (
        <div className="flex items-center gap-1.5">
          <button
            onClick={(e) => { e.stopPropagation(); handleTestConnection(s.id); }}
            disabled={testingId === s.id}
            className="px-2 py-1 text-xs bg-gray-100 rounded hover:bg-gray-200 disabled:opacity-50 transition-colors"
            title={t("testConnection")}
          >
            {testingId === s.id ? "⏳" : "🔌"}
          </button>
          <button
            onClick={(e) => { e.stopPropagation(); handleTriggerSync(s.id); }}
            disabled={syncingId === s.id}
            className="px-2 py-1 text-xs bg-blue-50 text-blue-700 rounded hover:bg-blue-100 disabled:opacity-50 transition-colors"
            title={t("syncNow")}
          >
            {syncingId === s.id ? "⏳" : "🔄"}
          </button>
          <button
            onClick={(e) => { e.stopPropagation(); handleOpenEdit(s); }}
            className="px-2 py-1 text-xs bg-gray-100 rounded hover:bg-gray-200 transition-colors"
            title={t("editSource")}
          >
            ✏️
          </button>
          <button
            onClick={(e) => { e.stopPropagation(); handleDeleteSource(s.id); }}
            className="px-2 py-1 text-xs bg-red-50 text-red-600 rounded hover:bg-red-100 transition-colors"
            title={t("deleteSource")}
          >
            🗑️
          </button>
        </div>
      ),
    },
  ];

  const historyColumns = [
    {
      key: "sync_type",
      header: t("colSyncType"),
      render: (l: SyncLog) => <span className="text-xs bg-gray-100 px-2 py-0.5 rounded">{l.sync_type}</span>,
    },
    {
      key: "direction",
      header: t("colDirection"),
      render: (l: SyncLog) => (
        <span className="text-xs">{l.direction === "pull" ? `⬇️ ${t("directionPull")}` : `⬆️ ${t("directionPush")}`}</span>
      ),
    },
    {
      key: "status",
      header: t("colStatus"),
      render: (l: SyncLog) => (
        <span className={`inline-block px-2 py-0.5 rounded-full text-xs ${SYNC_STATUS_COLORS[l.status] || "bg-gray-50"}`}>
          {t(`status${l.status.charAt(0).toUpperCase() + l.status.slice(1)}` as Parameters<typeof t>[0])}
        </span>
      ),
    },
    {
      key: "records",
      header: t("colRecords"),
      render: (l: SyncLog) => (
        <div className="text-xs space-y-0.5">
          <span className="text-green-600">+{l.records_created}</span>
          {" / "}
          <span className="text-blue-600">↻{l.records_updated}</span>
          {l.records_failed > 0 && (
            <>
              {" / "}
              <span className="text-red-500">✗{l.records_failed}</span>
            </>
          )}
        </div>
      ),
    },
    {
      key: "duration",
      header: t("colDuration"),
      render: (l: SyncLog) => (
        <span className="text-xs text-gray-500">
          {l.duration_seconds != null ? `${toPersianNum(l.duration_seconds.toFixed(1))} ${t("seconds")}` : "—"}
        </span>
      ),
    },
    {
      key: "triggered_by",
      header: t("colTriggeredBy"),
      render: (l: SyncLog) => (
        <span className="text-xs">
          {l.triggered_by === "manual" ? `🖱️ ${t("triggeredByManual")}` : `⏰ ${t("triggeredByScheduled")}`}
        </span>
      ),
    },
    {
      key: "started_at",
      header: t("colDate"),
      render: (l: SyncLog) => <span className="text-xs">{fmtDate(l.started_at)}</span>,
    },
    {
      key: "errors",
      header: t("colErrors"),
      render: (l: SyncLog) => {
        if (!l.error_message && l.errors.length === 0) return <span className="text-xs text-gray-300">—</span>;
        return (
          <span className="text-xs text-red-500 max-w-[200px] truncate block" title={l.error_message || l.errors.join(", ")}>
            {l.error_message || l.errors[0]}
          </span>
        );
      },
    },
  ];

  /* ── Render ──────────────────────────────────────────────────────── */

  return (
    <div className="space-y-6">
      {/* Title */}
      <div>
        <h1 className="text-xl font-bold">{t("title")}</h1>
        <p className="text-sm text-gray-400 mt-1">{t("subtitle")}</p>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard title={t("kpiTotalSources")} value={fmtNum(totalSources)} icon="📦" color="text-blue-600" />
        <StatCard title={t("kpiActiveSources")} value={fmtNum(activeSources)} icon="✅" color="text-green-600" />
        <StatCard title={t("kpiTotalSynced")} value={fmtNum(totalSynced)} icon="🔄" color="text-purple-600" />
        <StatCard
          title={t("kpiLastSync")}
          value={latestSync?.last_sync_at ? fmtDate(latestSync.last_sync_at) : t("never")}
          icon="🕐"
          color="text-gray-600"
        />
      </div>

      {/* Action message */}
      {actionMessage && (
        <div className={`p-3 rounded-lg text-sm ${actionMessage.ok ? "bg-green-50 text-green-700" : "bg-red-50 text-red-700"}`}>
          {actionMessage.text}
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-2 border-b border-gray-200 pb-0">
        {(["sources", "history", "connectors"] as const).map((key) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
              tab === key
                ? "border-blue-600 text-blue-600"
                : "border-transparent text-gray-500 hover:text-gray-700"
            }`}
          >
            {key === "sources" && t("dataSources")}
            {key === "history" && t("syncHistory")}
            {key === "connectors" && t("connectors")}
          </button>
        ))}
      </div>

      {/* Tab: Sources */}
      {tab === "sources" && (
        <div className="bg-white rounded-lg shadow p-5">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-semibold text-gray-700">{t("dataSources")}</h2>
            <div className="flex gap-2">
              <button onClick={sources.refetch} className="text-xs text-blue-600 hover:text-blue-800">{t("refresh")}</button>
              <button
                onClick={handleOpenCreate}
                className="px-3 py-1.5 text-xs bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
              >
                {t("addSource")}
              </button>
            </div>
          </div>

          {sources.error && <ErrorAlert message={sources.error} onRetry={sources.refetch} />}

          {!sources.isLoading && sourceList.length === 0 ? (
            <EmptyState title={t("noSources")} description={t("noSourcesDesc")} icon="📦" />
          ) : (
            <DataTable columns={sourceColumns} data={sourceList} isLoading={sources.isLoading} emptyMessage={t("noSources")} />
          )}
        </div>
      )}

      {/* Tab: History */}
      {tab === "history" && (
        <div className="bg-white rounded-lg shadow p-5">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-semibold text-gray-700">{t("syncHistory")}</h2>
            <button onClick={history.refetch} className="text-xs text-blue-600 hover:text-blue-800">{t("refresh")}</button>
          </div>

          {history.error && <ErrorAlert message={history.error} onRetry={history.refetch} />}

          <DataTable columns={historyColumns} data={historyLogs} isLoading={history.isLoading} emptyMessage={t("noHistory")} />
        </div>
      )}

      {/* Tab: Connectors */}
      {tab === "connectors" && (
        <div className="space-y-6">
          {/* Available connectors */}
          <div className="bg-white rounded-lg shadow p-5">
            <h2 className="text-sm font-semibold text-gray-700 mb-4">{t("availableConnectors")}</h2>
            {connectors.isLoading ? (
              <div className="text-sm text-gray-400">{tc("loading")}</div>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                {connectorList.map((c) => (
                  <div key={c.name} className="border border-gray-200 rounded-lg p-4 hover:shadow-sm transition-shadow">
                    <div className="flex items-center gap-3 mb-3">
                      <span className="text-2xl">{SOURCE_ICONS[c.name] || "📦"}</span>
                      <div>
                        <h3 className="text-sm font-semibold">{c.display_name}</h3>
                        <span className="text-xs text-gray-400">{c.sync_direction}</span>
                      </div>
                    </div>
                    <div className="flex flex-wrap gap-1.5">
                      {c.supports_invoices && <FeatureBadge label={t("supportsInvoices")} />}
                      {c.supports_payments && <FeatureBadge label={t("supportsPayments")} />}
                      {c.supports_customers && <FeatureBadge label={t("supportsCustomers")} />}
                      {c.supports_products && <FeatureBadge label={t("supportsProducts")} />}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Dedup strategies */}
          <div className="bg-white rounded-lg shadow p-5">
            <h2 className="text-sm font-semibold text-gray-700 mb-4">{t("dedupStrategies")}</h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {strategyList.map((s) => (
                <div key={s.name} className="border border-gray-200 rounded-lg p-3">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-sm font-medium">{s.display_name}</span>
                    {s.is_default && (
                      <span className="text-xs bg-blue-50 text-blue-700 px-1.5 py-0.5 rounded">{t("defaultStrategy")}</span>
                    )}
                  </div>
                  <p className="text-xs text-gray-400">{s.description}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Add/Edit Source Modal */}
      {showForm && (
        <SourceFormModal
          source={editingSource}
          onClose={handleFormClose}
          onSubmit={handleFormSubmit}
          t={t}
        />
      )}
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════════
 * Sub-components
 * ═══════════════════════════════════════════════════════════════════ */

function FeatureBadge({ label }: { label: string }) {
  return (
    <span className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full">{label}</span>
  );
}

/* ── Form data type (not the DOM FormData) ─────────────────────── */

interface FormData_ {
  name: string;
  source_type: string;
  connection_config: Record<string, string>;
  sync_interval_minutes: number;
  is_active: boolean;
  description?: string;
}

function SourceFormModal({
  source,
  onClose,
  onSubmit,
  t,
}: {
  source: DataSource | null;
  onClose: () => void;
  onSubmit: (data: FormData_) => Promise<void>;
  t: ReturnType<typeof useTranslations>;
}) {
  const tc = useTranslations("common");
  const isEdit = !!source;

  const [name, setName] = useState(source?.name ?? "");
  const [sourceType, setSourceType] = useState(source?.source_type ?? "mongodb");
  const [url, setUrl] = useState((source?.connection_config?.url as string) ?? "");
  const [database, setDatabase] = useState((source?.connection_config?.database as string) ?? "");
  const [username, setUsername] = useState((source?.connection_config?.username as string) ?? "");
  const [password, setPassword] = useState("");
  const [description, setDescription] = useState("");
  const [interval, setInterval] = useState(source?.sync_interval_minutes ?? 60);
  const [active, setActive] = useState(source?.is_active ?? true);
  const [saving, setSaving] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);

    const config: Record<string, string> = {};
    if (sourceType === "mongodb") {
      config.url = url;
      config.database = database;
    } else if (sourceType === "odoo") {
      config.url = url;
      config.database = database;
      config.username = username;
      if (password) config.password = password;
    }

    await onSubmit({
      name,
      source_type: sourceType,
      connection_config: config,
      sync_interval_minutes: interval,
      is_active: active,
      description: description || undefined,
    });
    setSaving(false);
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={onClose}>
      <div
        className="bg-white rounded-xl shadow-xl w-full max-w-lg mx-4 max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="p-5 border-b border-gray-100">
          <h2 className="text-lg font-semibold">{isEdit ? t("editSourceTitle") : t("addSourceTitle")}</h2>
        </div>

        <form onSubmit={handleSubmit} className="p-5 space-y-4">
          {/* Name */}
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">{t("fieldName")}</label>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
              placeholder={t("placeholderName")}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          {/* Type */}
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">{t("fieldType")}</label>
            <select
              value={sourceType}
              onChange={(e) => setSourceType(e.target.value)}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="mock">{t("typeMock")}</option>
              <option value="mongodb">{t("typeMongodb")}</option>
              <option value="odoo">{t("typeOdoo")}</option>
            </select>
          </div>

          {/* Connection URL */}
          {(sourceType === "mongodb" || sourceType === "odoo") && (
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">{t("fieldUrl")}</label>
              <input
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                placeholder={t("placeholderUrl")}
                dir="ltr"
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          )}

          {/* Database */}
          {(sourceType === "mongodb" || sourceType === "odoo") && (
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">{t("fieldDatabase")}</label>
              <input
                value={database}
                onChange={(e) => setDatabase(e.target.value)}
                placeholder={t("placeholderDb")}
                dir="ltr"
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          )}

          {/* Username / Password for Odoo */}
          {sourceType === "odoo" && (
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">{t("fieldUsername")}</label>
                <input
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder={t("placeholderUser")}
                  dir="ltr"
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">{t("fieldPassword")}</label>
                <input
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder={t("placeholderPass")}
                  type="password"
                  dir="ltr"
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
            </div>
          )}

          {/* Description */}
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">{t("fieldDescription")}</label>
            <input
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder={t("placeholderDesc")}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          {/* Interval */}
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">{t("fieldInterval")}</label>
            <input
              type="number"
              min={5}
              max={1440}
              value={interval}
              onChange={(e) => setInterval(Number(e.target.value))}
              dir="ltr"
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          {/* Active toggle */}
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={active}
              onChange={(e) => setActive(e.target.checked)}
              className="w-4 h-4 rounded text-blue-600 focus:ring-blue-500"
            />
            <span className="text-sm">{t("fieldActive")}</span>
          </label>

          {/* Buttons */}
          <div className="flex items-center justify-end gap-3 pt-2">
            <button type="button" onClick={onClose} className="px-4 py-2 text-sm text-gray-600 hover:text-gray-800 transition-colors">
              {tc("cancel")}
            </button>
            <button
              type="submit"
              disabled={saving || !name}
              className="px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors"
            >
              {saving ? tc("loading") : isEdit ? tc("save") : tc("create")}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}



