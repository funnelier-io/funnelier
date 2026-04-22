"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import ABTestModal from "@/components/campaigns/ABTestModal";
import { useFormat } from "@/lib/use-format";
import { useApi } from "@/lib/hooks";
import { apiPost } from "@/lib/api-client";
import StatCard from "@/components/ui/StatCard";
import DataTable from "@/components/ui/DataTable";

import {
  CAMPAIGN_STATUS_LABELS,
  CAMPAIGN_TYPE_LABELS,
  SEGMENT_LABELS,
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
  const t = useTranslations("campaigns");
  const fmt = useFormat();
  const tc = useTranslations("common");
  const tcs = useTranslations("campaignStatuses");
  const tct = useTranslations("campaignTypes");
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [showCreate, setShowCreate] = useState(false);
  const [formData, setFormData] = useState<CreateCampaignRequest>({
    name: "",
    campaign_type: "sms",
    content: "",
  });
  const [creating, setCreating] = useState(false);
  const [abTestCampaign, setAbTestCampaign] = useState<{ id: string; name: string } | null>(null);

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
    { key: "all", label: tc("all") },
    { key: "draft", label: tcs("draft") },
    { key: "running", label: tcs("running") },
    { key: "completed", label: tcs("completed") },
  ];

  const columns = [
    {
      key: "name",
      header: t("columns.name"),
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
      header: t("columns.type"),
      render: (c: Campaign) => (
        <span className="text-xs">
          {CAMPAIGN_TYPE_LABELS[c.campaign_type] || c.campaign_type}
        </span>
      ),
    },
    {
      key: "status",
      header: t("columns.status"),
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
      header: t("columns.recipients"),
      render: (c: Campaign) => (
        <span className="text-sm">{fmt.number(c.total_recipients)}</span>
      ),
    },
    {
      key: "sent",
      header: t("columns.sentDelivered"),
      render: (c: Campaign) => (
        <span className="text-xs text-gray-600">
          {fmt.number(c.sent_count)} / {fmt.number(c.delivered_count)}
        </span>
      ),
    },
    {
      key: "conversions",
      header: t("columns.conversions"),
      render: (c: Campaign) => (
        <span className="text-sm font-medium text-green-600">
          {fmt.number(c.conversion_count)}
        </span>
      ),
    },
    {
      key: "created_at",
      header: t("columns.date"),
      render: (c: Campaign) => (
        <span className="text-xs text-gray-500">{fmt.date(c.created_at)}</span>
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
              {t("start")}
            </button>
          )}
          {c.status === "running" && (
            <button
              onClick={() => handleAction(c.id, "pause")}
              className="text-xs px-2 py-1 bg-amber-50 text-amber-700 rounded hover:bg-amber-100"
            >
              {t("pause")}
            </button>
          )}
          {c.status === "paused" && (
            <button
              onClick={() => handleAction(c.id, "resume")}
              className="text-xs px-2 py-1 bg-blue-50 text-blue-700 rounded hover:bg-blue-100"
            >
              {t("resume")}
            </button>
          )}
          {(c.status === "draft" || c.status === "running") && (
            <button
              onClick={() => setAbTestCampaign({ id: c.id, name: c.name })}
              className="text-xs px-2 py-1 bg-purple-50 text-purple-700 rounded hover:bg-purple-100"
            >
              A/B
            </button>
          )}
        </div>
      ),
    },
  ];

  return (
    <>
      <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold">{t("title")}</h1>
        <button
          onClick={() => setShowCreate(!showCreate)}
          className="px-4 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700"
        >
          {showCreate ? tc("close") : t("newCampaign")}
        </button>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard title={t("totalCampaigns")} value={fmt.number(totalCount)} icon="📣" color="text-blue-600" />
        <StatCard title={t("running")} value={fmt.number(runningCount)} icon="▶️" color="text-green-600" />
        <StatCard title={t("completed")} value={fmt.number(completedCount)} icon="✅" color="text-emerald-600" />
        <StatCard title={t("drafts")} value={fmt.number(draftCount)} icon="📝" color="text-gray-600" />
      </div>

      {/* Create Campaign Form */}
      {showCreate && (
        <div className="bg-white rounded-lg shadow p-5 space-y-4">
          <h2 className="text-sm font-semibold text-gray-700">
            {t("createCampaign")}
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs text-gray-500 mb-1">
                {t("campaignName")}
              </label>
              <input
                type="text"
                value={formData.name}
                onChange={(e) =>
                  setFormData({ ...formData, name: e.target.value })
                }
                className="w-full border rounded-lg px-3 py-2 text-sm"
                placeholder={t("campaignNamePlaceholder")}
              />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">{t("type")}</label>
              <select
                value={formData.campaign_type}
                onChange={(e) =>
                  setFormData({ ...formData, campaign_type: e.target.value })
                }
                className="w-full border rounded-lg px-3 py-2 text-sm"
              >
                <option value="sms">{tct("sms")}</option>
                <option value="call">{tct("call")}</option>
                <option value="mixed">{tct("mixed")}</option>
              </select>
            </div>
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">
              {t("description")}
            </label>
            <input
              type="text"
              value={formData.description ?? ""}
              onChange={(e) =>
                setFormData({ ...formData, description: e.target.value })
              }
              className="w-full border rounded-lg px-3 py-2 text-sm"
              placeholder={t("descriptionPlaceholder")}
            />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">
              {t("messageContent")}
            </label>
            <textarea
              value={formData.content ?? ""}
              onChange={(e) =>
                setFormData({ ...formData, content: e.target.value })
              }
              rows={3}
              className="w-full border rounded-lg px-3 py-2 text-sm"
              placeholder={t("messagePlaceholder")}
            />
          </div>
          {/* Target Segments */}
          <div>
            <label className="block text-xs text-gray-500 mb-1">
              {t("targetSegments")}
            </label>
            <div className="flex flex-wrap gap-2">
              {Object.entries(SEGMENT_LABELS).map(([key, label]) => {
                const selected = formData.targeting?.segments?.includes(key) ?? false;
                return (
                  <button
                    key={key}
                    type="button"
                    onClick={() => {
                      const current = formData.targeting?.segments || [];
                      const next = selected
                        ? current.filter((s) => s !== key)
                        : [...current, key];
                      setFormData({
                        ...formData,
                        targeting: { ...formData.targeting, segments: next },
                      });
                    }}
                    className={`px-2.5 py-1 rounded-lg text-xs transition-colors ${
                      selected
                        ? "bg-blue-600 text-white"
                        : "bg-gray-100 text-gray-600 hover:bg-gray-200"
                    }`}
                  >
                    {label}
                  </button>
                );
              })}
            </div>
            {(formData.targeting?.segments?.length ?? 0) > 0 && (
              <p className="text-xs text-gray-400 mt-1">
                {t("segmentsSelected", { count: formData.targeting!.segments!.length })}
              </p>
            )}
          </div>
          <div className="flex justify-end">
            <button
              onClick={handleCreate}
              disabled={creating || !formData.name.trim()}
              className="px-4 py-2 bg-green-600 text-white text-sm rounded-lg hover:bg-green-700 disabled:opacity-50"
            >
              {creating ? t("creating") : t("createButton")}
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
            {tc("loading")}
          </div>
        ) : list.length === 0 ? (
          <div className="p-8 text-center text-gray-400 text-sm">
            {t("noCampaigns")}
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
              {tc("previous")}
            </button>
            <span className="text-xs text-gray-500">
              {tc("page", { current: fmt.number(page), total: fmt.number(totalPages) })}
            </span>
            <button
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page === totalPages}
              className="px-3 py-1 text-xs rounded bg-gray-100 disabled:opacity-50"
            >
              {tc("next")}
            </button>
          </div>
        )}
      </div>
    </div>

    {abTestCampaign && (
      <ABTestModal
        campaignId={abTestCampaign.id}
        campaignName={abTestCampaign.name}
        onClose={() => setAbTestCampaign(null)}
      />
    )}
    </>
  );
}

