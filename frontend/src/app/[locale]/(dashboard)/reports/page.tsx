"use client";

import { useState, useCallback } from "react";
import { useTranslations } from "next-intl";
import { useFormat } from "@/lib/use-format";
import { useApi } from "@/lib/hooks";
import { apiPost, apiDelete } from "@/lib/api-client";
import { API_BASE } from "@/lib/constants";
import StatCard from "@/components/ui/StatCard";
import EmptyState from "@/components/ui/EmptyState";

import type {
  ExportFormat,
  ReportType,
  ReportColumnInfo,
  ScheduledReportResponse,
  ScheduledReportListResponse,
} from "@/types/export";

/* ─── Quick-export card config ──────────────────────────────────── */

interface QuickExportCard {
  key: string;
  reportType: ReportType;
  icon: string;
  apiPath: string;
}

const QUICK_EXPORTS: QuickExportCard[] = [
  { key: "contacts", reportType: "contacts", icon: "📋", apiPath: "/export/contacts" },
  { key: "invoices", reportType: "invoices", icon: "🧾", apiPath: "/export/invoices" },
  { key: "callLogs", reportType: "call_logs", icon: "📞", apiPath: "/export/call-logs" },
  { key: "smsLogs", reportType: "sms_logs", icon: "💬", apiPath: "/export/sms-logs" },
  { key: "payments", reportType: "payments", icon: "💳", apiPath: "/export/payments" },
];

const SUMMARY_REPORTS = [
  { key: "funnelSummary", reportType: "funnel_summary" as ReportType, icon: "🔻" },
  { key: "teamPerformance", reportType: "team_performance" as ReportType, icon: "👥" },
  { key: "rfmBreakdown", reportType: "rfm_breakdown" as ReportType, icon: "🎯" },
];

const FORMAT_OPTIONS: { value: ExportFormat; label: string; icon: string }[] = [
  { value: "xlsx", label: "Excel", icon: "📊" },
  { value: "csv", label: "CSV", icon: "📄" },
  { value: "pdf", label: "PDF", icon: "📑" },
];

const FREQUENCY_OPTIONS = [
  { value: "daily", key: "daily" },
  { value: "weekly", key: "weekly" },
  { value: "monthly", key: "monthly" },
] as const;

/* ─── File download helper ──────────────────────────────────────── */

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("token");
}

async function downloadFile(url: string, fallbackName: string) {
  const token = getToken();
  const headers: Record<string, string> = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(url, { headers });
  if (!res.ok) throw new Error("Download failed");

  const disposition = res.headers.get("Content-Disposition") || "";
  const filenameMatch = disposition.match(/filename="?([^"]+)"?/);
  const filename = filenameMatch?.[1] || fallbackName;

  const blob = await res.blob();
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  a.click();
  URL.revokeObjectURL(a.href);
}

