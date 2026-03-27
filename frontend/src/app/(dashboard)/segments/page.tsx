"use client";

import { useApi } from "@/lib/hooks";
import StatCard from "@/components/ui/StatCard";
import RFMDoughnutChart from "@/components/charts/RFMDoughnutChart";
import { fmtNum, fmtPercent } from "@/lib/utils";
import { SEGMENT_LABELS, SEGMENT_COLORS } from "@/lib/constants";
import type { SegmentDistribution } from "@/types/segments";
import type { AllRecommendationsResponse, SegmentRecommendation } from "@/types/segments";

export default function SegmentsPage() {
  const dist = useApi<SegmentDistribution>("/segments/distribution");
  const recs = useApi<AllRecommendationsResponse>("/segments/recommendations");

  const activeSegments = dist.data?.segments?.filter((s) => s.count > 0) || [];

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-bold">بخش‌بندی RFM</h1>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="کل مخاطبین"
          value={fmtNum(dist.data?.total_contacts)}
          icon="👥"
          color="text-blue-600"
        />
        <StatCard
          title="بخش‌های فعال"
          value={fmtNum(activeSegments.length)}
          icon="🎯"
          color="text-green-600"
        />
        <StatCard
          title="تاریخ تحلیل"
          value={
            dist.data?.analysis_date
              ? new Date(dist.data.analysis_date).toLocaleDateString("fa-IR")
              : "—"
          }
          icon="📅"
          color="text-amber-600"
        />
        <StatCard
          title="کل بخش‌ها"
          value={fmtNum(dist.data?.segments?.length)}
          icon="📊"
          color="text-purple-600"
        />
      </div>

      {/* RFM Chart + Segment List */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white rounded-lg shadow p-5">
          <h2 className="text-sm font-semibold text-gray-700 mb-4">
            نمودار توزیع بخش‌ها
          </h2>
          {dist.data?.segments ? (
            <RFMDoughnutChart data={dist.data.segments} />
          ) : (
            <div className="h-[280px] flex items-center justify-center text-gray-400 text-sm">
              {dist.isLoading ? "در حال بارگذاری..." : "داده‌ای موجود نیست"}
            </div>
          )}
        </div>

        <div className="bg-white rounded-lg shadow p-5">
          <h2 className="text-sm font-semibold text-gray-700 mb-4">
            جزئیات بخش‌ها
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
                  <span className="text-sm font-semibold">{fmtNum(s.count)}</span>
                  <span className="text-xs text-gray-400">
                    {fmtPercent(s.percentage / 100)}
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
          <h2 className="text-lg font-semibold">پیشنهادات بازاریابی</h2>
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
  return (
    <div className="bg-white rounded-lg shadow p-5 space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="font-semibold text-gray-800">
          {SEGMENT_LABELS[rec.segment] || rec.segment_name_fa}
        </h3>
        {rec.discount_allowed && (
          <span className="text-xs bg-green-50 text-green-700 px-2 py-0.5 rounded-full">
            تخفیف تا {rec.max_discount_percent}%
          </span>
        )}
      </div>

      <p className="text-xs text-gray-500 leading-5">{rec.description_fa}</p>

      <div className="space-y-2">
        <div>
          <span className="text-xs text-gray-400">نوع پیام:</span>
          <div className="flex flex-wrap gap-1 mt-1">
            {rec.recommended_message_types.map((t) => (
              <span
                key={t}
                className="text-xs bg-blue-50 text-blue-700 px-2 py-0.5 rounded"
              >
                {t}
              </span>
            ))}
          </div>
        </div>

        {rec.recommended_products.length > 0 && (
          <div>
            <span className="text-xs text-gray-400">محصولات پیشنهادی:</span>
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
          <span>فراوانی تماس: {rec.contact_frequency}</span>
          <span>
            کانال: {rec.channel_priority.join(" → ")}
          </span>
        </div>
      </div>
    </div>
  );
}

