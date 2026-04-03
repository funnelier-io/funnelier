"use client";

import { useState, useRef } from "react";
import { useApi } from "@/lib/hooks";
import { apiPost, uploadFile } from "@/lib/api-client";
import DataTable from "@/components/ui/DataTable";
import { fmtDate, fmtNum } from "@/lib/utils";

interface ScanResult {
  folder: string;
  files: { name: string; size_kb: number; category: string }[];
}

interface ImportHistory {
  id: string;
  file_name: string;
  import_type: string;
  status: string;
  records_imported: number;
  records_failed: number;
  started_at: string;
  completed_at: string | null;
}

interface DataSourceConfig {
  id: string;
  name: string;
  source_type: string;
  description: string | null;
  is_active: boolean;
  last_sync_at: string | null;
  last_sync_status: string | null;
  records_synced: number;
}

interface DataSourceListResponse {
  configs: DataSourceConfig[];
  total_count: number;
}

// Static infrastructure services (always shown)
const INFRA_SOURCES: { name: string; description: string; icon: string; sourceType: string }[] = [
  { name: "PostgreSQL", description: "پایگاه‌داده اصلی", icon: "🐘", sourceType: "postgresql" },
  { name: "Redis", description: "کش و صف پیام", icon: "🔴", sourceType: "redis" },
  { name: "MongoDB", description: "فاکتورها و پرداخت‌ها", icon: "🍃", sourceType: "mongodb" },
  { name: "Kavenegar", description: "سرویس پیامک", icon: "💬", sourceType: "sms_provider" },
  { name: "Asterisk (VoIP)", description: "تلفن اینترنتی", icon: "📞", sourceType: "voip" },
  { name: "فایل‌های Excel", description: "لیست سرنخ‌ها", icon: "📊", sourceType: "file" },
];

const SOURCE_TYPE_ICONS: Record<string, string> = {
  postgresql: "🐘",
  redis: "🔴",
  mongodb: "🍃",
  sms_provider: "💬",
  voip: "📞",
  file: "📊",
  api: "🔗",
  mysql: "🐬",
};