async function downloadPost(path: string, body: unknown, fallbackName: string) {
  const token = getToken();
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${API_BASE}${path}`, { method: "POST", headers, body: JSON.stringify(body) });
  if (!res.ok) throw new Error("Download failed");

  const disposition = res.headers.get("Content-Disposition") || "";
  const filenameMatch = disposition.match(/filename="?([^"]+)"?/);
  const filename = filenameMatch?.[1] || fallbackName;

  const blob = await res.blob();
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  a.click();
  URL.revokeObjectURL(a.href);
}

/* ═══════════════════════════════════════════════════════════════════ */

export default function ReportsPage() {
  const t = useTranslations("reports");
  const fmt = useFormat();
  const tc = useTranslations("common");

  const [tab, setTab] = useState<"quick" | "summary" | "custom" | "scheduled">("quick");
  const [downloading, setDownloading] = useState<string | null>(null);
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null);

  /* ── Scheduled reports data ──────────────────────────────────────── */
  const schedules = useApi<ScheduledReportListResponse>("/export/schedules");
  const scheduleList = schedules.data?.items ?? [];

  /* ── Columns metadata ─────────────────────────────────────────── */
  const columns = useApi<Record<string, ReportColumnInfo[]>>("/export/columns");

  /* ── Quick export handler ────────────────────────────────────── */
  const [quickFormat, setQuickFormat] = useState<ExportFormat>("xlsx");
  const [quickStartDate, setQuickStartDate] = useState("");
  const [quickEndDate, setQuickEndDate] = useState("");

  const handleQuickExport = useCallback(
    async (card: QuickExportCard) => {
      setDownloading(card.key);
      setMessage(null);
      try {
        const params = new URLSearchParams({ format: quickFormat });
        if (quickStartDate) params.set("start_date", quickStartDate);
        if (quickEndDate) params.set("end_date", quickEndDate);
        await downloadFile(
          `${API_BASE}${card.apiPath}?${params}`,
          `${card.key}.${quickFormat}`
        );
        setMessage({ ok: true, text: t("downloadSuccess") });
      } catch {
        setMessage({ ok: false, text: t("downloadError") });
      } finally {
        setDownloading(null);
      }
    },
    [quickFormat, quickStartDate, quickEndDate, t]
  );

  /* ── Summary report handler ──────────────────────────────────── */
  const [summaryFormat, setSummaryFormat] = useState<ExportFormat>("xlsx");
  const [summaryStartDate, setSummaryStartDate] = useState("");
  const [summaryEndDate, setSummaryEndDate] = useState("");

  const handleSummaryExport = useCallback(
    async (reportType: ReportType) => {
      setDownloading(reportType);
      setMessage(null);
      try {
        const body = {
          report_type: reportType,
          format: summaryFormat,
          start_date: summaryStartDate || null,
          end_date: summaryEndDate || null,
        };
        await downloadPost("/export/download", body, `${reportType}.${summaryFormat}`);
        setMessage({ ok: true, text: t("downloadSuccess") });
      } catch {
        setMessage({ ok: false, text: t("downloadError") });
      } finally {
        setDownloading(null);
      }
    },
    [summaryFormat, summaryStartDate, summaryEndDate, t]
  );

  /* ── Custom report state ──────────────────────────────────────── */
  const [customName, setCustomName] = useState("");
  const [customFormat, setCustomFormat] = useState<ExportFormat>("xlsx");
  const [customSources, setCustomSources] = useState<ReportType[]>([]);
  const [customStartDate, setCustomStartDate] = useState("");
  const [customEndDate, setCustomEndDate] = useState("");
  const [buildingCustom, setBuildingCustom] = useState(false);

  const toggleCustomSource = (src: ReportType) => {
    setCustomSources((prev) =>
      prev.includes(src) ? prev.filter((s) => s !== src) : [...prev, src]
    );
  };

  const handleCustomExport = useCallback(async () => {
    if (!customName.trim() || customSources.length === 0) return;
    setBuildingCustom(true);
    setMessage(null);
    try {
      const body = {
        name: customName,
        data_sources: customSources,
        format: customFormat,
        start_date: customStartDate || null,
        end_date: customEndDate || null,
      };
      await downloadPost("/export/custom", body, `custom_report.${customFormat}`);
      setMessage({ ok: true, text: t("downloadSuccess") });
    } catch {
      setMessage({ ok: false, text: t("downloadError") });
    } finally {
      setBuildingCustom(false);
    }
  }, [customName, customSources, customFormat, customStartDate, customEndDate, t]);

  /* ── Scheduled report form ─────────────────────────────────────── */
  const [showScheduleForm, setShowScheduleForm] = useState(false);
  const [schedName, setSchedName] = useState("");
  const [schedType, setSchedType] = useState<ReportType>("contacts");
  const [schedFormat, setSchedFormat] = useState<ExportFormat>("xlsx");
  const [schedFreq, setSchedFreq] = useState<"daily" | "weekly" | "monthly">("weekly");
  const [schedRecipients, setSchedRecipients] = useState("");
  const [creatingSchedule, setCreatingSchedule] = useState(false);

  const handleCreateSchedule = useCallback(async () => {
    if (!schedName.trim()) return;
    setCreatingSchedule(true);
    setMessage(null);
    try {
      const body = {
        name: schedName,
        report_type: schedType,
        format: schedFormat,
        frequency: schedFreq,
        recipients: schedRecipients
          .split(",")
          .map((e) => e.trim())
          .filter(Boolean),
        is_active: true,
      };
      const res = await apiPost("/export/schedules", body);
      if (res.ok) {
        setMessage({ ok: true, text: t("scheduleCreated") });
        setShowScheduleForm(false);
        setSchedName("");
        setSchedRecipients("");
        schedules.refetch();
      } else {
        setMessage({ ok: false, text: t("scheduleError") });
      }
    } catch {
      setMessage({ ok: false, text: t("scheduleError") });
    } finally {
      setCreatingSchedule(false);
    }
  }, [schedName, schedType, schedFormat, schedFreq, schedRecipients, schedules, t]);

  const handleDeleteSchedule = useCallback(
    async (id: string) => {
      setMessage(null);
      try {
        await apiDelete(`/export/schedules/${id}`);
        schedules.refetch();
        setMessage({ ok: true, text: t("scheduleDeleted") });
      } catch {
        setMessage({ ok: false, text: t("scheduleError") });
      }
    },
    [schedules, t]
  );

  /* ── Tab buttons ─────────────────────────────────────────────── */
  const tabs = [
    { key: "quick" as const, label: t("tabQuick"), icon: "⚡" },
    { key: "summary" as const, label: t("tabSummary"), icon: "📈" },
    { key: "custom" as const, label: t("tabCustom"), icon: "🛠️" },
    { key: "scheduled" as const, label: t("tabScheduled"), icon: "🕐" },
  ];

  return (
    <div className="space-y-6">
      {/* ── Header ───────────────────────────────────────────── */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-800">{t("title")}</h1>
          <p className="text-sm text-gray-500 mt-1">{t("subtitle")}</p>
        </div>
      </div>

      {/* ── Message ──────────────────────────────────────────── */}
      {message && (
        <div
          className={`p-3 rounded-lg text-sm ${
            message.ok ? "bg-green-50 text-green-700" : "bg-red-50 text-red-700"
          }`}
        >
          {message.text}
        </div>
      )}

      {/* ── KPI cards ────────────────────────────────────────── */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard
          title={t("kpiDataExports")}
          value={fmt.digits(QUICK_EXPORTS.length)}
          icon="📥"
          color="text-blue-600"
        />
        <StatCard
          title={t("kpiSummaryReports")}
          value={fmt.digits(SUMMARY_REPORTS.length)}
          icon="📈"
          color="text-emerald-600"
        />
        <StatCard
          title={t("kpiScheduledReports")}
          value={fmt.digits(scheduleList.length)}
          icon="🕐"
          color="text-purple-600"
        />
        <StatCard
          title={t("kpiFormats")}
          value="CSV / Excel / PDF"
          icon="📊"
          color="text-amber-600"
        />
      </div>

      {/* ── Tab bar ──────────────────────────────────────────── */}
      <div className="flex gap-2 border-b pb-2 overflow-x-auto">
        {tabs.map((tb) => (
          <button
            key={tb.key}
            onClick={() => setTab(tb.key)}
            className={`px-4 py-2 rounded-t-lg text-sm font-medium whitespace-nowrap transition ${
              tab === tb.key
                ? "bg-blue-50 text-blue-700 border-b-2 border-blue-600"
                : "text-gray-500 hover:text-gray-700"
            }`}
          >
            {tb.icon} {tb.label}
          </button>
        ))}
      </div>

      {/* ── TAB: Quick Export ─────────────────────────────────── */}
      {tab === "quick" && (
        <div className="space-y-4">
          {/* Filters row */}
          <div className="bg-white p-4 rounded-lg shadow flex flex-wrap items-end gap-4">
            <div>
              <label className="block text-xs text-gray-500 mb-1">{t("format")}</label>
              <select
                value={quickFormat}
                onChange={(e) => setQuickFormat(e.target.value as ExportFormat)}
                className="border rounded px-3 py-2 text-sm"
              >
                {FORMAT_OPTIONS.filter((f) => f.value !== "pdf").map((f) => (
                  <option key={f.value} value={f.value}>
                    {f.icon} {f.label}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">{t("startDate")}</label>
              <input
                type="date"
                value={quickStartDate}
                onChange={(e) => setQuickStartDate(e.target.value)}
                className="border rounded px-3 py-2 text-sm"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">{t("endDate")}</label>
              <input
                type="date"
                value={quickEndDate}
                onChange={(e) => setQuickEndDate(e.target.value)}
                className="border rounded px-3 py-2 text-sm"
              />
            </div>
          </div>

          {/* Export cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {QUICK_EXPORTS.map((card) => (
              <div
                key={card.key}
                className="bg-white p-5 rounded-lg shadow hover:shadow-md transition cursor-pointer"
                onClick={() => handleQuickExport(card)}
              >
                <div className="flex items-center gap-3 mb-3">
                  <span className="text-3xl">{card.icon}</span>
                  <div>
                    <h3 className="font-bold text-gray-800">{t(`export_${card.key}`)}</h3>
                    <p className="text-xs text-gray-400">{t(`export_${card.key}_desc`)}</p>
                  </div>
                </div>
                <button
                  disabled={downloading === card.key}
                  className="w-full mt-2 bg-blue-600 text-white py-2 rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50 transition"
                >
                  {downloading === card.key ? t("downloading") : t("download")}
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── TAB: Summary Reports ─────────────────────────────── */}
      {tab === "summary" && (
        <div className="space-y-4">
          {/* Format/Date filters */}
          <div className="bg-white p-4 rounded-lg shadow flex flex-wrap items-end gap-4">
            <div>
              <label className="block text-xs text-gray-500 mb-1">{t("format")}</label>
              <select
                value={summaryFormat}
                onChange={(e) => setSummaryFormat(e.target.value as ExportFormat)}
                className="border rounded px-3 py-2 text-sm"
              >
                {FORMAT_OPTIONS.map((f) => (
                  <option key={f.value} value={f.value}>
                    {f.icon} {f.label}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">{t("startDate")}</label>
              <input
                type="date"
                value={summaryStartDate}
                onChange={(e) => setSummaryStartDate(e.target.value)}
                className="border rounded px-3 py-2 text-sm"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">{t("endDate")}</label>
              <input
                type="date"
                value={summaryEndDate}
                onChange={(e) => setSummaryEndDate(e.target.value)}
                className="border rounded px-3 py-2 text-sm"
              />
            </div>
          </div>

          {/* Summary report cards */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            {SUMMARY_REPORTS.map((rpt) => (
              <div
                key={rpt.key}
                className="bg-white p-6 rounded-lg shadow hover:shadow-md transition"
              >
                <div className="text-4xl mb-3">{rpt.icon}</div>
                <h3 className="font-bold text-gray-800 mb-1">{t(`summary_${rpt.key}`)}</h3>
                <p className="text-xs text-gray-400 mb-4">{t(`summary_${rpt.key}_desc`)}</p>
                <button
                  onClick={() => handleSummaryExport(rpt.reportType)}
                  disabled={downloading === rpt.reportType}
                  className="w-full bg-emerald-600 text-white py-2 rounded-lg text-sm font-medium hover:bg-emerald-700 disabled:opacity-50 transition"
                >
                  {downloading === rpt.reportType ? t("downloading") : t("generateReport")}
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── TAB: Custom Report Builder ───────────────────────── */}
      {tab === "custom" && (
        <div className="bg-white p-6 rounded-lg shadow space-y-5">
          <h2 className="text-lg font-bold text-gray-800">{t("customTitle")}</h2>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs text-gray-500 mb-1">{t("reportName")}</label>
              <input
                type="text"
                value={customName}
                onChange={(e) => setCustomName(e.target.value)}
                placeholder={t("reportNamePlaceholder")}
                className="w-full border rounded px-3 py-2 text-sm"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">{t("format")}</label>
              <select
                value={customFormat}
                onChange={(e) => setCustomFormat(e.target.value as ExportFormat)}
                className="border rounded px-3 py-2 text-sm"
              >
                {FORMAT_OPTIONS.filter((f) => f.value !== "pdf").map((f) => (
                  <option key={f.value} value={f.value}>
                    {f.icon} {f.label}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs text-gray-500 mb-1">{t("startDate")}</label>
              <input
                type="date"
                value={customStartDate}
                onChange={(e) => setCustomStartDate(e.target.value)}
                className="w-full border rounded px-3 py-2 text-sm"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">{t("endDate")}</label>
              <input
                type="date"
                value={customEndDate}
                onChange={(e) => setCustomEndDate(e.target.value)}
                className="w-full border rounded px-3 py-2 text-sm"
              />
            </div>
          </div>

          {/* Data sources selection */}
          <div>
            <label className="block text-xs text-gray-500 mb-2">{t("dataSources")}</label>
            <div className="flex flex-wrap gap-2">
              {QUICK_EXPORTS.map((card) => (
                <button
                  key={card.key}
                  onClick={() => toggleCustomSource(card.reportType)}
                  className={`px-4 py-2 rounded-full text-sm border transition ${
                    customSources.includes(card.reportType)
                      ? "bg-blue-600 text-white border-blue-600"
                      : "bg-white text-gray-600 border-gray-300 hover:border-blue-400"
                  }`}
                >
                  {card.icon} {t(`export_${card.key}`)}
                </button>
              ))}
            </div>
            {customSources.length > 0 && (
              <p className="text-xs text-gray-400 mt-2">
                {t("selectedSources", { count: customSources.length })}
              </p>
            )}
          </div>

          {/* Available columns preview */}
          {columns.data && customSources.length > 0 && (
            <div className="border rounded-lg p-4 bg-gray-50">
              <h4 className="text-sm font-medium text-gray-600 mb-2">{t("availableColumns")}</h4>
              {customSources.map((src) => {
                const srcCols = columns.data?.[src] ?? [];
                if (srcCols.length === 0) return null;
                return (
                  <div key={src} className="mb-3">
                    <span className="text-xs font-bold text-gray-500">{src}</span>
                    <div className="flex flex-wrap gap-1 mt-1">
                      {srcCols.map((col) => (
                        <span
                          key={col.key}
                          className="px-2 py-0.5 bg-white border rounded text-xs text-gray-600"
                        >
                          {col.label_fa}
                        </span>
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          <button
            onClick={handleCustomExport}
            disabled={buildingCustom || !customName.trim() || customSources.length === 0}
            className="bg-blue-600 text-white px-6 py-2.5 rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50 transition"
          >
            {buildingCustom ? t("building") : t("buildReport")}
          </button>
        </div>
      )}

      {/* ── TAB: Scheduled Reports ───────────────────────────── */}
      {tab === "scheduled" && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-bold text-gray-800">{t("scheduledTitle")}</h2>
            <button
              onClick={() => setShowScheduleForm(!showScheduleForm)}
              className="bg-purple-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-purple-700 transition"
            >
              {showScheduleForm ? tc("cancel") : t("newSchedule")}
            </button>
          </div>

          {/* Create form */}
          {showScheduleForm && (
            <div className="bg-white p-5 rounded-lg shadow space-y-4 border-2 border-purple-100">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs text-gray-500 mb-1">{t("scheduleName")}</label>
                  <input
                    type="text"
                    value={schedName}
                    onChange={(e) => setSchedName(e.target.value)}
                    placeholder={t("scheduleNamePlaceholder")}
                    className="w-full border rounded px-3 py-2 text-sm"
                  />
                </div>
                <div>
                  <label className="block text-xs text-gray-500 mb-1">{t("reportType")}</label>
                  <select
                    value={schedType}
                    onChange={(e) => setSchedType(e.target.value as ReportType)}
                    className="w-full border rounded px-3 py-2 text-sm"
                  >
                    {QUICK_EXPORTS.map((c) => (
                      <option key={c.reportType} value={c.reportType}>
                        {t(`export_${c.key}`)}
                      </option>
                    ))}
                    {SUMMARY_REPORTS.map((r) => (
                      <option key={r.reportType} value={r.reportType}>
                        {t(`summary_${r.key}`)}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div>
                  <label className="block text-xs text-gray-500 mb-1">{t("format")}</label>
                  <select
                    value={schedFormat}
                    onChange={(e) => setSchedFormat(e.target.value as ExportFormat)}
                    className="border rounded px-3 py-2 text-sm"
                  >
                    {FORMAT_OPTIONS.map((f) => (
                      <option key={f.value} value={f.value}>
                        {f.icon} {f.label}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-xs text-gray-500 mb-1">{t("frequency")}</label>
                  <select
                    value={schedFreq}
                    onChange={(e) => setSchedFreq(e.target.value as "daily" | "weekly" | "monthly")}
                    className="border rounded px-3 py-2 text-sm"
                  >
                    {FREQUENCY_OPTIONS.map((f) => (
                      <option key={f.value} value={f.value}>
                        {t(`freq_${f.key}`)}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-xs text-gray-500 mb-1">{t("recipients")}</label>
                  <input
                    type="text"
                    value={schedRecipients}
                    onChange={(e) => setSchedRecipients(e.target.value)}
                    placeholder={t("recipientsPlaceholder")}
                    className="w-full border rounded px-3 py-2 text-sm"
                  />
                </div>
              </div>

              <button
                onClick={handleCreateSchedule}
                disabled={creatingSchedule || !schedName.trim()}
                className="bg-purple-600 text-white px-6 py-2 rounded-lg text-sm font-medium hover:bg-purple-700 disabled:opacity-50 transition"
              >
                {creatingSchedule ? t("creating") : t("createSchedule")}
              </button>
            </div>
          )}

          {/* Scheduled reports list */}
          {schedules.isLoading ? (
            <p className="text-center text-gray-400 py-8">{tc("loading")}</p>
          ) : scheduleList.length === 0 ? (
            <EmptyState title={t("noSchedules")} />
          ) : (
            <div className="bg-white rounded-lg shadow overflow-hidden">
              <table className="min-w-full text-sm">
                <thead>
                  <tr className="bg-gray-50 text-gray-500 text-xs">
                    <th className="px-4 py-3 text-right">{t("colName")}</th>
                    <th className="px-4 py-3 text-right">{t("colType")}</th>
                    <th className="px-4 py-3 text-right">{t("colFormat")}</th>
                    <th className="px-4 py-3 text-right">{t("colFrequency")}</th>
                    <th className="px-4 py-3 text-right">{t("colRecipients")}</th>
                    <th className="px-4 py-3 text-right">{t("colNextRun")}</th>
                    <th className="px-4 py-3 text-right">{t("colStatus")}</th>
                    <th className="px-4 py-3 text-right">{t("colActions")}</th>
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {scheduleList.map((sched) => (
                    <tr key={sched.id} className="hover:bg-gray-50">
                      <td className="px-4 py-3 font-medium text-gray-800">{sched.name}</td>
                      <td className="px-4 py-3 text-gray-600">{sched.report_type}</td>
                      <td className="px-4 py-3 text-gray-600 uppercase">{sched.format}</td>
                      <td className="px-4 py-3 text-gray-600">{t(`freq_${sched.frequency}`)}</td>
                      <td className="px-4 py-3 text-gray-600 text-xs">
                        {sched.recipients.join(", ") || "—"}
                      </td>
                      <td className="px-4 py-3 text-gray-500 text-xs">
                        {sched.next_run_at ? fmt.date(sched.next_run_at) : "—"}
                      </td>
                      <td className="px-4 py-3">
                        <span
                          className={`px-2 py-0.5 rounded-full text-xs ${
                            sched.is_active
                              ? "bg-green-50 text-green-700"
                              : "bg-gray-100 text-gray-500"
                          }`}
                        >
                          {sched.is_active ? t("active") : t("inactive")}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <button
                          onClick={() => handleDeleteSchedule(sched.id)}
                          className="text-red-500 hover:text-red-700 text-xs"
                        >
                          {tc("delete")}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

