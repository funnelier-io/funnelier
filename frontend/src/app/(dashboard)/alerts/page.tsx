"use client";

import { useState } from "react";
import { useApi } from "@/lib/hooks";
import { apiPost } from "@/lib/api-client";
import StatCard from "@/components/ui/StatCard";
import DataTable from "@/components/ui/DataTable";
import { fmtNum, fmtDate } from "@/lib/utils";
import { SEVERITY_CONFIG } from "@/lib/constants";
import type {
  AlertInstance,
  AlertListResponse,
  AlertRule,
  CreateAlertRuleRequest,
} from "@/types/alerts";

export default function AlertsPage() {
  const alerts = useApi<AlertListResponse>("/analytics/alerts");
  const rules = useApi<AlertRule[]>("/analytics/alerts/rules");

  const [showCreateRule, setShowCreateRule] = useState(false);
  const [ruleForm, setRuleForm] = useState<CreateAlertRuleRequest>({
    name: "",
    metric_name: "conversion_rate",
    condition: "below",
    threshold_value: 0.05,
    severity: "warning",
  });
  const [creating, setCreating] = useState(false);

  const alertList = alerts.data?.alerts ?? [];
  const totalAlerts = alerts.data?.total_count ?? 0;
  const unackCount = alerts.data?.unacknowledged_count ?? 0;
  const criticalCount = alertList.filter(
    (a) => a.severity === "critical" && !a.is_acknowledged
  ).length;

  async function handleAcknowledge(id: string) {
    await apiPost(`/analytics/alerts/${id}/acknowledge`);
    alerts.refetch();
  }

  async function handleCreateRule() {
    if (!ruleForm.name.trim()) return;
    setCreating(true);
    try {
      const res = await apiPost("/analytics/alerts/rules", ruleForm);
      if (res.ok) {
        setShowCreateRule(false);
        setRuleForm({
          name: "",
          metric_name: "conversion_rate",
          condition: "below",
          threshold_value: 0.05,
          severity: "warning",
        });
        rules.refetch();
      }
    } finally {
      setCreating(false);
    }
  }

  const metricLabels: Record<string, string> = {
    conversion_rate: "نرخ تبدیل",
    lead_count: "تعداد سرنخ",
    sms_delivery_rate: "نرخ تحویل پیامک",
    call_answer_rate: "نرخ پاسخ تماس",
    daily_revenue: "درآمد روزانه",
    drop_off_rate: "نرخ ریزش",
  };

  const conditionLabels: Record<string, string> = {
    above: "بالاتر از",
    below: "پایین‌تر از",
    change_percent: "تغییر درصدی",
  };

  const alertColumns = [
    {
      key: "severity",
      header: "",
      render: (a: AlertInstance) => (
        <span className="text-base">
          {SEVERITY_CONFIG[a.severity]?.icon ?? "⚪"}
        </span>
      ),
    },
    {
      key: "rule_name",
      header: "قاعده",
      render: (a: AlertInstance) => (
        <div>
          <div className="font-medium text-sm">{a.rule_name}</div>
          <div className="text-xs text-gray-500">
            {metricLabels[a.metric_name] || a.metric_name}
          </div>
        </div>
      ),
    },
    {
      key: "message",
      header: "پیام",
      render: (a: AlertInstance) => (
        <span className="text-sm text-gray-700 line-clamp-2">
          {a.message}
        </span>
      ),
    },
    {
      key: "values",
      header: "مقدار / آستانه",
      render: (a: AlertInstance) => (
        <div className="text-xs">
          <span className="font-mono text-red-600">
            {a.metric_value.toFixed(2)}
          </span>
          <span className="text-gray-400 mx-1">/</span>
          <span className="font-mono text-gray-500">
            {a.threshold_value.toFixed(2)}
          </span>
        </div>
      ),
    },
    {
      key: "triggered_at",
      header: "زمان",
      render: (a: AlertInstance) => (
        <span className="text-xs text-gray-500">
          {fmtDate(a.triggered_at)}
        </span>
      ),
    },
    {
      key: "status",
      header: "وضعیت",
      render: (a: AlertInstance) =>
        a.is_acknowledged ? (
          <span className="inline-block px-2 py-0.5 rounded-full text-xs bg-green-50 text-green-700">
            تأیید شده
          </span>
        ) : (
          <button
            onClick={() => handleAcknowledge(a.id)}
            className="px-2 py-1 text-xs bg-amber-50 text-amber-700 rounded hover:bg-amber-100"
          >
            تأیید
          </button>
        ),
    },
  ];

  const ruleColumns = [
    {
      key: "name",
      header: "نام",
      render: (r: AlertRule) => (
        <span className="font-medium text-sm">{r.name}</span>
      ),
    },
    {
      key: "metric",
      header: "متریک",
      render: (r: AlertRule) => (
        <span className="text-xs">
          {metricLabels[r.metric_name] || r.metric_name}
        </span>
      ),
    },
    {
      key: "condition",
      header: "شرط",
      render: (r: AlertRule) => (
        <span className="text-xs">
          {conditionLabels[r.condition] || r.condition}{" "}
          <span className="font-mono">{r.threshold_value}</span>
        </span>
      ),
    },
    {
      key: "severity",
      header: "شدت",
      render: (r: AlertRule) => {
        const cfg = SEVERITY_CONFIG[r.severity] || SEVERITY_CONFIG.info;
        return (
          <span
            className={`inline-block px-2 py-0.5 rounded-full text-xs ${cfg.bg} ${cfg.color}`}
          >
            {cfg.icon}{" "}
            {r.severity === "critical"
              ? "بحرانی"
              : r.severity === "warning"
                ? "هشدار"
                : "اطلاع"}
          </span>
        );
      },
    },
    {
      key: "is_active",
      header: "وضعیت",
      render: (r: AlertRule) => (
        <span
          className={`text-xs ${r.is_active ? "text-green-600" : "text-gray-400"}`}
        >
          {r.is_active ? "فعال" : "غیرفعال"}
        </span>
      ),
    },
  ];

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-bold">هشدارها و اعلان‌ها</h1>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="کل هشدارها"
          value={fmtNum(totalAlerts)}
          icon="🔔"
          color="text-blue-600"
        />
        <StatCard
          title="تأیید نشده"
          value={fmtNum(unackCount)}
          icon="⚠️"
          color="text-amber-600"
        />
        <StatCard
          title="بحرانی"
          value={fmtNum(criticalCount)}
          icon="🔴"
          color="text-red-600"
        />
        <StatCard
          title="قوانین فعال"
          value={fmtNum(
            (rules.data ?? []).filter((r) => r.is_active).length
          )}
          icon="📏"
          color="text-purple-600"
        />
      </div>

      {/* Active Alerts */}
      <div className="bg-white rounded-lg shadow">
        <div className="px-5 py-3 border-b flex items-center justify-between">
          <h2 className="text-sm font-semibold text-gray-700">
            هشدارهای اخیر
          </h2>
          {unackCount > 0 && (
            <span className="text-xs bg-red-100 text-red-700 px-2 py-0.5 rounded-full">
              {fmtNum(unackCount)} تأیید نشده
            </span>
          )}
        </div>
        {alerts.isLoading ? (
          <div className="p-8 text-center text-gray-400 text-sm">
            در حال بارگذاری...
          </div>
        ) : alertList.length === 0 ? (
          <div className="p-8 text-center text-gray-400 text-sm">
            هشداری وجود ندارد 🎉
          </div>
        ) : (
          <DataTable columns={alertColumns} data={alertList} />
        )}
      </div>

      {/* Alert Rules */}
      <div className="bg-white rounded-lg shadow">
        <div className="px-5 py-3 border-b flex items-center justify-between">
          <h2 className="text-sm font-semibold text-gray-700">
            قوانین هشدار
          </h2>
          <button
            onClick={() => setShowCreateRule(!showCreateRule)}
            className="text-xs px-3 py-1.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
          >
            {showCreateRule ? "بستن" : "+ قانون جدید"}
          </button>
        </div>

        {/* Create Rule Form */}
        {showCreateRule && (
          <div className="p-5 border-b space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <label className="block text-xs text-gray-500 mb-1">
                  نام قانون
                </label>
                <input
                  type="text"
                  value={ruleForm.name}
                  onChange={(e) =>
                    setRuleForm({ ...ruleForm, name: e.target.value })
                  }
                  className="w-full border rounded-lg px-3 py-2 text-sm"
                  placeholder="مثلاً: کاهش نرخ تبدیل"
                />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">
                  متریک
                </label>
                <select
                  value={ruleForm.metric_name}
                  onChange={(e) =>
                    setRuleForm({ ...ruleForm, metric_name: e.target.value })
                  }
                  className="w-full border rounded-lg px-3 py-2 text-sm"
                >
                  {Object.entries(metricLabels).map(([k, v]) => (
                    <option key={k} value={k}>
                      {v}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">شرط</label>
                <select
                  value={ruleForm.condition}
                  onChange={(e) =>
                    setRuleForm({ ...ruleForm, condition: e.target.value })
                  }
                  className="w-full border rounded-lg px-3 py-2 text-sm"
                >
                  {Object.entries(conditionLabels).map(([k, v]) => (
                    <option key={k} value={k}>
                      {v}
                    </option>
                  ))}
                </select>
              </div>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <label className="block text-xs text-gray-500 mb-1">
                  آستانه
                </label>
                <input
                  type="number"
                  step="0.01"
                  value={ruleForm.threshold_value}
                  onChange={(e) =>
                    setRuleForm({
                      ...ruleForm,
                      threshold_value: parseFloat(e.target.value) || 0,
                    })
                  }
                  className="w-full border rounded-lg px-3 py-2 text-sm"
                />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">شدت</label>
                <select
                  value={ruleForm.severity}
                  onChange={(e) =>
                    setRuleForm({ ...ruleForm, severity: e.target.value })
                  }
                  className="w-full border rounded-lg px-3 py-2 text-sm"
                >
                  <option value="info">اطلاع</option>
                  <option value="warning">هشدار</option>
                  <option value="critical">بحرانی</option>
                </select>
              </div>
              <div className="flex items-end">
                <button
                  onClick={handleCreateRule}
                  disabled={creating || !ruleForm.name.trim()}
                  className="w-full px-4 py-2 bg-green-600 text-white text-sm rounded-lg hover:bg-green-700 disabled:opacity-50"
                >
                  {creating ? "در حال ایجاد..." : "ایجاد قانون"}
                </button>
              </div>
            </div>
          </div>
        )}

        {rules.isLoading ? (
          <div className="p-8 text-center text-gray-400 text-sm">
            در حال بارگذاری...
          </div>
        ) : (rules.data ?? []).length === 0 ? (
          <div className="p-8 text-center text-gray-400 text-sm">
            قانون هشداری تعریف نشده. اولین قانون را ایجاد کنید.
          </div>
        ) : (
          <DataTable columns={ruleColumns} data={rules.data ?? []} />
        )}
      </div>
    </div>
  );
}

