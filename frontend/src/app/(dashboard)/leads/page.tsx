"use client";

import { useState } from "react";
import { useApi, useDebounce } from "@/lib/hooks";
import StatCard from "@/components/ui/StatCard";
import DataTable from "@/components/ui/DataTable";
import ContactDetailPanel from "@/components/ui/ContactDetailPanel";
import { fmtNum, fmtDate, fmtPercent } from "@/lib/utils";
import { STAGE_LABELS, SEGMENT_LABELS } from "@/lib/constants";
import type { ContactListResponse, LeadStatsSummary, Contact } from "@/types/leads";

const STAGE_BADGE_COLORS: Record<string, string> = {
  lead_acquired: "bg-blue-50 text-blue-700",
  sms_sent: "bg-purple-50 text-purple-700",
  sms_delivered: "bg-violet-50 text-violet-700",
  call_attempted: "bg-amber-50 text-amber-700",
  call_answered: "bg-green-50 text-green-700",
  invoice_issued: "bg-cyan-50 text-cyan-700",
  payment_received: "bg-emerald-50 text-emerald-700",
};

const SEGMENT_BADGE_COLORS: Record<string, string> = {
  champions: "bg-emerald-50 text-emerald-700",
  loyal: "bg-green-50 text-green-700",
  potential_loyalist: "bg-blue-50 text-blue-700",
  new_customers: "bg-cyan-50 text-cyan-700",
  promising: "bg-purple-50 text-purple-700",
  need_attention: "bg-amber-50 text-amber-700",
  about_to_sleep: "bg-orange-50 text-orange-700",
  at_risk: "bg-red-50 text-red-700",
  cant_lose: "bg-rose-50 text-rose-700",
  hibernating: "bg-gray-100 text-gray-600",
  lost: "bg-gray-100 text-gray-500",
};

