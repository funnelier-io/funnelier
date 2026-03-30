"use client";

import { useState, useRef } from "react";
import { useApi } from "@/lib/hooks";
import { api } from "@/lib/api-client";
import StatCard from "@/components/ui/StatCard";
import DataTable from "@/components/ui/DataTable";
import { fmtNum, fmtDate } from "@/lib/utils";

/* ---------- types ---------- */

interface LeadScanFile {
  name: string;
  size_kb: number;
  category: string;
}

interface LeadScanResponse {
  folder: string;
  files: LeadScanFile[];
  total_files: number;
}

interface ImportHistoryItem {
  id: string;
  source_type: string;
  source_name: string;
  status: string;
  total_records: number;
  success_records: number;
  error_records: number;
  started_at: string;
  completed_at: string | null;
  error_message: string | null;
}

interface DataSummary {
  total_contacts: number;
  active_contacts: number;
  blocked_contacts: number;
  by_stage: Record<string, number>;
  by_category: Record<string, number>;
  by_source: Record<string, number>;
  by_segment: Record<string, number>;
}

/* ---------- helpers ---------- */

const STATUS_LABELS: Record<string, { label: string; color: string }> = {
  pending: { label: "در انتظار", color: "bg-gray-100 text-gray-600" },
  running: { label: "در حال اجرا", color: "bg-blue-100 text-blue-700" },
  completed: { label: "تکمیل شده", color: "bg-green-100 text-green-700" },
  failed: { label: "ناموفق", color: "bg-red-100 text-red-700" },
};

/* ---------- page ---------- */