export default function SettingsPage() {
  // ...existing code for scan/upload state...
  const [scanResult, setScanResult] = useState<ScanResult | null>(null);
  const [scanLoading, setScanLoading] = useState(false);
  const [scanError, setScanError] = useState("");
  const [uploadType, setUploadType] = useState<string>("leads");
  const [uploadFile_, setUploadFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadResult, setUploadResult] = useState<{ ok: boolean; message: string } | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const history = useApi<ImportHistory[]>("/import/history");
  const dataSources = useApi<DataSourceListResponse>("/tenants/me/data-sources");

  // Merge API data sources with static infra list
  const apiConfigs = dataSources.data?.configs || [];
  const apiByType = new Map(apiConfigs.map((c) => [c.source_type, c]));

  const mergedSources = INFRA_SOURCES.map((infra) => {
    const apiCfg = apiByType.get(infra.sourceType);
    return {
      name: apiCfg?.name || infra.name,
      description: apiCfg?.description || infra.description,
      icon: SOURCE_TYPE_ICONS[infra.sourceType] || "📦",
      status: apiCfg
        ? apiCfg.is_active ? "connected" as const : "disconnected" as const
        : infra.sourceType === "postgresql" || infra.sourceType === "redis" || infra.sourceType === "file"
          ? "connected" as const
          : "configured" as const,
      lastSyncAt: apiCfg?.last_sync_at || null,
      recordsSynced: apiCfg?.records_synced || 0,
    };
  });

  // Add any API data sources not in the static list
  for (const cfg of apiConfigs) {
    if (!INFRA_SOURCES.some((i) => i.sourceType === cfg.source_type)) {
      mergedSources.push({
        name: cfg.name,
        description: cfg.description || "",
        icon: SOURCE_TYPE_ICONS[cfg.source_type] || "📦",
        status: cfg.is_active ? "connected" : "disconnected",
        lastSyncAt: cfg.last_sync_at,
        recordsSynced: cfg.records_synced,
      });
    }
  }

  const uploadEndpoints: Record<string, { path: string; label: string; accept: string }> = {
    leads: { path: "/import/leads/upload", label: "سرنخ‌ها (Excel)", accept: ".xlsx,.xls" },
    calls: { path: "/import/calls/upload", label: "تماس‌ها (CSV)", accept: ".csv" },
    sms: { path: "/import/sms/upload", label: "پیامک‌ها (CSV)", accept: ".csv" },
    voip: { path: "/import/voip/upload", label: "VoIP (JSON)", accept: ".json,.txt" },
  };

  async function handleUpload() {
    if (!uploadFile_) return;
    setUploading(true);
    setUploadResult(null);
    try {
      const ep = uploadEndpoints[uploadType];
      const res = await uploadFile(ep.path, uploadFile_);
      if (res.ok) {
        setUploadResult({
          ok: true,
          message: `فایل "${uploadFile_.name}" با موفقیت بارگذاری شد`,
        });
        setUploadFile(null);
        if (fileInputRef.current) fileInputRef.current.value = "";
        history.refetch();
      } else {
        setUploadResult({
          ok: false,
          message: (res.data as Record<string, string>)?.detail || "خطا در بارگذاری فایل",
        });
      }
    } catch {
      setUploadResult({ ok: false, message: "خطا در اتصال به سرور" });
    }
    setUploading(false);
  }

  async function handleScan() {
    setScanLoading(true);
    setScanError("");
    try {
      const res = await apiPost<ScanResult>("/import/leads/scan");
      if (res.ok) {
        setScanResult(res.data);
      } else {
        setScanError("خطا در اسکن فایل‌ها");
      }
    } catch {
      setScanError("خطا در اتصال به سرور");
    }
    setScanLoading(false);
  }

  const historyColumns = [
    {
      key: "file_name",
      header: "نام فایل",
      render: (h: ImportHistory) => (
        <span className="text-sm">{h.file_name || "—"}</span>
      ),
    },
    {
      key: "import_type",
      header: "نوع",
      render: (h: ImportHistory) => {
        const labels: Record<string, string> = {
          leads: "سرنخ",
          call_logs: "تماس",
          sms_logs: "پیامک",
          voip: "VoIP",
          invoices: "فاکتور",
        };
        return (
          <span className="text-xs bg-gray-100 px-2 py-0.5 rounded">
            {labels[h.import_type] || h.import_type}
          </span>
        );
      },
    },
    {
      key: "status",
      header: "وضعیت",
      render: (h: ImportHistory) => {
        const colors: Record<string, string> = {
          completed: "bg-green-50 text-green-700",
          running: "bg-blue-50 text-blue-700",
          failed: "bg-red-50 text-red-700",
          pending: "bg-yellow-50 text-yellow-700",
        };
        const labels: Record<string, string> = {
          completed: "انجام شد",
          running: "در حال اجرا",
          failed: "ناموفق",
          pending: "در انتظار",
        };
        return (
          <span
            className={`inline-block px-2 py-0.5 rounded-full text-xs ${colors[h.status] || "bg-gray-50"}`}
          >
            {labels[h.status] || h.status}
          </span>
        );
      },
    },
    {
      key: "records_imported",
      header: "وارد شده",
      render: (h: ImportHistory) => (
        <span className="text-sm text-green-600">{h.records_imported ?? 0}</span>
      ),
    },
    {
      key: "records_failed",
      header: "ناموفق",
      render: (h: ImportHistory) => (
        <span className="text-sm text-red-500">{h.records_failed ?? 0}</span>
      ),
    },
    {
      key: "started_at",
      header: "تاریخ",
      render: (h: ImportHistory) => fmtDate(h.started_at),
    },
  ];

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-bold">تنظیمات</h1>

      {/* Data Sources */}
      <div className="bg-white rounded-lg shadow p-5">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm font-semibold text-gray-700">
            منابع داده
          </h2>
          {dataSources.isLoading && (
            <span className="text-xs text-gray-400">بارگذاری...</span>
          )}
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {mergedSources.map((src) => (
            <DataSourceCard
              key={src.name}
              name={src.name}
              description={src.description}
              status={src.status}
              icon={src.icon}
              lastSyncAt={src.lastSyncAt}
              recordsSynced={src.recordsSynced}
            />
          ))}
        </div>
      </div>

      {/* Lead Scanner */}
      <div className="bg-white rounded-lg shadow p-5">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm font-semibold text-gray-700">
            اسکن فایل‌های سرنخ
          </h2>
          <button
            onClick={handleScan}
            disabled={scanLoading}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700 disabled:opacity-50 transition-colors"
          >
            {scanLoading ? "در حال اسکن..." : "🔍 اسکن پوشه"}
          </button>
        </div>

        {scanError && (
          <div className="text-red-500 text-sm bg-red-50 rounded-lg p-3 mb-3">
            {scanError}
          </div>
        )}

        {scanResult && (
          <div>
            <p className="text-xs text-gray-400 mb-3">
              پوشه: <span dir="ltr" className="font-mono">{scanResult.folder}</span>
              {" — "}
              {scanResult.files.length} فایل یافت شد
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
              {scanResult.files.map((f) => (
                <div
                  key={f.name}
                  className="flex items-center justify-between p-2.5 bg-gray-50 rounded-md text-xs"
                >
                  <span className="truncate ml-2">{f.category}</span>
                  <span className="text-gray-400 shrink-0" dir="ltr">
                    {f.size_kb.toFixed(1)} KB
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* File Upload */}
      <div className="bg-white rounded-lg shadow p-5">
        <h2 className="text-sm font-semibold text-gray-700 mb-4">
          📤 بارگذاری فایل
        </h2>

        {/* Upload Type Tabs */}
        <div className="flex gap-2 mb-4">
          {Object.entries(uploadEndpoints).map(([key, ep]) => (
            <button
              key={key}
              onClick={() => {
                setUploadType(key);
                setUploadFile(null);
                setUploadResult(null);
                if (fileInputRef.current) fileInputRef.current.value = "";
              }}
              className={`px-3 py-1.5 text-xs rounded-lg transition-colors ${
                uploadType === key
                  ? "bg-blue-600 text-white"
                  : "bg-gray-100 text-gray-600 hover:bg-gray-200"
              }`}
            >
              {ep.label}
            </button>
          ))}
        </div>

        {/* Drop zone */}
        <div
          className="border-2 border-dashed border-gray-300 rounded-lg p-6 text-center hover:border-blue-400 transition-colors cursor-pointer"
          onClick={() => fileInputRef.current?.click()}
          onDragOver={(e) => { e.preventDefault(); e.currentTarget.classList.add("border-blue-400", "bg-blue-50"); }}
          onDragLeave={(e) => { e.currentTarget.classList.remove("border-blue-400", "bg-blue-50"); }}
          onDrop={(e) => {
            e.preventDefault();
            e.currentTarget.classList.remove("border-blue-400", "bg-blue-50");
            const file = e.dataTransfer.files[0];
            if (file) setUploadFile(file);
          }}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept={uploadEndpoints[uploadType].accept}
            className="hidden"
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) setUploadFile(file);
            }}
          />
          {uploadFile_ ? (
            <div className="space-y-2">
              <div className="text-2xl">📄</div>
              <div className="text-sm font-medium">{uploadFile_.name}</div>
              <div className="text-xs text-gray-400">
                {(uploadFile_.size / 1024).toFixed(1)} KB
              </div>
            </div>
          ) : (
            <div className="space-y-2">
              <div className="text-3xl text-gray-300">📁</div>
              <div className="text-sm text-gray-500">
                فایل را اینجا بکشید یا کلیک کنید
              </div>
              <div className="text-xs text-gray-400">
                فرمت‌های مجاز: {uploadEndpoints[uploadType].accept}
              </div>
            </div>
          )}
        </div>

        {/* Upload button and result */}
        <div className="mt-4 flex items-center justify-between">
          <button
            onClick={handleUpload}
            disabled={!uploadFile_ || uploading}
            className="px-4 py-2 bg-green-600 text-white text-sm rounded-lg hover:bg-green-700 disabled:opacity-50"
          >
            {uploading ? "در حال بارگذاری..." : "⬆️ بارگذاری"}
          </button>
          {uploadResult && (
            <div
              className={`text-sm px-3 py-1 rounded-lg ${
                uploadResult.ok
                  ? "bg-green-50 text-green-700"
                  : "bg-red-50 text-red-700"
              }`}
            >
              {uploadResult.ok ? "✅" : "❌"} {uploadResult.message}
            </div>
          )}
        </div>
      </div>

      {/* Import History */}
      <div className="bg-white rounded-lg shadow p-5">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm font-semibold text-gray-700">
            تاریخچه واردسازی
          </h2>
          <button
            onClick={history.refetch}
            className="text-xs text-blue-600 hover:text-blue-800"
          >
            🔄 بروزرسانی
          </button>
        </div>

        <DataTable
          columns={historyColumns}
          data={Array.isArray(history.data) ? history.data : []}
          isLoading={history.isLoading}
          emptyMessage="تاریخچه واردسازی موجود نیست"
        />
      </div>
    </div>
  );
}

