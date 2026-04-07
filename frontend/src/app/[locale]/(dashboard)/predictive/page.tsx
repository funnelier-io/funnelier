"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
  BarChart,
  Bar,
  Cell,
  Legend,
  PieChart,
  Pie,
} from "recharts";
import { useApi } from "@/lib/hooks";
import { api } from "@/lib/api-client";
import StatCard from "@/components/ui/StatCard";
import { fmtNum, fmtPercent, fmtPercentRaw, fmtCurrency, cn } from "@/lib/utils";
import type {
  ChurnSummary,
  LeadScoringResult,
  ABTestResult,
  CampaignROI,
  RetentionAnalysis,
} from "@/types/predictive";

const RISK_COLORS: Record<string, string> = {
  low: "#22c55e",
  medium: "#f59e0b",
  high: "#f97316",
  critical: "#ef4444",
};

const GRADE_COLORS: Record<string, string> = {
  A: "#059669",
  B: "#22c55e",
  C: "#f59e0b",
  D: "#f97316",
  F: "#ef4444",
};

type Tab = "churn" | "scoring" | "abtest" | "roi" | "retention";

export default function PredictivePage() {
  const t = useTranslations("predictive");
  const tc = useTranslations("common");
  const [activeTab, setActiveTab] = useState<Tab>("churn");

  const tabs: { key: Tab; label: string; icon: string }[] = [
    { key: "churn", label: t("churnTab"), icon: "⚠️" },
    { key: "scoring", label: t("scoringTab"), icon: "⭐" },
    { key: "abtest", label: t("abTestTab"), icon: "🔬" },
    { key: "roi", label: t("roiTab"), icon: "💰" },
    { key: "retention", label: t("retentionTab"), icon: "📈" },
  ];

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-bold">{t("title")}</h1>
      <p className="text-sm text-gray-500">{t("subtitle")}</p>

      {/* Tab Navigation */}
      <div className="flex flex-wrap gap-2 border-b border-gray-200 pb-2">
        {tabs.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={cn(
              "px-4 py-2 text-sm rounded-t-md transition-colors",
              activeTab === tab.key
                ? "bg-blue-100 text-blue-700 font-semibold border-b-2 border-blue-600"
                : "text-gray-500 hover:bg-gray-100"
            )}
          >
            {tab.icon} {tab.label}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      {activeTab === "churn" && <ChurnPanel />}
      {activeTab === "scoring" && <ScoringPanel />}
      {activeTab === "abtest" && <ABTestPanel />}
      {activeTab === "roi" && <ROIPanel />}
      {activeTab === "retention" && <RetentionPanel />}
    </div>
  );
}

/* ───────────────────────────────────────────────────── */
/*  Churn Prediction Panel                               */
/* ───────────────────────────────────────────────────── */

