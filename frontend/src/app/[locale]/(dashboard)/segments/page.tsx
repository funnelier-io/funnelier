"use client";

import { useTranslations } from "next-intl";
import { useFormat } from "@/lib/use-format";
import { useApi } from "@/lib/hooks";
import StatCard from "@/components/ui/StatCard";
import RFMDoughnutChart from "@/components/charts/RFMDoughnutChart";

import { SEGMENT_LABELS, SEGMENT_COLORS } from "@/lib/constants";
import type { SegmentDistribution } from "@/types/segments";
import type { AllRecommendationsResponse, SegmentRecommendation } from "@/types/segments";

export default function SegmentsPage() {
  const t = useTranslations("segments");
  const fmt = useFormat();
  const tc = useTranslations("common");
  const dist = useApi<SegmentDistribution>("/segments/distribution");
  const recs = useApi<AllRecommendationsResponse>("/segments/recommendations");

  const activeSegments = dist.data?.segments?.filter((s) => s.count > 0) || [];

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-bold">{t("title")}</h1>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title={t("totalContacts")}
          value={fmt.number(dist.data?.total_contacts)}
          icon="👥"
          color="text-blue-600"
        />
        <StatCard
          title={t("activeSegments")}
          value={fmt.number(activeSegments.length)}
          icon="🎯"
          color="text-green-600"
        />
        <StatCard
          title={t("analysisDate")}
          value={
            dist.data?.analysis_date
              ? new Date(dist.data.analysis_date).toLocaleDateString("fa-IR")
              : "—"
          }
          icon="📅"
          color="text-amber-600"
        />
        <StatCard
          title={t("totalSegments")}
          value={fmt.number(dist.data?.segments?.length)}
          icon="📊"
          color="text-purple-600"
        />
      </div>

      {/* RFM Chart + Segment List */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white rounded-lg shadow p-5">
          <h2 className="text-sm font-semibold text-gray-700 mb-4">
            {t("distributionChart")}
          </h2>
          {dist.data?.segments ? (
            <RFMDoughnutChart data={dist.data.segments} />
          ) : (
            <div className="h-[280px] flex items-center justify-center text-gray-400 text-sm">
              {dist.isLoading ? tc("loading") : tc("noData")}
            </div>
          )}
        </div>

        <div className="bg-white rounded-lg shadow p-5">
          <h2 className="text-sm font-semibold text-gray-700 mb-4">
            {t("segmentDetails")}
          </h2>
          <div className="space-y-2 max-h-[320px] overflow-y-auto">
            {dist.data?.segments?.map((s, i) => (
              <div
                key={s.segment}
                className="flex items-center justify-between p-2.5 rounded-md hover:bg-gray-50"
              >
                <div className="flex items-center gap-2">
                  <div
                    className="w-3 h-3 rounded-full"
                    style={{
                      backgroundColor: SEGMENT_COLORS[i % SEGMENT_COLORS.length],
                    }}
                  />
                  <span className="text-sm">
                    {SEGMENT_LABELS[s.segment] || s.segment_name_fa}
                  </span>
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-sm font-semibold">{fmt.number(s.count)}</span>
                  <span className="text-xs text-gray-400">
                    {fmt.percentRaw(s.percentage)}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Recommendations */}
      {recs.data?.recommendations && recs.data.recommendations.length > 0 && (
        <div className="space-y-4">
          <h2 className="text-lg font-semibold">{t("marketingRecommendations")}</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {recs.data.recommendations.map((rec: SegmentRecommendation) => (
              <RecommendationCard key={rec.segment} rec={rec} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function RecommendationCard({ rec }: { rec: SegmentRecommendation }) {
  const t = useTranslations("segments");

  return (
    <div className="bg-white rounded-lg shadow p-5 space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="font-semibold text-gray-800">
          {SEGMENT_LABELS[rec.segment] || rec.segment_name_fa}
        </h3>
        {rec.discount_allowed && (
          <span className="text-xs bg-green-50 text-green-700 px-2 py-0.5 rounded-full">
            {t("discountAllowed", { percent: rec.max_discount_percent })}
          </span>
        )}
      </div>

      <p className="text-xs text-gray-500 leading-5">{rec.description_fa}</p>

      <div className="space-y-2">
        <div>
          <span className="text-xs text-gray-400">{t("messageType")}</span>
          <div className="flex flex-wrap gap-1 mt-1">
            {rec.recommended_message_types.map((mt) => (
              <span
                key={mt}
                className="text-xs bg-blue-50 text-blue-700 px-2 py-0.5 rounded"
              >
                {mt}
              </span>
            ))}
          </div>
        </div>

        {rec.recommended_products.length > 0 && (
          <div>
            <span className="text-xs text-gray-400">{t("recommendedProducts")}</span>
            <div className="flex flex-wrap gap-1 mt-1">
              {rec.recommended_products.map((p) => (
                <span
                  key={p}
                  className="text-xs bg-amber-50 text-amber-700 px-2 py-0.5 rounded"
                >
                  {p}
                </span>
              ))}
            </div>
          </div>
        )}

        <div className="flex items-center justify-between text-xs text-gray-400 pt-1 border-t">
          <span>{t("contactFrequency", { freq: rec.contact_frequency })}</span>
          <span>
            {t("channel", { channels: rec.channel_priority.join(" → ") })}
          </span>
        </div>
      </div>
    </div>
  );
}

