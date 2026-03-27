"use client";

import { useState } from "react";
import { useApi } from "@/lib/hooks";
import { apiPost } from "@/lib/api-client";
import StatCard from "@/components/ui/StatCard";
import DataTable from "@/components/ui/DataTable";
import { fmtNum, fmtDate } from "@/lib/utils";
import {
  CAMPAIGN_STATUS_LABELS,
  CAMPAIGN_TYPE_LABELS,
} from "@/lib/constants";
import type {
  Campaign,
  CampaignListResponse,
  CreateCampaignRequest,
} from "@/types/campaigns";

const STATUS_COLORS: Record<string, string> = {
  draft: "bg-gray-100 text-gray-700",
  scheduled: "bg-blue-50 text-blue-700",
  running: "bg-green-50 text-green-700",
  paused: "bg-amber-50 text-amber-700",
  completed: "bg-emerald-50 text-emerald-700",
  cancelled: "bg-red-50 text-red-700",
};

export default function CampaignsPage() {
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [showCreate, setShowCreate] = useState(false);
  const [formData, setFormData] = useState<CreateCampaignRequest>({
    name: "",
    campaign_type: "sms",
    content: "",
  });
  const [creating, setCreating] = useState(false);

  const queryPath =
    statusFilter === "all"
      ? `/campaigns?page=${page}&page_size=20`
      : `/campaigns?page=${page}&page_size=20&status=${statusFilter}`;

  const campaigns = useApi<CampaignListResponse>(queryPath);

  const list = campaigns.data?.campaigns ?? [];
  const totalPages = campaigns.data
    ? Math.ceil(campaigns.data.total_count / 20)
    : 0;

  // Summary counts
  const totalCount = campaigns.data?.total_count ?? 0;
  const runningCount = list.filter((c) => c.status === "running").length;
  const completedCount = list.filter((c) => c.status === "completed").length;
  const draftCount = list.filter((c) => c.status === "draft").length;

  async function handleCreate() {
    if (!formData.name.trim()) return;
    setCreating(true);
    try {
      const res = await apiPost<Campaign>("/campaigns", formData);
      if (res.ok) {
        setShowCreate(false);
        setFormData({ name: "", campaign_type: "sms", content: "" });
        campaigns.refetch();
      }
    } finally {
      setCreating(false);
    }
  }

  async function handleAction(id: string, action: string) {
    await apiPost(`/campaigns/${id}/${action}`);
    campaigns.refetch();
  }

  const statusTabs = [
    { key: "all", label: "همه" },
    { key: "draft", label: "پیش‌نویس" },
    { key: "running", label: "در حال اجرا" },
    { key: "completed", label: "تکمیل شده" },
  ];

  const columns = [
    {
      key: "name",
      header: "نام کمپین",
      render: (c: Campaign) => (
        <div>
          <div className="font-medium text-sm">{c.name}</div>
          {c.description && (
            <div className="text-xs text-gray-500 mt-0.5 truncate max-w-[200px]">
              {c.description}
            </div>
          )}
        </div>
      ),
    },
    {
      key: "campaign_type",
      header: "نوع",
      render: (c: Campaign) => (
        <span className="text-xs">
          {CAMPAIGN_TYPE_LABELS[c.campaign_type] || c.campaign_type}
        </span>
      ),
    },
    {
      key: "status",
      header: "وضعیت",
      render: (c: Campaign) => (
        <span
          className={`inline-block px-2 py-0.5 rounded-full text-xs ${STATUS_COLORS[c.status] || "bg-gray-100"}`}
        >
          {CAMPAIGN_STATUS_LABELS[c.status] || c.status}
        </span>
      ),
    },
    {
      key: "recipients",
      header: "مخاطبین",
      render: (c: Campaign) => (
        <span className="text-sm">{fmtNum(c.total_recipients)}</span>
      ),
    },
    {
      key: "sent",
      header: "ارسال / تحویل",
      render: (c: Campaign) => (
        <span className="text-xs text-gray-600">
          {fmtNum(c.sent_count)} / {fmtNum(c.delivered_count)}
        </span>
      ),
    },
    {
      key: "conversions",
      header: "تبدیل",
      render: (c: Campaign) => (
        <span className="text-sm font-medium text-green-600">
          {fmtNum(c.conversion_count)}
        </span>
      ),
    },
    {
      key: "created_at",
      header: "تاریخ",
      render: (c: Campaign) => (
        <span className="text-xs text-gray-500">{fmtDate(c.created_at)}</span>
      ),
    },
    {
      key: "actions",
      header: "",
      render: (c: Campaign) => (
        <div className="flex gap-1">
          {c.status === "draft" && (
            <button
              onClick={() => handleAction(c.id, "start")}
              className="text-xs px-2 py-1 bg-green-50 text-green-700 rounded hover:bg-green-100"
            >
              شروع
            </button>
          )}
          {c.status === "running" && (
            <button
              onClick={() => handleAction(c.id, "pause")}
              className="text-xs px-2 py-1 bg-amber-50 text-amber-700 rounded hover:bg-amber-100"
            >
              توقف
            </button>
          )}
          {c.status === "paused" && (
            <button
              onClick={() => handleAction(c.id, "resume")}
              className="text-xs px-2 py-1 bg-blue-50 text-blue-700 rounded hover:bg-blue-100"
            >
              ادامه
            </button>
          )}
        </div>
      ),
    },
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold">کمپین‌ها</h1>
        <button
          onClick={() => setShowCreate(!showCreate)}
          className="px-4 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700"
        >
          {showCreate ? "بستن" : "+ کمپین جدید"}
        </button>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard title="کل کمپین‌ها" value={fmtNum(totalCount)} icon="📣" color="text-blue-600" />
        <StatCard title="در حال اجرا" value={fmtNum(runningCount)} icon="▶️" color="text-green-600" />
        <StatCard title="تکمیل شده" value={fmtNum(completedCount)} icon="✅" color="text-emerald-600" />
        <StatCard title="پیش‌نویس" value={fmtNum(draftCount)} icon="📝" color="text-gray-600" />
      </div>

      {/* Create Campaign Form */}
      {showCreate && (
        <div className="bg-white rounded-lg shadow p-5 space-y-4">
          <h2 className="text-sm font-semibold text-gray-700">
            ایجاد کمپین جدید
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs text-gray-500 mb-1">
                نام کمپین
              </label>
              <input
                type="text"
                value={formData.name}
                onChange={(e) =>
                  setFormData({ ...formData, name: e.target.value })
                }
                className="w-full border rounded-lg px-3 py-2 text-sm"
                placeholder="نام کمپین را وارد کنید"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">نوع</label>
              <select
                value={formData.campaign_type}
                onChange={(e) =>
                  setFormData({ ...formData, campaign_type: e.target.value })
                }
                className="w-full border rounded-lg px-3 py-2 text-sm"
              >
                <option value="sms">پیامکی</option>
                <option value="call">تماسی</option>
                <option value="mixed">ترکیبی</option>
              </select>
            </div>
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">
              توضیحات
            </label>
            <input
              type="text"
              value={formData.description ?? ""}
              onChange={(e) =>
                setFormData({ ...formData, description: e.target.value })
              }
              className="w-full border rounded-lg px-3 py-2 text-sm"
              placeholder="توضیحات کمپین"
            />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">
              متن پیام
            </label>
            <textarea
              value={formData.content ?? ""}
              onChange={(e) =>
                setFormData({ ...formData, content: e.target.value })
              }
              rows={3}
              className="w-full border rounded-lg px-3 py-2 text-sm"
              placeholder="متن پیامک یا اسکریپت تماس"
            />
          </div>
          <div className="flex justify-end">
            <button
              onClick={handleCreate}
              disabled={creating || !formData.name.trim()}
              className="px-4 py-2 bg-green-600 text-white text-sm rounded-lg hover:bg-green-700 disabled:opacity-50"
            >
              {creating ? "در حال ایجاد..." : "ایجاد کمپین"}
            </button>
          </div>
        </div>
      )}

      {/* Status Filter Tabs */}
      <div className="flex gap-2">
        {statusTabs.map((tab) => (
          <button
            key={tab.key}
            onClick={() => {
              setStatusFilter(tab.key);
              setPage(1);
            }}
            className={`px-3 py-1.5 text-xs rounded-lg transition-colors ${
              statusFilter === tab.key
                ? "bg-blue-600 text-white"
                : "bg-gray-100 text-gray-600 hover:bg-gray-200"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Campaigns Table */}
      <div className="bg-white rounded-lg shadow">
        {campaigns.isLoading ? (
          <div className="p-8 text-center text-gray-400 text-sm">
            در حال بارگذاری...
          </div>
        ) : list.length === 0 ? (
          <div className="p-8 text-center text-gray-400 text-sm">
            کمپینی یافت نشد. اولین کمپین خود را ایجاد کنید.
          </div>
        ) : (
          <DataTable columns={columns} data={list} />
        )}

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="flex items-center justify-center gap-2 py-3 border-t">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page === 1}
              className="px-3 py-1 text-xs rounded bg-gray-100 disabled:opacity-50"
            >
              قبلی
            </button>
            <span className="text-xs text-gray-500">
              صفحه {fmtNum(page)} از {fmtNum(totalPages)}
            </span>
            <button
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page === totalPages}
              className="px-3 py-1 text-xs rounded bg-gray-100 disabled:opacity-50"
            >
              بعدی
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