function ChurnPanel() {
  const t = useTranslations("predictive");
  const tc = useTranslations("common");
  const { data, isLoading } = useApi<ChurnSummary>("/analytics/predictive/churn");

  if (isLoading) return <Loading />;
  if (!data) return <NoData />;

  const riskData = Object.entries(data.risk_distribution).map(([level, count]) => ({
    name: t(`risk_${level}`),
    value: count,
    color: RISK_COLORS[level] || "#9ca3af",
  }));

  return (
    <div className="space-y-6">
      {/* Summary Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title={t("totalContacts")}
          value={fmtNum(data.total_contacts)}
          icon="👥"
          color="text-blue-600"
        />
        <StatCard
          title={t("atRiskCount")}
          value={fmtNum(data.at_risk_count)}
          subtitle={fmtPercentRaw(data.at_risk_percentage)}
          icon="⚠️"
          color="text-red-600"
        />
        <StatCard
          title={t("revenueAtRisk")}
          value={fmtCurrency(data.estimated_revenue_at_risk)}
          icon="💸"
          color="text-amber-600"
        />
        <StatCard
          title={t("analysisDate")}
          value={new Date(data.analysis_date).toLocaleDateString("fa-IR")}
          icon="📅"
          color="text-purple-600"
        />
      </div>

      {/* Risk Distribution Chart + Recommendations */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white rounded-lg shadow p-5">
          <h2 className="text-sm font-semibold text-gray-700 mb-4">{t("riskDistribution")}</h2>
          <ResponsiveContainer width="100%" height={280}>
            <PieChart>
              <Pie
                data={riskData}
                dataKey="value"
                nameKey="name"
                cx="50%"
                cy="50%"
                outerRadius={100}
                label={({ name, value }) => `${name}: ${value}`}
              >
                {riskData.map((entry, i) => (
                  <Cell key={i} fill={entry.color} />
                ))}
              </Pie>
              <Tooltip />
              <Legend wrapperStyle={{ fontSize: 12 }} />
            </PieChart>
          </ResponsiveContainer>
        </div>

        <div className="bg-white rounded-lg shadow p-5">
          <h2 className="text-sm font-semibold text-gray-700 mb-4">{t("recommendations")}</h2>
          <div className="space-y-2">
            {data.recommendations.map((rec, i) => (
              <div key={i} className="text-sm text-gray-600 bg-gray-50 rounded-md p-3">
                {rec}
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Top Risk Contacts Table */}
      <div className="bg-white rounded-lg shadow p-5">
        <h2 className="text-sm font-semibold text-gray-700 mb-4">{t("topRiskContacts")}</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-xs text-gray-500 border-b">
                <th className="text-start py-2 px-3">{t("colName")}</th>
                <th className="text-start py-2 px-3">{t("colPhone")}</th>
                <th className="text-start py-2 px-3">{t("colSegment")}</th>
                <th className="text-start py-2 px-3">{t("colRisk")}</th>
                <th className="text-start py-2 px-3">{t("colProbability")}</th>
                <th className="text-start py-2 px-3">{t("colDaysSince")}</th>
                <th className="text-start py-2 px-3">{t("colAction")}</th>
              </tr>
            </thead>
            <tbody>
              {data.top_risk_contacts.slice(0, 15).map((c) => (
                <tr key={c.contact_id} className="border-b hover:bg-gray-50">
                  <td className="py-2 px-3">{c.name || "—"}</td>
                  <td className="py-2 px-3 font-mono text-xs">{c.phone_number}</td>
                  <td className="py-2 px-3">{c.segment || "—"}</td>
                  <td className="py-2 px-3">
                    <span
                      className={cn(
                        "inline-block px-2 py-0.5 rounded-full text-xs font-semibold text-white",
                      )}
                      style={{ backgroundColor: RISK_COLORS[c.risk_level] }}
                    >
                      {t(`risk_${c.risk_level}`)}
                    </span>
                  </td>
                  <td className="py-2 px-3 font-mono">{fmtPercentRaw(c.churn_probability * 100)}</td>
                  <td className="py-2 px-3">{c.days_since_last_activity ?? "—"}</td>
                  <td className="py-2 px-3 text-xs text-gray-500 max-w-[200px] truncate">{c.recommended_action}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

/* ───────────────────────────────────────────────────── */
/*  Lead Scoring Panel                                   */
/* ───────────────────────────────────────────────────── */

function ScoringPanel() {
  const t = useTranslations("predictive");
  const { data, isLoading } = useApi<LeadScoringResult>("/analytics/predictive/lead-scores");

  if (isLoading) return <Loading />;
  if (!data) return <NoData />;

  const gradeData = Object.entries(data.grade_distribution).map(([grade, count]) => ({
    name: t("grade", { grade }),
    grade,
    value: count,
    color: GRADE_COLORS[grade] || "#9ca3af",
  }));

  return (
    <div className="space-y-6">
      {/* Summary Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title={t("totalScored")}
          value={fmtNum(data.total_scored)}
          icon="⭐"
          color="text-blue-600"
        />
        <StatCard
          title={t("averageScore")}
          value={fmtNum(Math.round(data.average_score))}
          subtitle={`${t("outOf")} ۱۰۰`}
          icon="📊"
          color="text-green-600"
        />
        <StatCard
          title={t("gradeA")}
          value={fmtNum(data.grade_distribution["A"] || 0)}
          subtitle={t("hotLeads")}
          icon="🔥"
          color="text-emerald-600"
        />
        <StatCard
          title={t("analysisDate")}
          value={new Date(data.analysis_date).toLocaleDateString("fa-IR")}
          icon="📅"
          color="text-purple-600"
        />
      </div>

      {/* Grade Distribution + Top Leads */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white rounded-lg shadow p-5">
          <h2 className="text-sm font-semibold text-gray-700 mb-4">{t("gradeDistribution")}</h2>
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={gradeData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
              <XAxis dataKey="name" tick={{ fontSize: 12 }} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip />
              <Bar dataKey="value" name={t("leadsCount")} radius={[4, 4, 0, 0]}>
                {gradeData.map((entry, i) => (
                  <Cell key={i} fill={entry.color} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="bg-white rounded-lg shadow p-5">
          <h2 className="text-sm font-semibold text-gray-700 mb-4">{t("topLeads")}</h2>
          <div className="space-y-2 max-h-[320px] overflow-y-auto">
            {data.top_leads.slice(0, 10).map((lead) => (
              <div key={lead.contact_id} className="flex items-center justify-between p-2.5 rounded-md hover:bg-gray-50 border border-gray-100">
                <div>
                  <div className="text-sm font-medium">{lead.name || lead.phone_number}</div>
                  <div className="text-xs text-gray-400">{lead.category || "—"}</div>
                </div>
                <div className="flex items-center gap-3">
                  <span
                    className="text-xs font-bold px-2 py-1 rounded text-white"
                    style={{ backgroundColor: GRADE_COLORS[lead.grade] }}
                  >
                    {lead.grade}
                  </span>
                  <span className="text-sm font-semibold">{Math.round(lead.score)}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Full Table */}
      <div className="bg-white rounded-lg shadow p-5">
        <h2 className="text-sm font-semibold text-gray-700 mb-4">{t("leadScoreDetails")}</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-xs text-gray-500 border-b">
                <th className="text-start py-2 px-3">{t("colName")}</th>
                <th className="text-start py-2 px-3">{t("colPhone")}</th>
                <th className="text-start py-2 px-3">{t("colCategory")}</th>
                <th className="text-start py-2 px-3">{t("colGrade")}</th>
                <th className="text-start py-2 px-3">{t("colScore")}</th>
                <th className="text-start py-2 px-3">{t("colAction")}</th>
              </tr>
            </thead>
            <tbody>
              {data.top_leads.map((l) => (
                <tr key={l.contact_id} className="border-b hover:bg-gray-50">
                  <td className="py-2 px-3">{l.name || "—"}</td>
                  <td className="py-2 px-3 font-mono text-xs">{l.phone_number}</td>
                  <td className="py-2 px-3">{l.category || "—"}</td>
                  <td className="py-2 px-3">
                    <span
                      className="inline-block px-2 py-0.5 rounded text-xs font-bold text-white"
                      style={{ backgroundColor: GRADE_COLORS[l.grade] }}
                    >
                      {l.grade}
                    </span>
                  </td>
                  <td className="py-2 px-3 font-semibold">{Math.round(l.score)}</td>
                  <td className="py-2 px-3 text-xs text-gray-500 max-w-[200px] truncate">{l.recommended_action}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

/* ───────────────────────────────────────────────────── */
/*  A/B Test Calculator                                  */
/* ───────────────────────────────────────────────────── */

function ABTestPanel() {
  const t = useTranslations("predictive");
  const [form, setForm] = useState({
    test_name: "",
    variant_a_name: "کنترل (A)",
    variant_b_name: "آزمایشی (B)",
    variant_a_conversions: "",
    variant_a_total: "",
    variant_b_conversions: "",
    variant_b_total: "",
    confidence_threshold: "0.95",
  });
  const [result, setResult] = useState<ABTestResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);

    const res = await api<ABTestResult>("POST", "/analytics/predictive/ab-test", {
      test_name: form.test_name || "آزمایش A/B",
      variant_a_name: form.variant_a_name,
      variant_b_name: form.variant_b_name,
      variant_a_conversions: parseInt(form.variant_a_conversions) || 0,
      variant_a_total: parseInt(form.variant_a_total) || 1,
      variant_b_conversions: parseInt(form.variant_b_conversions) || 0,
      variant_b_total: parseInt(form.variant_b_total) || 1,
      confidence_threshold: parseFloat(form.confidence_threshold) || 0.95,
    });

    if (res.ok) {
      setResult(res.data);
    } else {
      setError(t("calcError"));
    }
    setLoading(false);
  }

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Input Form */}
        <div className="bg-white rounded-lg shadow p-5">
          <h2 className="text-sm font-semibold text-gray-700 mb-4">{t("abTestCalc")}</h2>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs text-gray-500 mb-1">{t("testName")}</label>
              <input
                className="w-full border rounded-md px-3 py-2 text-sm"
                value={form.test_name}
                onChange={(e) => setForm({ ...form, test_name: e.target.value })}
                placeholder={t("testNamePlaceholder")}
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs text-gray-500 mb-1">{t("variantAName")}</label>
                <input
                  className="w-full border rounded-md px-3 py-2 text-sm"
                  value={form.variant_a_name}
                  onChange={(e) => setForm({ ...form, variant_a_name: e.target.value })}
                />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">{t("variantBName")}</label>
                <input
                  className="w-full border rounded-md px-3 py-2 text-sm"
                  value={form.variant_b_name}
                  onChange={(e) => setForm({ ...form, variant_b_name: e.target.value })}
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs text-gray-500 mb-1">{t("variantAConversions")}</label>
                <input
                  type="number"
                  className="w-full border rounded-md px-3 py-2 text-sm"
                  value={form.variant_a_conversions}
                  onChange={(e) => setForm({ ...form, variant_a_conversions: e.target.value })}
                  placeholder="50"
                  required
                />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">{t("variantATotal")}</label>
                <input
                  type="number"
                  className="w-full border rounded-md px-3 py-2 text-sm"
                  value={form.variant_a_total}
                  onChange={(e) => setForm({ ...form, variant_a_total: e.target.value })}
                  placeholder="1000"
                  required
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs text-gray-500 mb-1">{t("variantBConversions")}</label>
                <input
                  type="number"
                  className="w-full border rounded-md px-3 py-2 text-sm"
                  value={form.variant_b_conversions}
                  onChange={(e) => setForm({ ...form, variant_b_conversions: e.target.value })}
                  placeholder="65"
                  required
                />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">{t("variantBTotal")}</label>
                <input
                  type="number"
                  className="w-full border rounded-md px-3 py-2 text-sm"
                  value={form.variant_b_total}
                  onChange={(e) => setForm({ ...form, variant_b_total: e.target.value })}
                  placeholder="1000"
                  required
                />
              </div>
            </div>

            <div>
              <label className="block text-xs text-gray-500 mb-1">{t("confidenceLevel")}</label>
              <select
                className="w-full border rounded-md px-3 py-2 text-sm"
                value={form.confidence_threshold}
                onChange={(e) => setForm({ ...form, confidence_threshold: e.target.value })}
              >
                <option value="0.90">90%</option>
                <option value="0.95">95%</option>
                <option value="0.99">99%</option>
              </select>
            </div>

            {error && <div className="text-red-500 text-sm">{error}</div>}

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-blue-600 text-white px-4 py-2 rounded-md text-sm hover:bg-blue-700 disabled:opacity-50"
            >
              {loading ? t("calculating") : t("calculate")}
            </button>
          </form>
        </div>

        {/* Results */}
        <div className="bg-white rounded-lg shadow p-5">
          <h2 className="text-sm font-semibold text-gray-700 mb-4">{t("abTestResults")}</h2>
          {result ? (
            <div className="space-y-4">
              <div className={cn(
                "text-center p-4 rounded-lg",
                result.is_significant ? "bg-green-50 border border-green-200" : "bg-amber-50 border border-amber-200"
              )}>
                <div className="text-2xl mb-1">{result.is_significant ? "✅" : "⏳"}</div>
                <div className={cn(
                  "text-sm font-semibold",
                  result.is_significant ? "text-green-700" : "text-amber-700"
                )}>
                  {result.is_significant ? t("significantResult") : t("notSignificant")}
                </div>
                {result.winner && (
                  <div className="text-sm text-green-600 mt-1">{t("winner")}: {result.winner}</div>
                )}
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="bg-blue-50 rounded-md p-3 text-center">
                  <div className="text-xs text-gray-500">{result.variant_a_name}</div>
                  <div className="text-lg font-bold text-blue-700">{fmtPercentRaw(result.variant_a_rate * 100)}</div>
                  <div className="text-xs text-gray-400">{result.variant_a_conversions}/{result.variant_a_total}</div>
                </div>
                <div className="bg-purple-50 rounded-md p-3 text-center">
                  <div className="text-xs text-gray-500">{result.variant_b_name}</div>
                  <div className="text-lg font-bold text-purple-700">{fmtPercentRaw(result.variant_b_rate * 100)}</div>
                  <div className="text-xs text-gray-400">{result.variant_b_conversions}/{result.variant_b_total}</div>
                </div>
              </div>

              <div className="space-y-2 text-sm">
                <div className="flex justify-between"><span className="text-gray-500">{t("relativeImprovement")}</span><span className="font-semibold">{result.relative_improvement > 0 ? "+" : ""}{result.relative_improvement.toFixed(1)}%</span></div>
                <div className="flex justify-between"><span className="text-gray-500">{t("pValue")}</span><span className="font-mono">{result.p_value.toFixed(4)}</span></div>
                <div className="flex justify-between"><span className="text-gray-500">{t("zScore")}</span><span className="font-mono">{result.z_score.toFixed(3)}</span></div>
                <div className="flex justify-between"><span className="text-gray-500">{t("confidenceAchieved")}</span><span className="font-semibold">{fmtPercentRaw(result.confidence_level * 100)}</span></div>
                <div className="flex justify-between"><span className="text-gray-500">{t("requiredSampleSize")}</span><span>{fmtNum(result.required_sample_size)}</span></div>
              </div>

              <div className="bg-gray-50 rounded-md p-3 text-sm text-gray-600">
                {result.recommendation}
              </div>
            </div>
          ) : (
            <div className="flex items-center justify-center h-[300px] text-gray-400 text-sm">
              {t("enterTestData")}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

/* ───────────────────────────────────────────────────── */
/*  Campaign ROI Calculator                              */
/* ───────────────────────────────────────────────────── */

function ROIPanel() {
  const t = useTranslations("predictive");
  const [form, setForm] = useState({
    campaign_name: "",
    total_cost: "",
    leads_generated: "",
    conversions: "",
    total_revenue: "",
    average_product_margin: "0.3",
  });
  const [result, setResult] = useState<CampaignROI | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);

    const res = await api<CampaignROI>("POST", "/analytics/predictive/campaign-roi", {
      campaign_name: form.campaign_name || "کمپین",
      total_cost: parseFloat(form.total_cost) || 0,
      leads_generated: parseInt(form.leads_generated) || 0,
      conversions: parseInt(form.conversions) || 0,
      total_revenue: parseFloat(form.total_revenue) || 0,
      average_product_margin: parseFloat(form.average_product_margin) || 0.3,
    });

    if (res.ok) {
      setResult(res.data);
    } else {
      setError(t("calcError"));
    }
    setLoading(false);
  }

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Input Form */}
        <div className="bg-white rounded-lg shadow p-5">
          <h2 className="text-sm font-semibold text-gray-700 mb-4">{t("roiCalc")}</h2>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs text-gray-500 mb-1">{t("campaignName")}</label>
              <input
                className="w-full border rounded-md px-3 py-2 text-sm"
                value={form.campaign_name}
                onChange={(e) => setForm({ ...form, campaign_name: e.target.value })}
                placeholder={t("campaignNamePlaceholder")}
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs text-gray-500 mb-1">{t("totalCost")} ({t("rial")})</label>
                <input
                  type="number"
                  className="w-full border rounded-md px-3 py-2 text-sm"
                  value={form.total_cost}
                  onChange={(e) => setForm({ ...form, total_cost: e.target.value })}
                  placeholder="10000000"
                  required
                />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">{t("totalRevenue")} ({t("rial")})</label>
                <input
                  type="number"
                  className="w-full border rounded-md px-3 py-2 text-sm"
                  value={form.total_revenue}
                  onChange={(e) => setForm({ ...form, total_revenue: e.target.value })}
                  placeholder="50000000"
                  required
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs text-gray-500 mb-1">{t("leadsGenerated")}</label>
                <input
                  type="number"
                  className="w-full border rounded-md px-3 py-2 text-sm"
                  value={form.leads_generated}
                  onChange={(e) => setForm({ ...form, leads_generated: e.target.value })}
                  placeholder="500"
                  required
                />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">{t("totalConversions")}</label>
                <input
                  type="number"
                  className="w-full border rounded-md px-3 py-2 text-sm"
                  value={form.conversions}
                  onChange={(e) => setForm({ ...form, conversions: e.target.value })}
                  placeholder="50"
                  required
                />
              </div>
            </div>

            <div>
              <label className="block text-xs text-gray-500 mb-1">{t("productMargin")}</label>
              <select
                className="w-full border rounded-md px-3 py-2 text-sm"
                value={form.average_product_margin}
                onChange={(e) => setForm({ ...form, average_product_margin: e.target.value })}
              >
                <option value="0.1">10%</option>
                <option value="0.2">20%</option>
                <option value="0.3">30%</option>
                <option value="0.4">40%</option>
                <option value="0.5">50%</option>
              </select>
            </div>

            {error && <div className="text-red-500 text-sm">{error}</div>}

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-blue-600 text-white px-4 py-2 rounded-md text-sm hover:bg-blue-700 disabled:opacity-50"
            >
              {loading ? t("calculating") : t("calculate")}
            </button>
          </form>
        </div>

        {/* Results */}
        <div className="bg-white rounded-lg shadow p-5">
          <h2 className="text-sm font-semibold text-gray-700 mb-4">{t("roiResults")}</h2>
          {result ? (
            <div className="space-y-4">
              <div className={cn(
                "text-center p-4 rounded-lg",
                result.roi_percent > 0 ? "bg-green-50 border border-green-200" : "bg-red-50 border border-red-200"
              )}>
                <div className="text-xs text-gray-500">{t("roiPercent")}</div>
                <div className={cn(
                  "text-3xl font-bold",
                  result.roi_percent > 0 ? "text-green-700" : "text-red-700"
                )}>
                  {result.roi_percent > 0 ? "+" : ""}{result.roi_percent.toFixed(1)}%
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="bg-gray-50 rounded-md p-3">
                  <div className="text-xs text-gray-500">{t("costPerLead")}</div>
                  <div className="text-sm font-bold">{fmtCurrency(result.cost_per_lead)}</div>
                </div>
                <div className="bg-gray-50 rounded-md p-3">
                  <div className="text-xs text-gray-500">{t("costPerConversion")}</div>
                  <div className="text-sm font-bold">{fmtCurrency(result.cost_per_conversion)}</div>
                </div>
                <div className="bg-gray-50 rounded-md p-3">
                  <div className="text-xs text-gray-500">{t("conversionRate")}</div>
                  <div className="text-sm font-bold">{fmtPercentRaw(result.conversion_rate * 100)}</div>
                </div>
                <div className="bg-gray-50 rounded-md p-3">
                  <div className="text-xs text-gray-500">{t("revenuePerLead")}</div>
                  <div className="text-sm font-bold">{fmtCurrency(result.revenue_per_lead)}</div>
                </div>
              </div>

              <div className="space-y-2 text-sm">
                <div className="flex justify-between"><span className="text-gray-500">{t("totalCost")}</span><span>{fmtCurrency(result.total_cost)}</span></div>
                <div className="flex justify-between"><span className="text-gray-500">{t("totalRevenue")}</span><span>{fmtCurrency(result.total_revenue)}</span></div>
                <div className="flex justify-between"><span className="text-gray-500">{t("breakEven")}</span><span>{fmtNum(result.break_even_conversions)} {t("conversionsNeeded")}</span></div>
              </div>
            </div>
          ) : (
            <div className="flex items-center justify-center h-[300px] text-gray-400 text-sm">
              {t("enterCampaignData")}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

/* ───────────────────────────────────────────────────── */
/*  Retention Curves Panel                               */
/* ───────────────────────────────────────────────────── */

function RetentionPanel() {
  const t = useTranslations("predictive");
  const tc = useTranslations("common");
  const [periodType, setPeriodType] = useState<"weekly" | "monthly">("weekly");
  const { data, isLoading } = useApi<RetentionAnalysis>(
    `/analytics/predictive/retention?period_type=${periodType}&num_cohorts=8&num_periods=8`
  );

  if (isLoading) return <Loading />;
  if (!data) return <NoData />;

  // Build chart data from average_retention_by_period
  const chartData = Object.entries(data.average_retention_by_period)
    .sort(([a], [b]) => parseInt(a) - parseInt(b))
    .map(([period, rate]) => ({
      period: periodType === "weekly" ? `${t("week")} ${period}` : `${t("month")} ${period}`,
      retention: +(rate * 100).toFixed(1),
    }));

  return (
    <div className="space-y-6">
      {/* Summary Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title={t("totalCohorts")}
          value={fmtNum(data.cohorts.length)}
          icon="📊"
          color="text-blue-600"
        />
        <StatCard
          title={t("overallChurn")}
          value={fmtPercentRaw(data.overall_churn_rate * 100)}
          icon="📉"
          color="text-red-600"
        />
        <StatCard
          title={t("periodType")}
          value={periodType === "weekly" ? t("weekly") : t("monthly")}
          icon="📅"
          color="text-purple-600"
        />
        <StatCard
          title={t("analysisDate")}
          value={new Date(data.analysis_date).toLocaleDateString("fa-IR")}
          icon="🕐"
          color="text-gray-600"
        />
      </div>

      {/* Period type selector */}
      <div className="flex gap-2">
        <button
          onClick={() => setPeriodType("weekly")}
          className={cn(
            "px-4 py-2 text-sm rounded-md",
            periodType === "weekly" ? "bg-blue-600 text-white" : "bg-gray-100 text-gray-600"
          )}
        >
          {t("weekly")}
        </button>
        <button
          onClick={() => setPeriodType("monthly")}
          className={cn(
            "px-4 py-2 text-sm rounded-md",
            periodType === "monthly" ? "bg-blue-600 text-white" : "bg-gray-100 text-gray-600"
          )}
        >
          {t("monthly")}
        </button>
      </div>

      {/* Retention Curve Chart */}
      <div className="bg-white rounded-lg shadow p-5">
        <h2 className="text-sm font-semibold text-gray-700 mb-4">{t("retentionCurve")}</h2>
        {chartData.length > 0 ? (
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={chartData} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
              <XAxis dataKey="period" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} domain={[0, 100]} unit="%" />
              <Tooltip
                formatter={(value) => [`${value}%`, t("retentionRate")]}
              />
              <Line
                type="monotone"
                dataKey="retention"
                stroke="#3b82f6"
                strokeWidth={3}
                dot={{ r: 5, fill: "#3b82f6" }}
                name="retention"
              />
            </LineChart>
          </ResponsiveContainer>
        ) : (
          <div className="flex items-center justify-center h-[300px] text-gray-400 text-sm">
            {tc("noData")}
          </div>
        )}
      </div>

      {/* Cohort Table */}
      {data.cohorts.length > 0 && (
        <div className="bg-white rounded-lg shadow p-5">
          <h2 className="text-sm font-semibold text-gray-700 mb-4">{t("cohortDetails")}</h2>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-xs text-gray-500 border-b">
                  <th className="text-start py-2 px-3">{t("cohort")}</th>
                  <th className="text-start py-2 px-3">{t("cohortSize")}</th>
                  {Array.from({ length: Math.min(9, Object.keys(data.cohorts[0]?.retention_by_period || {}).length) }, (_, i) => (
                    <th key={i} className="text-center py-2 px-2 text-xs">
                      P{i}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.cohorts.map((cohort) => (
                  <tr key={cohort.cohort_label} className="border-b hover:bg-gray-50">
                    <td className="py-2 px-3 text-xs">{cohort.cohort_label}</td>
                    <td className="py-2 px-3">{fmtNum(cohort.cohort_size)}</td>
                    {Array.from({ length: Math.min(9, Object.keys(cohort.retention_by_period).length) }, (_, i) => {
                      const rate = cohort.retention_by_period[String(i)] ?? 0;
                      const pct = rate * 100;
                      const bg = pct > 50 ? `rgba(34,197,94,${pct / 100 * 0.4})` : `rgba(239,68,68,${(100 - pct) / 100 * 0.3})`;
                      return (
                        <td key={i} className="py-2 px-2 text-center text-xs" style={{ backgroundColor: bg }}>
                          {pct.toFixed(0)}%
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

/* ───────────────────────────────────────────────────── */
/*  Shared Components                                    */
/* ───────────────────────────────────────────────────── */

function Loading() {
  const tc = useTranslations("common");
  return (
    <div className="flex items-center justify-center h-64 text-gray-400 text-sm">
      {tc("loading")}
    </div>
  );
}

function NoData() {
  const tc = useTranslations("common");
  return (
    <div className="flex items-center justify-center h-64 text-gray-400 text-sm">
      {tc("noData")}
    </div>
  );
}

