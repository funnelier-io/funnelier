"use client";

import { useState } from "react";
import { useApi } from "@/lib/hooks";
import StatCard from "@/components/ui/StatCard";
import DataTable from "@/components/ui/DataTable";
import { fmtNum, fmtPercent, fmtDate } from "@/lib/utils";
import type {
  SMSStats,
  CallStats,
  SMSLogListResponse,
  SMSLog,
  CallLogListResponse,
  CallLog,
} from "@/types/communications";

const SMS_STATUS_LABELS: Record<string, string> = {
  sent: "ارسال شده",
  delivered: "تحویل شده",
  failed: "ناموفق",
  queued: "در صف",
  pending: "در انتظار",
};
const SMS_STATUS_COLORS: Record<string, string> = {
  sent: "bg-blue-50 text-blue-700",
  delivered: "bg-green-50 text-green-700",
  failed: "bg-red-50 text-red-700",
  queued: "bg-yellow-50 text-yellow-700",
  pending: "bg-gray-50 text-gray-700",
};

const CALL_TYPE_LABELS: Record<string, string> = {
  outgoing: "خروجی",
  incoming: "ورودی",
  missed: "از دست رفته",
};

function fmtDuration(seconds: number): string {
  if (!seconds) return "—";
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return m > 0 ? `${m}:${String(s).padStart(2, "0")}` : `${s}s`;
}

