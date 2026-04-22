"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { apiPost } from "@/lib/api-client";
import { useApi } from "@/lib/hooks";
import type { ABTestConfig, ABTestLaunchRequest, ABTestWinnerResponse } from "@/types/ab-test";

interface Props {
  campaignId: string;
  campaignName: string;
  onClose: () => void;
}

export default function ABTestModal({ campaignId, campaignName, onClose }: Props) {
  const t = useTranslations("abTest");
  const { data: config, isLoading, refetch } = useApi<ABTestConfig>(
    `/campaigns/${campaignId}/ab-test`
  );

  const [variantAContent, setVariantAContent] = useState("");
  const [variantBContent, setVariantBContent] = useState("");
  const [splitPercent, setSplitPercent] = useState(50);
  const [launching, setLaunching] = useState(false);
  const [declaring, setDeclaring] = useState(false);
  const [winnerResult, setWinnerResult] = useState<ABTestWinnerResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleLaunch() {
    if (!variantAContent.trim() || !variantBContent.trim()) {
      setError(t("contentRequired"));
      return;
    }
    setLaunching(true);
    setError(null);
    const payload: ABTestLaunchRequest = {
      variant_a_content: variantAContent,
      variant_b_content: variantBContent,
      split_percent: splitPercent,
    };
    const res = await apiPost<ABTestConfig>(`/campaigns/${campaignId}/ab-test/launch`, payload);
    setLaunching(false);
    if (res.ok) {
      refetch();
    } else {
      setError(res.error || t("launchFailed"));
    }
  }

  async function handleDeclareWinner() {
    setDeclaring(true);
    const res = await apiPost<ABTestWinnerResponse>(
      `/campaigns/${campaignId}/ab-test/winner`,
      {}
    );
    setDeclaring(false);
    if (res.ok && res.data) {
      setWinnerResult(res.data);
      refetch();
    }
  }

  const MetricRow = ({
    label,
    valueA,
    valueB,
    isPercent,
  }: {
    label: string;
    valueA: number;
    valueB: number;
    isPercent?: boolean;
  }) => {
    const fmt = (v: number) => isPercent ? `${(v * 100).toFixed(1)}%` : v.toLocaleString();
    const better = valueA >= valueB ? "A" : "B";
    return (
      <tr className="border-b last:border-0">
        <td className="py-1.5 text-sm text-gray-600 w-1/3">{label}</td>
        <td className={`py-1.5 text-sm text-center font-medium ${better === "A" ? "text-green-700" : "text-gray-700"}`}>
          {fmt(valueA)}
        </td>
        <td className={`py-1.5 text-sm text-center font-medium ${better === "B" ? "text-green-700" : "text-gray-700"}`}>
          {fmt(valueB)}
        </td>
      </tr>
    );
  };

  return (
    <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-2xl p-6 space-y-5 max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between">
          <h2 className="font-semibold text-gray-800">{t("title")} — {campaignName}</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-xl">✕</button>
        </div>

        {error && <p className="text-sm text-red-600 bg-red-50 rounded-lg px-3 py-2">{error}</p>}

        {isLoading && <p className="text-sm text-gray-400">{t("loading")}</p>}

        {/* Active test results */}
        {config && (
          <div className="space-y-3">
            <div className="flex items-center gap-3">
              <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${config.is_complete ? "bg-emerald-100 text-emerald-700" : "bg-blue-100 text-blue-700"}`}>
                {config.is_complete ? t("complete") : t("running")}
              </span>
              <span className="text-xs text-gray-500">{t("split")}: {config.split_percent}% / {100 - config.split_percent}%</span>
              {config.winner && (
                <span className="text-xs font-semibold text-emerald-700">🏆 {t("winner")}: {t(`variant${config.winner}`)}</span>
              )}
            </div>

            <table className="w-full">
              <thead>
                <tr className="border-b">
                  <th className="py-1.5 text-xs text-gray-500 text-start w-1/3">{t("metric")}</th>
                  <th className="py-1.5 text-xs text-gray-500 text-center">{t("variantA")}</th>
                  <th className="py-1.5 text-xs text-gray-500 text-center">{t("variantB")}</th>
                </tr>
              </thead>
              <tbody>
                <MetricRow label={t("recipients")} valueA={config.variant_a.recipient_count} valueB={config.variant_b.recipient_count} />
                <MetricRow label={t("sent")} valueA={config.variant_a.sent_count} valueB={config.variant_b.sent_count} />
                <MetricRow label={t("deliveryRate")} valueA={config.variant_a.delivery_rate} valueB={config.variant_b.delivery_rate} isPercent />
                <MetricRow label={t("responseRate")} valueA={config.variant_a.response_rate} valueB={config.variant_b.response_rate} isPercent />
                <MetricRow label={t("conversionRate")} valueA={config.variant_a.conversion_rate} valueB={config.variant_b.conversion_rate} isPercent />
              </tbody>
            </table>

            {winnerResult && (
              <div className="bg-emerald-50 rounded-lg p-3 text-sm text-emerald-800">
                {winnerResult.message} ({(winnerResult.confidence * 100).toFixed(0)}% {t("confidence")})
              </div>
            )}

            {!config.is_complete && !config.winner && (
              <button
                onClick={handleDeclareWinner}
                disabled={declaring}
                className="text-sm bg-emerald-600 text-white px-4 py-2 rounded-lg hover:bg-emerald-700 disabled:opacity-50"
              >
                {declaring ? t("declaring") : t("declareWinner")}
              </button>
            )}
          </div>
        )}

        {/* Launch new test form */}
        {!config && !isLoading && (
          <div className="space-y-4">
            <p className="text-sm text-gray-500">{t("noTestYet")}</p>

            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">{t("variantAContent")}</label>
              <textarea
                rows={3}
                value={variantAContent}
                onChange={(e) => setVariantAContent(e.target.value)}
                className="border rounded-lg px-3 py-2 text-sm w-full resize-none"
                placeholder={t("contentPlaceholder")}
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">{t("variantBContent")}</label>
              <textarea
                rows={3}
                value={variantBContent}
                onChange={(e) => setVariantBContent(e.target.value)}
                className="border rounded-lg px-3 py-2 text-sm w-full resize-none"
                placeholder={t("contentPlaceholder")}
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">
                {t("splitPercent")}: {splitPercent}% A / {100 - splitPercent}% B
              </label>
              <input
                type="range"
                min={10}
                max={90}
                step={5}
                value={splitPercent}
                onChange={(e) => setSplitPercent(+e.target.value)}
                className="w-full"
              />
            </div>

            <button
              onClick={handleLaunch}
              disabled={launching}
              className="w-full bg-blue-600 text-white py-2 rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
            >
              {launching ? t("launching") : t("launch")}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