function DataSourceCard({
  name,
  description,
  status,
  icon,
  lastSyncAt,
  recordsSynced,
}: {
  name: string;
  description: string;
  status: "connected" | "disconnected" | "configured";
  icon: string;
  lastSyncAt?: string | null;
  recordsSynced?: number;
}) {
  const statusConfig = {
    connected: { label: "متصل", color: "bg-green-500", textColor: "text-green-700" },
    disconnected: { label: "قطع", color: "bg-red-500", textColor: "text-red-700" },
    configured: { label: "تنظیم شده", color: "bg-yellow-500", textColor: "text-yellow-700" },
  };

  const cfg = statusConfig[status];

  return (
    <div className="border border-gray-200 rounded-lg p-4 hover:shadow-sm transition-shadow">
      <div className="flex items-center gap-3">
        <span className="text-2xl">{icon}</span>
        <div className="flex-1">
          <h3 className="text-sm font-semibold">{name}</h3>
          <p className="text-xs text-gray-400">{description}</p>
        </div>
        <div className="flex items-center gap-1.5">
          <div className={`w-2 h-2 rounded-full ${cfg.color}`} />
          <span className={`text-xs ${cfg.textColor}`}>{cfg.label}</span>
        </div>
      </div>
      {(lastSyncAt || (recordsSynced != null && recordsSynced > 0)) && (
        <div className="mt-2 pt-2 border-t border-gray-100 flex items-center justify-between text-xs text-gray-400">
          {lastSyncAt && <span>آخرین همگام‌سازی: {fmtDate(lastSyncAt)}</span>}
          {recordsSynced != null && recordsSynced > 0 && (
            <span>{fmtNum(recordsSynced)} رکورد</span>
          )}
        </div>
      )}
    </div>
  );
}