export default function CommunicationsPage() {
  const [tab, setTab] = useState<"calls" | "sms">("calls");
  const [callPage, setCallPage] = useState(1);
  const [smsPage, setSmsPage] = useState(1);
  const pageSize = 20;

  const smsStats = useApi<SMSStats>("/communications/sms/stats");
  const callStats = useApi<CallStats>("/communications/calls/stats");

  const calls = useApi<CallLogListResponse>(
    tab === "calls"
      ? `/communications/calls?page=${callPage}&page_size=${pageSize}`
      : null
  );
  const smsLogs = useApi<SMSLogListResponse>(
    tab === "sms"
      ? `/communications/sms/logs?page=${smsPage}&page_size=${pageSize}`
      : null
  );

  const callTotalPages = calls.data
    ? Math.ceil(calls.data.total_count / pageSize)
    : 0;
  const smsTotalPages = smsLogs.data
    ? Math.ceil(smsLogs.data.total_count / pageSize)
    : 0;

  const callColumns = [
    {
      key: "phone_number",
      header: "شماره",
      render: (c: CallLog) => (
        <span className="font-mono text-xs" dir="ltr">{c.phone_number}</span>
      ),
    },
    {
      key: "contact_name",
      header: "نام",
      render: (c: CallLog) => c.contact_name || "—",
    },
    {
      key: "call_type",
      header: "نوع",
      render: (c: CallLog) => {
        const label = CALL_TYPE_LABELS[c.call_type] || c.call_type;
        const color =
          c.call_type === "incoming"
            ? "bg-green-50 text-green-700"
            : c.call_type === "missed"
              ? "bg-red-50 text-red-700"
              : "bg-blue-50 text-blue-700";
        return (
          <span className={`px-2 py-0.5 rounded-full text-xs ${color}`}>{label}</span>
        );
      },
    },
    {
      key: "duration_seconds",
      header: "مدت",
      render: (c: CallLog) => (
        <span dir="ltr" className="text-xs">{fmtDuration(c.duration_seconds)}</span>
      ),
    },
    {
      key: "is_successful",
      header: "وضعیت",
      render: (c: CallLog) =>
        c.is_successful ? (
          <span className="text-green-600 text-xs font-medium">✓ موفق</span>
        ) : c.is_answered ? (
          <span className="text-amber-600 text-xs">پاسخ داده</span>
        ) : (
          <span className="text-gray-400 text-xs">بدون پاسخ</span>
        ),
    },
    {
      key: "salesperson_name",
      header: "فروشنده",
      render: (c: CallLog) => c.salesperson_name || "—",
    },
    {
      key: "call_time",
      header: "تاریخ",
      render: (c: CallLog) => fmtDate(c.call_time),
    },
  ];

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
          {l.message?.substring(0, 50)}{l.message && l.message.length > 50 ? "..." : ""}
        </span>
      ),
    },
    {
      key: "status",
      header: "وضعیت",
      render: (l: SMSLog) => (
        <span className={`inline-block px-2 py-0.5 rounded-full text-xs ${SMS_STATUS_COLORS[l.status] || "bg-gray-50 text-gray-700"}`}>
          {SMS_STATUS_LABELS[l.status] || l.status}
        </span>
      ),
    },
    {
      key: "provider",
      header: "ارائه‌دهنده",
      render: (l: SMSLog) => <span className="text-xs">{l.provider || "—"}</span>,
    },
    {
      key: "sent_at",
      header: "تاریخ",
      render: (l: SMSLog) => fmtDate(l.sent_at),
    },
  ];

  function Pagination({ page, totalPages, setPage }: { page: number; totalPages: number; setPage: (fn: (p: number) => number) => void }) {
    if (totalPages <= 1) return null;
    return (
      <div className="flex items-center justify-center gap-2 mt-4">
        <button onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page <= 1} className="px-3 py-1 text-sm border rounded-md disabled:opacity-30 hover:bg-gray-50">قبلی</button>
        <span className="text-sm text-gray-500">صفحه {fmtNum(page)} از {fmtNum(totalPages)}</span>
        <button onClick={() => setPage((p) => Math.min(totalPages, p + 1))} disabled={page >= totalPages} className="px-3 py-1 text-sm border rounded-md disabled:opacity-30 hover:bg-gray-50">بعدی</button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-bold">ارتباطات</h1>

      {/* Call Stats */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard title="کل تماس‌ها" value={fmtNum(callStats.data?.total_calls)} icon="📞" color="text-blue-600" />
        <StatCard title="تماس پاسخ داده" value={fmtNum(callStats.data?.total_answered)} icon="📲" color="text-green-600" subtitle={`نرخ پاسخ: ${fmtPercent(callStats.data?.answer_rate)}`} />
        <StatCard title="تماس موفق (≥۹۰ ثانیه)" value={fmtNum(callStats.data?.total_successful)} icon="✅" color="text-emerald-600" subtitle={`نرخ موفقیت: ${fmtPercent(callStats.data?.success_rate)}`} />
        <StatCard title="مدت کل" value={callStats.data?.total_duration ? `${Math.floor(callStats.data.total_duration / 3600)} ساعت` : "—"} icon="⏱️" color="text-purple-600" subtitle={callStats.data?.average_duration ? `میانگین: ${fmtNum(Math.round(callStats.data.average_duration))} ثانیه` : undefined} />
      </div>

      {/* SMS Stats */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard title="پیامک ارسالی" value={fmtNum(smsStats.data?.total_sent)} icon="💬" color="text-blue-500" />
        <StatCard title="تحویل شده" value={fmtNum(smsStats.data?.total_delivered)} icon="✅" color="text-green-500" />
        <StatCard title="ناموفق" value={fmtNum(smsStats.data?.total_failed)} icon="❌" color="text-red-500" />
        <StatCard title="نرخ تحویل" value={fmtPercent(smsStats.data?.delivery_rate)} icon="📊" color="text-purple-500" />
      </div>

      {/* Tabs */}
      <div className="flex gap-1 bg-gray-100 p-1 rounded-lg w-fit">
        <button onClick={() => setTab("calls")} className={`px-4 py-2 text-sm rounded-md transition-colors ${tab === "calls" ? "bg-white shadow text-blue-700 font-medium" : "text-gray-600 hover:text-gray-800"}`}>
          📞 تماس‌ها ({fmtNum(callStats.data?.total_calls)})
        </button>
        <button onClick={() => setTab("sms")} className={`px-4 py-2 text-sm rounded-md transition-colors ${tab === "sms" ? "bg-white shadow text-blue-700 font-medium" : "text-gray-600 hover:text-gray-800"}`}>
          💬 پیامک‌ها ({fmtNum(smsStats.data?.total_sent)})
        </button>
      </div>

      {/* Calls Table */}
      {tab === "calls" && (
        <div className="bg-white rounded-lg shadow p-5">
          <h2 className="text-sm font-semibold text-gray-700 mb-4">لاگ تماس‌ها</h2>
          <DataTable columns={callColumns} data={calls.data?.calls || []} isLoading={calls.isLoading} emptyMessage="تماسی ثبت نشده است" />
          <Pagination page={callPage} totalPages={callTotalPages} setPage={setCallPage} />
        </div>
      )}

      {/* SMS Table */}
      {tab === "sms" && (
        <div className="bg-white rounded-lg shadow p-5">
          <h2 className="text-sm font-semibold text-gray-700 mb-4">لاگ پیامک‌ها</h2>
          <DataTable columns={smsColumns} data={smsLogs.data?.logs || []} isLoading={smsLogs.isLoading} emptyMessage="پیامکی ثبت نشده است" />
          <Pagination page={smsPage} totalPages={smsTotalPages} setPage={setSmsPage} />
        </div>
      )}
    </div>
  );
}
