"use client";

import { useState } from "react";
import { useApi } from "@/lib/hooks";
import StatCard from "@/components/ui/StatCard";
import DataTable from "@/components/ui/DataTable";
import { fmtNum, fmtPercent, fmtDate } from "@/lib/utils";
import type { SMSStats, CallStats, SMSLogListResponse, SMSLog } from "@/types/communications";

const STATUS_LABELS: Record<string, string> = {
  sent: "ارسال شده",
  delivered: "تحویل شده",
  failed: "ناموفق",
  queued: "در صف",
  pending: "در انتظار",
};

const STATUS_COLORS: Record<string, string> = {
  sent: "bg-blue-50 text-blue-700",
  delivered: "bg-green-50 text-green-700",
  failed: "bg-red-50 text-red-700",
  queued: "bg-yellow-50 text-yellow-700",
  pending: "bg-gray-50 text-gray-700",
};

export default function CommunicationsPage() {
  const [page, setPage] = useState(1);
  const pageSize = 20;

  const smsStats = useApi<SMSStats>("/communications/sms/stats");
  const callStats = useApi<CallStats>("/communications/calls/stats");
  const smsLogs = useApi<SMSLogListResponse>(
    `/communications/sms/logs?page=${page}&page_size=${pageSize}`
  );

  const totalPages = smsLogs.data
    ? Math.ceil(smsLogs.data.total_count / pageSize)
    : 0;

  const smsColumns = [
    {
      key: "phone_number",
      header: "شماره",
      render: (l: SMSLog) => (
        <span className="font-mono text-xs" dir="ltr">{l.phone_number}</span>
      ),
    },
    {
      key: "message",
      header: "پیام",
      render: (l: SMSLog) => (
        <span className="text-xs text-gray-600 max-w-xs truncate block">
          {l.message?.substring(0, 50)}
          {l.message?.length > 50 ? "..." : ""}
        </span>
      ),
    },
    {
      key: "status",
      header: "وضعیت",
      render: (l: SMSLog) => (
        <span
          className={`inline-block px-2 py-0.5 rounded-full text-xs ${STATUS_COLORS[l.status] || "bg-gray-50 text-gray-700"}`}
        >
          {STATUS_LABELS[l.status] || l.status}
        </span>
      ),
    },
    {
      key: "delivery_status",
      header: "وضعیت تحویل",
      render: (l: SMSLog) => (
        <span className="text-xs text-gray-500">
          {l.delivery_status || "—"}
        </span>
      ),
    },
    {
      key: "provider",
      header: "ارائه‌دهنده",
      render: (l: SMSLog) => (
        <span className="text-xs">{l.provider || "—"}</span>
      ),
    },
    {
      key: "sent_at",
      header: "تاریخ ارسال",
      render: (l: SMSLog) => fmtDate(l.sent_at),
    },
  ];

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-bold">ارتباطات</h1>

      {/* SMS Stats */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="پیامک ارسالی"
          value={fmtNum(smsStats.data?.total_sent)}
          icon="💬"
          color="text-blue-600"
        />
        <StatCard
          title="تحویل شده"
          value={fmtNum(smsStats.data?.total_delivered)}
          icon="✅"
          color="text-green-600"
        />
        <StatCard
          title="ناموفق"
          value={fmtNum(smsStats.data?.total_failed)}
          icon="❌"
          color="text-red-600"
        />
        <StatCard
          title="نرخ تحویل"
          value={fmtPercent(smsStats.data?.delivery_rate)}
          icon="📊"
          color="text-purple-600"
        />
      </div>

      {/* Call Stats */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="کل تماس‌ها"
          value={fmtNum(callStats.data?.total_calls)}
          icon="📞"
          color="text-amber-600"
        />
        <StatCard
          title="تماس پاسخ داده"
          value={fmtNum(callStats.data?.answered_calls)}
          icon="📲"
          color="text-green-600"
        />
        <StatCard
          title="تماس از دست رفته"
          value={fmtNum(callStats.data?.missed_calls)}
          icon="📵"
          color="text-red-600"
        />
        <StatCard
          title="نرخ پاسخ"
          value={fmtPercent(callStats.data?.answer_rate)}
          icon="📈"
          color="text-blue-600"
          subtitle={
            callStats.data?.average_duration
              ? `میانگین مدت: ${fmtNum(Math.round(callStats.data.average_duration))} ثانیه`
              : undefined
          }
        />
      </div>

      {/* SMS Logs Table */}
      <div className="bg-white rounded-lg shadow p-5">
        <h2 className="text-sm font-semibold text-gray-700 mb-4">
          لاگ پیامک‌ها
        </h2>

        <DataTable
          columns={smsColumns}
          data={smsLogs.data?.logs || []}
          isLoading={smsLogs.isLoading}
          emptyMessage="پیامکی ثبت نشده است"
        />

        {totalPages > 1 && (
          <div className="flex items-center justify-center gap-2 mt-4">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page <= 1}
              className="px-3 py-1 text-sm border rounded-md disabled:opacity-30 hover:bg-gray-50"
            >
              قبلی
            </button>
            <span className="text-sm text-gray-500">
              صفحه {fmtNum(page)} از {fmtNum(totalPages)}
            </span>
            <button
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page >= totalPages}
              className="px-3 py-1 text-sm border rounded-md disabled:opacity-30 hover:bg-gray-50"
            >
              بعدی
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

