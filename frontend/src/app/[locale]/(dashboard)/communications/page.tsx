"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { useFormat } from "@/lib/use-format";
import { formatNumber, formatDuration as fmtDurLocale } from "@/lib/format";
import { useApi, useDebounce } from "@/lib/hooks";
import StatCard from "@/components/ui/StatCard";
import DataTable from "@/components/ui/DataTable";

import type {
  SMSStats, SMSBalance, CallStats, SMSLogListResponse, SMSLog, CallLogListResponse, CallLog,
} from "@/types/communications";

function fmtDuration(seconds: number): string {
  if (!seconds) return "\u2014";
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return m > 0 ? `${m}:${String(s).padStart(2, "0")}` : `${s}s`;
}

function fmtCost(cost: number, unit: string, locale: string): string {
  if (!cost) return "\u2014";
  return `${formatNumber(cost, locale)} ${unit}`;
}

function SMSBalanceCard({ balance, t, tc }: { balance: SMSBalance | undefined; t: ReturnType<typeof useTranslations>; tc: ReturnType<typeof useTranslations> }) {
  const fmt = useFormat();
  if (!balance) return null;
  const balanceStr = balance.balance != null ? fmt.number(Math.round(balance.balance)) : "\u2014";
  return (
    <div className={`rounded-lg border p-4 ${balance.is_low ? "border-red-200 bg-red-50" : "border-green-200 bg-green-50"}`}>
      <div className="flex items-center justify-between">
        <div>
          <p className="text-xs text-gray-500">{t("balance")}</p>
          <p className="text-lg font-bold mt-1" dir="ltr">
            {balanceStr}{" "}
            <span className="text-sm font-normal text-gray-500">
              {balance.currency === "toman" ? tc("currency.toman") : balance.currency}
            </span>
          </p>
          <p className="text-xs text-gray-400 mt-0.5">{balance.provider}</p>
        </div>
        <span className="text-3xl">{balance.is_low ? "\u26a0\ufe0f" : "\U0001f4b3"}</span>
      </div>
      {balance.is_low && (
        <p className="text-xs text-red-600 mt-2 font-medium">{t("balanceLow")}</p>
      )}
    </div>
  );
}