export default function ImportsPage() {
  const [activeTab, setActiveTab] = useState<"scan" | "history" | "upload">(
    "scan"
  );
  const [importing, setImporting] = useState(false);
  const [importResult, setImportResult] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const scan = useApi<LeadScanResponse>("/import/leads/scan");
  const history = useApi<ImportHistoryItem[]>("/import/history");
  const stats = useApi<DataSummary>("/leads/stats");

  /* ---- upload handler ---- */
  async function handleFileUpload() {
    const file = fileInputRef.current?.files?.[0];
    if (!file) return;

    setImporting(true);
    setImportResult(null);

    const formData = new FormData();
    formData.append("file", file);

    try {
      const res = await fetch("/api/v1/import/leads/upload", {
        method: "POST",
        headers: {
          Authorization: `Bearer ${localStorage.getItem("token")}`,
        },
        body: formData,
      });
      const data = await res.json();
      if (res.ok) {
        setImportResult(
          `✅ وارد شد: ${data.imported ?? data.success_count ?? 0} | خطا: ${data.errors ?? data.error_count ?? 0}`
        );
        scan.refetch();
        history.refetch();
        stats.refetch();
      } else {
        setImportResult(`❌ ${data.detail || "خطا در واردسازی"}`);
      }
    } catch {
      setImportResult("❌ خطا در ارتباط با سرور");
    } finally {
      setImporting(false);
    }
  }

  /* ---- trigger pipeline ---- */
  async function handleRunPipeline() {
    setImporting(true);
    setImportResult(null);
    try {
      const res = await api("POST", "/import/leads/scan-and-import");
      if (res.ok) {
        setImportResult("✅ واردسازی از فایل‌های موجود با موفقیت انجام شد");
        scan.refetch();
        history.refetch();
        stats.refetch();
      } else {
        setImportResult(`❌ ${(res.data as Record<string,string>)?.detail || "خطا"}`);
      }
    } catch {
      setImportResult("❌ خطا در اجرای واردسازی");
    } finally {
      setImporting(false);
    }
  }

  /* ---- scan columns ---- */
  const scanColumns = [
    {
      key: "name",
      header: "نام فایل",
      render: (f: LeadScanFile) => (
        <span className="text-sm font-medium" dir="rtl">
          {f.name}
        </span>
      ),
    },
    {
      key: "category",
      header: "دسته‌بندی",
      render: (f: LeadScanFile) => (
        <span className="px-2 py-0.5 rounded-full text-xs bg-purple-50 text-purple-700">
          {f.category}
        </span>
      ),
    },
    {
      key: "size_kb",
      header: "حجم",
      render: (f: LeadScanFile) => `${f.size_kb.toFixed(1)} KB`,
    },
  ];

  const historyColumns = [
    {
      key: "source_name",
      header: "منبع",
      render: (h: ImportHistoryItem) => h.source_name || h.source_type,
    },
    {
      key: "status",
      header: "وضعیت",
      render: (h: ImportHistoryItem) => {
        const cfg = STATUS_LABELS[h.status] || STATUS_LABELS.pending;
        return (
          <span className={`px-2 py-0.5 rounded-full text-xs ${cfg.color}`}>
            {cfg.label}
          </span>
        );
      },
    },
    {
      key: "total_records",
      header: "کل رکوردها",
      render: (h: ImportHistoryItem) => fmtNum(h.total_records),
    },
    {
      key: "success_records",
      header: "موفق",
      render: (h: ImportHistoryItem) => (
        <span className="text-green-600">{fmtNum(h.success_records)}</span>
      ),
    },
    {
      key: "error_records",
      header: "خطا",
      render: (h: ImportHistoryItem) => (
        <span className="text-red-600">{fmtNum(h.error_records)}</span>
      ),
    },
    {
      key: "started_at",
      header: "تاریخ",
      render: (h: ImportHistoryItem) => fmtDate(h.started_at),
    },
  ];

  const topCategories = stats.data?.by_category
    ? Object.entries(stats.data.by_category)
        .sort((a, b) => b[1] - a[1])
        .slice(0, 10)
    : [];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold">واردسازی داده</h1>
        <div className="flex gap-2">
          <button
            onClick={handleRunPipeline}
            disabled={importing}
            className="px-4 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors"
          >
            {importing ? "در حال اجرا..." : "🔄 اجرای واردسازی"}
          </button>
        </div>
      </div>

      {/* Stats */}
      {stats.data && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard
            title="کل مخاطبین"
            value={fmtNum(stats.data.total_contacts)}
            icon="📋"
            color="text-blue-600"
          />
          <StatCard
            title="دسته‌بندی‌ها"
            value={fmtNum(Object.keys(stats.data.by_category).length)}
            icon="🏷️"
            color="text-purple-600"
          />
          <StatCard
            title="فایل‌های موجود"
            value={fmtNum(scan.data?.total_files)}
            icon="📂"
            color="text-amber-600"
          />
          <StatCard
            title="بخش‌بندی‌ها"
            value={fmtNum(Object.keys(stats.data.by_segment).length)}
            icon="🎯"
            color="text-green-600"
          />
        </div>
      )}

      {/* Import result banner */}
      {importResult && (
        <div
          className={`p-3 rounded-lg text-sm ${
            importResult.startsWith("✅")
              ? "bg-green-50 text-green-700"
              : "bg-red-50 text-red-700"
          }`}
        >
          {importResult}
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-1 bg-gray-100 p-1 rounded-lg w-fit">
        {(
          [
            { key: "scan", label: "📂 فایل‌های موجود" },
            { key: "upload", label: "📤 آپلود فایل" },
            { key: "history", label: "📜 تاریخچه" },
          ] as const
        ).map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`px-4 py-2 text-sm rounded-md transition-colors ${
              activeTab === tab.key
                ? "bg-white shadow text-blue-700 font-medium"
                : "text-gray-600 hover:text-gray-800"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      {activeTab === "scan" && (
        <div className="bg-white rounded-lg shadow p-5">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-semibold text-gray-700">
              فایل‌های سرنخ در پوشه leads-numbers
            </h2>
            <span className="text-xs text-gray-400">
              {scan.data?.folder}
            </span>
          </div>
          <DataTable
            columns={scanColumns}
            data={scan.data?.files || []}
            isLoading={scan.isLoading}
            emptyMessage="فایلی یافت نشد"
          />
        </div>
      )}

      {activeTab === "upload" && (
        <div className="bg-white rounded-lg shadow p-5">
          <h2 className="text-sm font-semibold text-gray-700 mb-4">
            آپلود فایل اکسل سرنخ
          </h2>
          <div className="border-2 border-dashed border-gray-300 rounded-lg p-8 text-center">
            <div className="text-4xl mb-3">📤</div>
            <p className="text-sm text-gray-500 mb-4">
              فایل اکسل (.xlsx) حاوی شماره تماس سرنخ‌ها را انتخاب کنید
            </p>
            <input
              ref={fileInputRef}
              type="file"
              accept=".xlsx,.xls,.csv"
              className="hidden"
              onChange={handleFileUpload}
            />
            <button
              onClick={() => fileInputRef.current?.click()}
              disabled={importing}
              className="px-6 py-2.5 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors"
            >
              {importing ? "در حال واردسازی..." : "انتخاب فایل"}
            </button>
          </div>
        </div>
      )}

      {activeTab === "history" && (
        <div className="bg-white rounded-lg shadow p-5">
          <h2 className="text-sm font-semibold text-gray-700 mb-4">
            تاریخچه واردسازی
          </h2>
          <DataTable
            columns={historyColumns}
            data={history.data || []}
            isLoading={history.isLoading}
            emptyMessage="تاریخچه‌ای موجود نیست"
          />
        </div>
      )}

      {/* Top Categories */}
      {topCategories.length > 0 && (
        <div className="bg-white rounded-lg shadow p-5">
          <h2 className="text-sm font-semibold text-gray-700 mb-4">
            ۱۰ دسته‌بندی برتر
          </h2>
          <div className="space-y-2">
            {topCategories.map(([cat, count]) => {
              const pct =
                (count / (stats.data?.total_contacts || 1)) * 100;
              return (
                <div key={cat} className="flex items-center gap-3">
                  <span className="text-xs text-gray-700 w-48 truncate text-right">
                    {cat}
                  </span>
                  <div className="flex-1 h-5 bg-gray-100 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-blue-500 rounded-full"
                      style={{ width: `${Math.max(pct, 0.5)}%` }}
                    />
                  </div>
                  <span className="text-xs text-gray-500 w-20 text-left" dir="ltr">
                    {fmtNum(count)} ({pct.toFixed(1)}%)
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

