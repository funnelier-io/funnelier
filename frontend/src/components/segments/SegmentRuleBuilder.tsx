"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { apiPost, apiPut, apiDelete } from "@/lib/api-client";
import type {
  SegmentRule,
  SegmentRuleCreateRequest,
  SegmentRulePreviewResponse,
  BulkAssignResponse,
} from "@/types/segment-rules";

const COLORS = [
  "#059669", "#22c55e", "#3b82f6", "#06b6d4", "#8b5cf6",
  "#f59e0b", "#f97316", "#ef4444", "#ec4899", "#6366f1",
];

const RANGE_OPTIONS = [1, 2, 3, 4, 5];

interface RuleFormData {
  name: string;
  color: string;
  priority: number;
  r_min: number;
  r_max: number;
  f_min: number;
  f_max: number;
  m_min: number;
  m_max: number;
}

const defaultForm = (): RuleFormData => ({
  name: "",
  color: COLORS[0],
  priority: 1,
  r_min: 1, r_max: 5,
  f_min: 1, f_max: 5,
  m_min: 1, m_max: 5,
});

interface Props {
  rules: SegmentRule[];
  onRefresh: () => void;
}

export default function SegmentRuleBuilder({ rules, onRefresh }: Props) {
  const t = useTranslations("segmentRules");
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState<RuleFormData>(defaultForm());
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [preview, setPreview] = useState<Record<string, SegmentRulePreviewResponse>>({});
  const [assigning, setAssigning] = useState<string | null>(null);
  const [assignResult, setAssignResult] = useState<Record<string, number>>({});

  function openCreate() {
    setEditingId(null);
    setForm(defaultForm());
    setError(null);
    setShowForm(true);
  }

  function openEdit(rule: SegmentRule) {
    setEditingId(rule.id);
    setForm({
      name: rule.name,
      color: rule.color,
      priority: rule.priority,
      r_min: rule.r_min, r_max: rule.r_max,
      f_min: rule.f_min, f_max: rule.f_max,
      m_min: rule.m_min, m_max: rule.m_max,
    });
    setError(null);
    setShowForm(true);
  }

  async function handleSave() {
    if (!form.name.trim()) { setError(t("nameRequired")); return; }
    setSaving(true);
    setError(null);
    const payload: SegmentRuleCreateRequest = form;
    const res = editingId
      ? await apiPut<SegmentRule>(`/segments/rules/${editingId}`, payload)
      : await apiPost<SegmentRule>("/segments/rules", payload);
    setSaving(false);
    if (res.ok) {
      setShowForm(false);
      onRefresh();
    } else {
      setError(res.error || t("saveFailed"));
    }
  }

  async function handleDelete(id: string) {
    if (!confirm(t("confirmDelete"))) return;
    await apiDelete(`/segments/rules/${id}`);
    onRefresh();
  }

  async function handlePreview(id: string) {
    const res = await apiPost<SegmentRulePreviewResponse>(`/segments/rules/${id}/preview`, {});
    if (res.ok && res.data) {
      setPreview((prev) => ({ ...prev, [id]: res.data! }));
    }
  }

  async function handleAssign(id: string) {
    setAssigning(id);
    const res = await apiPost<BulkAssignResponse>(`/segments/rules/${id}/assign`, {});
    setAssigning(null);
    if (res.ok && res.data) {
      setAssignResult((prev) => ({ ...prev, [id]: res.data!.assigned_count }));
    }
  }

  const RangeSelect = ({
    label,
    minKey,
    maxKey,
  }: {
    label: string;
    minKey: keyof RuleFormData;
    maxKey: keyof RuleFormData;
  }) => (
    <div>
      <label className="block text-xs font-medium text-gray-600 mb-1">{label}</label>
      <div className="flex gap-2 items-center">
        <select
          value={form[minKey] as number}
          onChange={(e) => setForm((f) => ({ ...f, [minKey]: +e.target.value }))}
          className="border rounded px-2 py-1 text-sm w-16"
        >
          {RANGE_OPTIONS.map((v) => <option key={v}>{v}</option>)}
        </select>
        <span className="text-gray-400 text-xs">–</span>
        <select
          value={form[maxKey] as number}
          onChange={(e) => setForm((f) => ({ ...f, [maxKey]: +e.target.value }))}
          className="border rounded px-2 py-1 text-sm w-16"
        >
          {RANGE_OPTIONS.map((v) => <option key={v}>{v}</option>)}
        </select>
      </div>
    </div>
  );

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-base font-semibold text-gray-800">{t("title")}</h2>
        <button
          onClick={openCreate}
          className="bg-blue-600 text-white text-sm px-3 py-1.5 rounded-lg hover:bg-blue-700"
        >
          + {t("addRule")}
        </button>
      </div>

      {/* Rule list */}
      <div className="space-y-3">
        {rules.length === 0 && (
          <p className="text-sm text-gray-500 text-center py-6">{t("noRules")}</p>
        )}
        {rules.map((rule) => (
          <div
            key={rule.id}
            className="border rounded-xl p-4 bg-white shadow-sm flex flex-col gap-3"
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span
                  className="w-4 h-4 rounded-full inline-block"
                  style={{ backgroundColor: rule.color }}
                />
                <span className="font-medium text-gray-800">{rule.name}</span>
                <span className="text-xs text-gray-400">#{rule.priority}</span>
              </div>
              <div className="flex gap-2">
                <button onClick={() => handlePreview(rule.id)} className="text-xs text-blue-600 hover:underline">
                  {t("preview")}
                </button>
                <button onClick={() => openEdit(rule)} className="text-xs text-amber-600 hover:underline">
                  {t("edit")}
                </button>
                <button onClick={() => handleDelete(rule.id)} className="text-xs text-red-600 hover:underline">
                  {t("delete")}
                </button>
              </div>
            </div>

            {/* RFM range badges */}
            <div className="flex gap-3 text-xs">
              {[
                { label: "R", min: rule.r_min, max: rule.r_max },
                { label: "F", min: rule.f_min, max: rule.f_max },
                { label: "M", min: rule.m_min, max: rule.m_max },
              ].map(({ label, min, max }) => (
                <span key={label} className="bg-gray-100 rounded-full px-2 py-0.5 font-mono">
                  {label}: {min}–{max}
                </span>
              ))}
            </div>

            {/* Preview result */}
            {preview[rule.id] && (
              <div className="text-xs text-gray-600 bg-blue-50 rounded-lg p-2">
                {t("matchedCount", { count: preview[rule.id].matched_count })}
              </div>
            )}

            {/* Assign button */}
            <div className="flex items-center gap-3">
              <button
                onClick={() => handleAssign(rule.id)}
                disabled={assigning === rule.id}
                className="text-xs bg-green-600 text-white px-3 py-1 rounded-lg hover:bg-green-700 disabled:opacity-50"
              >
                {assigning === rule.id ? t("assigning") : t("assign")}
              </button>
              {assignResult[rule.id] !== undefined && (
                <span className="text-xs text-green-700">
                  ✓ {t("assignedCount", { count: assignResult[rule.id] })}
                </span>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Create/Edit modal */}
      {showForm && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-md p-6 space-y-4">
            <h3 className="font-semibold text-gray-800">
              {editingId ? t("editRule") : t("createRule")}
            </h3>

            {error && <p className="text-sm text-red-600">{error}</p>}

            <div className="space-y-3">
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">{t("name")}</label>
                <input
                  type="text"
                  value={form.name}
                  onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                  className="border rounded-lg px-3 py-2 text-sm w-full"
                  placeholder={t("namePlaceholder")}
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">{t("color")}</label>
                <div className="flex gap-2 flex-wrap">
                  {COLORS.map((c) => (
                    <button
                      key={c}
                      onClick={() => setForm((f) => ({ ...f, color: c }))}
                      className={`w-6 h-6 rounded-full border-2 ${form.color === c ? "border-gray-800" : "border-transparent"}`}
                      style={{ backgroundColor: c }}
                    />
                  ))}
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">{t("priority")}</label>
                <input
                  type="number"
                  min={1}
                  max={100}
                  value={form.priority}
                  onChange={(e) => setForm((f) => ({ ...f, priority: +e.target.value }))}
                  className="border rounded-lg px-3 py-2 text-sm w-24"
                />
              </div>

              <div className="grid grid-cols-3 gap-3">
                <RangeSelect label={t("recency")} minKey="r_min" maxKey="r_max" />
                <RangeSelect label={t("frequency")} minKey="f_min" maxKey="f_max" />
                <RangeSelect label={t("monetary")} minKey="m_min" maxKey="m_max" />
              </div>
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <button
                onClick={() => setShowForm(false)}
                className="px-4 py-2 text-sm rounded-lg border hover:bg-gray-50"
              >
                {t("cancel")}
              </button>
              <button
                onClick={handleSave}
                disabled={saving}
                className="px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
              >
                {saving ? t("saving") : t("save")}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