export default function CommunicationsPage() {
  const t = useTranslations("communications");
  const fmt = useFormat();
  const tc = useTranslations("common");
  const tss = useTranslations("smsStatuses");
  const tct = useTranslations("callTypes");
  const [tab, setTab] = useState<"calls" | "sms">("calls");
  const [callPage, setCallPage] = useState(1);
  const [smsPage, setSmsPage] = useState(1);
  const [search, setSearch] = useState("");
  const [callTypeFilter, setCallTypeFilter] = useState<string>("all");
  const [smsStatusFilter, setSmsStatusFilter] = useState<string>("all");
  const pageSize = 20;

  const debouncedSearch = useDebounce(search, 300);
  const smsStats = useApi<SMSStats>("/communications/sms/stats");
  const callStats = useApi<CallStats>("/communications/calls/stats");
  const smsBalance = useApi<SMSBalance>("/communications/sms/balance");

  let callsPath = `/communications/calls?page=${callPage}&page_size=${pageSize}`;
  if (debouncedSearch) callsPath += `&search=${encodeURIComponent(debouncedSearch)}`;
  if (callTypeFilter !== "all") callsPath += `&call_type=${callTypeFilter}`;

  let smsPath = `/communications/sms/logs?page=${smsPage}&page_size=${pageSize}`;
  if (debouncedSearch) smsPath += `&search=${encodeURIComponent(debouncedSearch)}`;
  if (smsStatusFilter !== "all") smsPath += `&status=${smsStatusFilter}`;

  const calls = useApi<CallLogListResponse>(tab === "calls" ? callsPath : null);
  const smsLogs = useApi<SMSLogListResponse>(tab === "sms" ? smsPath : null);
  const callTotalPages = calls.data ? Math.ceil(calls.data.total_count / pageSize) : 0;
  const smsTotalPages = smsLogs.data ? Math.ceil(smsLogs.data.total_count / pageSize) : 0;

  const SMS_STATUS_COLORS: Record<string, string> = {
    sent: "bg-blue-50 text-blue-700", delivered: "bg-green-50 text-green-700",
    failed: "bg-red-50 text-red-700", queued: "bg-yellow-50 text-yellow-700",
    pending: "bg-gray-50 text-gray-700",
  };

  const callColumns = [
    { key: "phone_number", header: t("columns.phone"), render: (c: CallLog) => <span className="font-mono text-xs" dir="ltr">{c.phone_number}</span> },
    { key: "contact_name", header: t("columns.name"), render: (c: CallLog) => c.contact_name || "\u2014" },
    {
      key: "call_type", header: t("columns.type"),
      render: (c: CallLog) => {
        const label = tct(c.call_type as "outgoing" | "incoming" | "missed");
        const color = c.call_type === "incoming" ? "bg-green-50 text-green-700" : c.call_type === "missed" ? "bg-red-50 text-red-700" : "bg-blue-50 text-blue-700";
        return <span className={`px-2 py-0.5 rounded-full text-xs ${color}`}>{label}</span>;
      },
    },
    { key: "duration_seconds", header: t("columns.duration"), render: (c: CallLog) => <span dir="ltr" className="text-xs">{fmtDuration(c.duration_seconds)}</span> },
    {
      key: "is_successful", header: t("columns.status"),
      render: (c: CallLog) =>
        c.is_successful ? <span className="text-green-600 text-xs font-medium">{t("successful")}</span>
        : c.is_answered ? <span className="text-amber-600 text-xs">{t("answeredStatus")}</span>
        : <span className="text-gray-400 text-xs">{t("noAnswer")}</span>,
    },
    { key: "salesperson_name", header: t("columns.salesperson"), render: (c: CallLog) => c.salesperson_name || "\u2014" },
    { key: "call_time", header: t("columns.date"), render: (c: CallLog) => fmt.date(c.call_time) },
  ];

  const smsColumns = [
    { key: "phone_number", header: t("columns.phone"), render: (l: SMSLog) => <span className="font-mono text-xs" dir="ltr">{l.phone_number}</span> },
    {
      key: "message", header: t("columns.message"),
      render: (l: SMSLog) => {
        const text = l.message || l.content || "";
        return <span className="text-xs text-gray-600 max-w-xs truncate block">{text.substring(0, 50)}{text.length > 50 ? "..." : ""}</span>;
      },
    },
    {
      key: "status", header: t("columns.status"),
      render: (l: SMSLog) => (
        <span className={`inline-block px-2 py-0.5 rounded-full text-xs ${SMS_STATUS_COLORS[l.status] || "bg-gray-50 text-gray-700"}`}>
          {tss(l.status as "sent" | "delivered" | "failed" | "queued" | "pending")}
        </span>
      ),
    },
    { key: "cost", header: t("columns.cost"), render: (l: SMSLog) => <span className="text-xs text-gray-500" dir="ltr">{l.cost ? fmtCost(l.cost, t("costUnit"), fmt.locale) : "\u2014"}</span> },
    { key: "provider", header: t("columns.provider"), render: (l: SMSLog) => <span className="text-xs">{l.provider || l.provider_name || "\u2014"}</span> },
    { key: "sent_at", header: t("columns.date"), render: (l: SMSLog) => fmt.date(l.sent_at) },
  ];

  function Pagination({ page, totalPages, setPage }: { page: number; totalPages: number; setPage: (fn: (p: number) => number) => void }) {
    if (totalPages <= 1) return null;
    return (
      <div className="flex items-center justify-center gap-2 mt-4">
        <button onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page <= 1} className="px-3 py-1 text-sm border rounded-md disabled:opacity-30 hover:bg-gray-50">{tc("previous")}</button>
        <span className="text-sm text-gray-500">{tc("page", { current: fmt.number(page), total: fmt.number(totalPages) })}</span>
        <button onClick={() => setPage((p) => Math.min(totalPages, p + 1))} disabled={page >= totalPages} className="px-3 py-1 text-sm border rounded-md disabled:opacity-30 hover:bg-gray-50">{tc("next")}</button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-bold">{t("title")}</h1>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
        <div className="lg:col-span-1">
          <SMSBalanceCard balance={smsBalance.data ?? undefined} t={t} tc={tc} />
        </div>
        <StatCard title={t("totalCalls")} value={fmt.number(callStats.data?.total_calls)} icon="\U0001f4de" color="text-blue-600" />
        <StatCard title={t("answeredCalls")} value={fmt.number(callStats.data?.total_answered)} icon="\U0001f4f2" color="text-green-600" />
        <StatCard title={t("successfulCalls")} value={fmt.number(callStats.data?.total_successful)} icon="\u2705" color="text-emerald-600" />
        <StatCard title={t("totalDuration")} value={callStats.data?.total_duration ? `${Math.floor(callStats.data.total_duration / 3600)} ${tc("time.hours")}` : "\u2014"} icon="\u23f1\ufe0f" color="text-purple-600" subtitle={callStats.data?.average_duration ? t("avgDuration", { seconds: String(Math.round(callStats.data.average_duration)) }) : undefined} />
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard title={t("smsSent")} value={fmt.number(smsStats.data?.total_sent)} icon="\U0001f4ac" color="text-blue-500" />
        <StatCard title={t("smsDelivered")} value={fmt.number(smsStats.data?.total_delivered)} icon="\u2705" color="text-green-500" />
        <StatCard title={t("smsFailed")} value={fmt.number(smsStats.data?.total_failed)} icon="\u274c" color="text-red-500" />
        <StatCard title={t("deliveryRate")} value={fmt.percent(smsStats.data?.delivery_rate)} icon="\U0001f4ca" color="text-purple-500" />
      </div>

      <div className="flex gap-1 bg-gray-100 p-1 rounded-lg w-fit">
        <button onClick={() => setTab("calls")} className={`px-4 py-2 text-sm rounded-md transition-colors ${tab === "calls" ? "bg-white shadow text-blue-700 font-medium" : "text-gray-600 hover:text-gray-800"}`}>
          {t("callsTab", { count: fmt.number(callStats.data?.total_calls) })}
        </button>
        <button onClick={() => setTab("sms")} className={`px-4 py-2 text-sm rounded-md transition-colors ${tab === "sms" ? "bg-white shadow text-blue-700 font-medium" : "text-gray-600 hover:text-gray-800"}`}>
          {t("smsTab", { count: fmt.number(smsStats.data?.total_sent) })}
        </button>
      </div>

      {tab === "calls" && (
        <div className="bg-white rounded-lg shadow p-5">
          <div className="flex flex-wrap items-center gap-3 mb-4">
            <h2 className="text-sm font-semibold text-gray-700 ml-auto">{t("callLog")}</h2>
            <select value={callTypeFilter} onChange={(e) => { setCallTypeFilter(e.target.value); setCallPage(1); }} className="px-3 py-1.5 border border-gray-300 rounded-lg text-xs bg-white focus:outline-none focus:ring-2 focus:ring-blue-500">
              <option value="all">{t("allTypes")}</option>
              <option value="outgoing">{tct("outgoing")}</option>
              <option value="incoming">{tct("incoming")}</option>
              <option value="missed">{tct("missed")}</option>
            </select>
            <input type="text" value={search} onChange={(e) => { setSearch(e.target.value); setCallPage(1); setSmsPage(1); }} placeholder={t("searchPhoneOrName")} className="px-3 py-1.5 border border-gray-300 rounded-lg text-sm w-52 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent" />
          </div>
          <DataTable columns={callColumns} data={calls.data?.calls || []} isLoading={calls.isLoading} emptyMessage={t("noCalls")} />
          <Pagination page={callPage} totalPages={callTotalPages} setPage={setCallPage} />
        </div>
      )}

      {tab === "sms" && (
        <div className="bg-white rounded-lg shadow p-5">
          <div className="flex flex-wrap items-center gap-3 mb-4">
            <h2 className="text-sm font-semibold text-gray-700 ml-auto">{t("smsLog")}</h2>
            <select value={smsStatusFilter} onChange={(e) => { setSmsStatusFilter(e.target.value); setSmsPage(1); }} className="px-3 py-1.5 border border-gray-300 rounded-lg text-xs bg-white focus:outline-none focus:ring-2 focus:ring-blue-500">
              <option value="all">{t("allStatuses")}</option>
              <option value="sent">{tss("sent")}</option>
              <option value="delivered">{tss("delivered")}</option>
              <option value="failed">{tss("failed")}</option>
            </select>
            <input type="text" value={search} onChange={(e) => { setSearch(e.target.value); setCallPage(1); setSmsPage(1); }} placeholder={t("searchPhone")} className="px-3 py-1.5 border border-gray-300 rounded-lg text-sm w-52 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent" />
          </div>
          <DataTable columns={smsColumns} data={smsLogs.data?.logs || []} isLoading={smsLogs.isLoading} emptyMessage={t("noSms")} />
          <Pagination page={smsPage} totalPages={smsTotalPages} setPage={setSmsPage} />
        </div>
      )}
    </div>
  );
}