export default function LeadsPage() {
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [stageFilter, setStageFilter] = useState<string>("all");
  const [segmentFilter, setSegmentFilter] = useState<string>("all");
  const [selectedContact, setSelectedContact] = useState<Contact | null>(null);
  const pageSize = 20;

  const debouncedSearch = useDebounce(search, 300);

  // Build query path with filters
  let queryPath = `/leads/contacts?page=${page}&page_size=${pageSize}`;
  if (debouncedSearch) queryPath += `&search=${encodeURIComponent(debouncedSearch)}`;
  if (stageFilter !== "all") queryPath += `&stage=${stageFilter}`;
  if (segmentFilter !== "all") queryPath += `&segment=${segmentFilter}`;

  const contacts = useApi<ContactListResponse>(queryPath);
  const stats = useApi<LeadStatsSummary>("/leads/stats");

  const totalPages = contacts.data
    ? Math.ceil(contacts.data.total_count / pageSize)
    : 0;

  // Available stages and segments from stats
  const stages = stats.data?.by_stage
    ? Object.entries(stats.data.by_stage).sort((a, b) => b[1] - a[1])
    : [];
  const segments = stats.data?.by_segment
    ? Object.entries(stats.data.by_segment).sort((a, b) => b[1] - a[1])
    : [];

  const columns = [
    {
      key: "name",
      header: "نام",
      render: (c: Contact) => (
        <div>
          <span className="font-medium">{c.name || "—"}</span>
          {c.category_name && (
            <span className="text-xs text-gray-400 block truncate max-w-[150px]">
              {c.category_name}
            </span>
          )}
        </div>
      ),
    },
    {
      key: "phone_number",
      header: "شماره",
      render: (c: Contact) => (
        <span className="font-mono text-xs" dir="ltr">{c.phone_number}</span>
      ),
    },
    {
      key: "current_stage",
      header: "مرحله",
      render: (c: Contact) => (
        <span className={`inline-block px-2 py-0.5 rounded-full text-xs ${STAGE_BADGE_COLORS[c.current_stage] || "bg-gray-50 text-gray-700"}`}>
          {STAGE_LABELS[c.current_stage] || c.current_stage}
        </span>
      ),
    },
    {
      key: "rfm_segment",
      header: "بخش RFM",
      render: (c: Contact) => c.rfm_segment ? (
        <span className={`inline-block px-2 py-0.5 rounded-full text-xs ${SEGMENT_BADGE_COLORS[c.rfm_segment] || "bg-gray-100 text-gray-600"}`}>
          {SEGMENT_LABELS[c.rfm_segment] || c.rfm_segment}
        </span>
      ) : (
        <span className="text-gray-300 text-xs">—</span>
      ),
    },
    {
      key: "total_calls",
      header: "تماس",
      render: (c: Contact) => (
        <div className="text-center">
          <span className="text-sm">{fmtNum(c.total_calls)}</span>
          {c.total_answered_calls > 0 && (
            <span className="text-xs text-green-600 block">
              {fmtNum(c.total_answered_calls)} پاسخ
            </span>
          )}
        </div>
      ),
    },
    {
      key: "total_sms_sent",
      header: "پیامک",
      render: (c: Contact) => fmtNum(c.total_sms_sent),
    },
    {
      key: "total_revenue",
      header: "درآمد",
      render: (c: Contact) => c.total_revenue > 0 ? (
        <span className="text-green-600 text-xs font-medium">
          {fmtNum(Math.round(c.total_revenue / 10_000_000))}M
        </span>
      ) : (
        <span className="text-gray-300 text-xs">—</span>
      ),
    },
    {
      key: "created_at",
      header: "تاریخ",
      render: (c: Contact) => fmtDate(c.created_at),
    },
  ];

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-bold">سرنخ‌ها</h1>

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
            title="تماس گرفته شده"
            value={fmtNum(
              (stats.data.by_stage?.call_attempted || 0) +
                (stats.data.by_stage?.call_answered || 0)
            )}
            icon="📞"
            color="text-amber-600"
            subtitle={`${fmtPercent(
              ((stats.data.by_stage?.call_attempted || 0) + (stats.data.by_stage?.call_answered || 0)) / Math.max(stats.data.total_contacts, 1)
            )} از کل`}
          />
          <StatCard
            title="بخش‌بندی‌ها"
            value={fmtNum(Object.keys(stats.data.by_segment || {}).length)}
            icon="🎯"
            color="text-green-600"
          />
          <StatCard
            title="دسته‌بندی‌ها"
            value={fmtNum(Object.keys(stats.data.by_category || {}).length)}
            icon="🏷️"
            color="text-purple-600"
          />
        </div>
      )}

      {/* Search + Filters + Table */}
      <div className="bg-white rounded-lg shadow p-5">
        <div className="flex flex-wrap items-center gap-3 mb-4">
          <h2 className="text-sm font-semibold text-gray-700 ml-auto">لیست مخاطبین</h2>

          {/* Stage filter */}
          <select
            value={stageFilter}
            onChange={(e) => { setStageFilter(e.target.value); setPage(1); }}
            className="px-3 py-1.5 border border-gray-300 rounded-lg text-xs bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="all">همه مراحل</option>
            {stages.map(([stage, count]) => (
              <option key={stage} value={stage}>
                {STAGE_LABELS[stage] || stage} ({fmtNum(count)})
              </option>
            ))}
          </select>

          {/* Segment filter */}
          <select
            value={segmentFilter}
            onChange={(e) => { setSegmentFilter(e.target.value); setPage(1); }}
            className="px-3 py-1.5 border border-gray-300 rounded-lg text-xs bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="all">همه بخش‌ها</option>
            {segments.map(([seg, count]) => (
              <option key={seg} value={seg}>
                {SEGMENT_LABELS[seg] || seg} ({fmtNum(count)})
              </option>
            ))}
          </select>

          {/* Search */}
          <input
            type="text"
            value={search}
            onChange={(e) => { setSearch(e.target.value); setPage(1); }}
            placeholder="جستجو نام یا شماره..."
            className="px-3 py-1.5 border border-gray-300 rounded-lg text-sm w-56 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
        </div>

        {/* Active filters */}
        {(stageFilter !== "all" || segmentFilter !== "all" || debouncedSearch) && (
          <div className="flex items-center gap-2 mb-3">
            <span className="text-xs text-gray-400">فیلتر فعال:</span>
            {stageFilter !== "all" && (
              <button
                onClick={() => { setStageFilter("all"); setPage(1); }}
                className="px-2 py-0.5 bg-blue-50 text-blue-700 rounded text-xs hover:bg-blue-100 transition-colors"
              >
                {STAGE_LABELS[stageFilter] || stageFilter} ✕
              </button>
            )}
            {segmentFilter !== "all" && (
              <button
                onClick={() => { setSegmentFilter("all"); setPage(1); }}
                className="px-2 py-0.5 bg-green-50 text-green-700 rounded text-xs hover:bg-green-100 transition-colors"
              >
                {SEGMENT_LABELS[segmentFilter] || segmentFilter} ✕
              </button>
            )}
            {debouncedSearch && (
              <button
                onClick={() => { setSearch(""); setPage(1); }}
                className="px-2 py-0.5 bg-gray-50 text-gray-700 rounded text-xs hover:bg-gray-100 transition-colors"
              >
                «{debouncedSearch}» ✕
              </button>
            )}
            <span className="text-xs text-gray-400 mr-2">
              {contacts.data ? fmtNum(contacts.data.total_count) : "..."} نتیجه
            </span>
          </div>
        )}

        <DataTable
          columns={columns}
          data={contacts.data?.contacts || []}
          isLoading={contacts.isLoading}
          emptyMessage="مخاطبی یافت نشد"
          onRowClick={(c) => setSelectedContact(c)}
        />

        {/* Pagination */}
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

      {/* Contact Detail Panel */}
      {selectedContact && (
        <ContactDetailPanel
          contact={selectedContact}
          onClose={() => setSelectedContact(null)}
        />
      )}
    </div>
  );
}
