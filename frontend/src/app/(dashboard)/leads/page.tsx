"use client";

import { useState } from "react";
import { useApi, useDebounce } from "@/lib/hooks";
import StatCard from "@/components/ui/StatCard";
import DataTable from "@/components/ui/DataTable";
import { fmtNum, fmtDate } from "@/lib/utils";
import { STAGE_LABELS } from "@/lib/constants";
import type { ContactListResponse, LeadStatsSummary, Contact } from "@/types/leads";

export default function LeadsPage() {
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const pageSize = 20;

  const debouncedSearch = useDebounce(search, 300);

  const contacts = useApi<ContactListResponse>(
    `/leads/contacts?page=${page}&page_size=${pageSize}${debouncedSearch ? `&search=${encodeURIComponent(debouncedSearch)}` : ""}`
  );
  const stats = useApi<LeadStatsSummary>("/leads/stats");

  const totalPages = contacts.data
    ? Math.ceil(contacts.data.total_count / pageSize)
    : 0;

  const columns = [
    {
      key: "name",
      header: "نام",
      render: (c: Contact) => (
        <span className="font-medium">{c.name || "—"}</span>
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
        <span className="inline-block px-2 py-0.5 rounded-full text-xs bg-blue-50 text-blue-700">
          {STAGE_LABELS[c.current_stage] || c.current_stage}
        </span>
      ),
    },
    {
      key: "category",
      header: "دسته‌بندی",
      render: (c: Contact) => c.category || "—",
    },
    {
      key: "total_calls",
      header: "تماس‌ها",
      render: (c: Contact) => fmtNum(c.total_calls),
    },
    {
      key: "sms_count",
      header: "پیامک",
      render: (c: Contact) => fmtNum(c.sms_count),
    },
    {
      key: "created_at",
      header: "تاریخ ایجاد",
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
            title="سرنخ‌های جدید"
            value={fmtNum(stats.data.by_stage?.lead_acquired)}
            icon="📥"
            color="text-green-600"
          />
          <StatCard
            title="تماس گرفته شده"
            value={fmtNum(
              (stats.data.by_stage?.call_attempted || 0) +
                (stats.data.by_stage?.call_answered || 0)
            )}
            icon="📞"
            color="text-amber-600"
          />
          <StatCard
            title="دسته‌بندی‌ها"
            value={fmtNum(
              Object.keys(stats.data.by_category || {}).length
            )}
            icon="🏷️"
            color="text-purple-600"
          />
        </div>
      )}

      {/* Search + Table */}
      <div className="bg-white rounded-lg shadow p-5">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm font-semibold text-gray-700">لیست مخاطبین</h2>
          <input
            type="text"
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(1);
            }}
            placeholder="جستجو نام یا شماره..."
            className="px-3 py-1.5 border border-gray-300 rounded-lg text-sm w-64 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
        </div>

        <DataTable
          columns={columns}
          data={contacts.data?.contacts || []}
          isLoading={contacts.isLoading}
          emptyMessage="مخاطبی یافت نشد"
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
    </div>
  );
}
