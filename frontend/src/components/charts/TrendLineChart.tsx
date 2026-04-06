"use client";

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
  Legend,
} from "recharts";
import { useTranslations } from "next-intl";
import { fmtNum, fmtDate } from "@/lib/utils";
import type { DailySnapshot } from "@/types/analytics";

interface TrendLineChartProps {
  data: DailySnapshot[];
}

export default function TrendLineChart({ data }: TrendLineChartProps) {
  const t = useTranslations("charts");

  if (data.length === 0) {
    return (
      <div className="flex items-center justify-center h-[300px] text-gray-400 text-sm">
        {t("noDataToDisplay")}
      </div>
    );
  }

  const chartData = data.map((s) => ({
    date: fmtDate(s.date),
    new_leads: s.new_leads,
    new_conversions: s.new_conversions,
    conversion_rate: +(s.conversion_rate * 100).toFixed(1),
  }));

  return (
    <ResponsiveContainer width="100%" height={300}>
      <LineChart data={chartData} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
        <XAxis
          dataKey="date"
          tick={{ fontSize: 11 }}
        />
        <YAxis tick={{ fontSize: 11 }} />
        <Tooltip
          formatter={(value, name) => {
            const labels: Record<string, string> = {
              new_leads: t("newLeads"),
              new_conversions: t("newConversions"),
              conversion_rate: t("conversionRatePercent"),
            };
            return [fmtNum(value as number), labels[name as string] || String(name)];
          }}
        />
        <Legend
          formatter={(value) => {
            const labels: Record<string, string> = {
              new_leads: t("newLeads"),
              new_conversions: t("newConversions"),
              conversion_rate: t("conversionRatePercent"),
            };
            return labels[value] || value;
          }}
          wrapperStyle={{ fontSize: 12 }}
        />
        <Line
          type="monotone"
          dataKey="new_leads"
          stroke="#3b82f6"
          strokeWidth={2}
          dot={{ r: 3 }}
          name="new_leads"
        />
        <Line
          type="monotone"
          dataKey="new_conversions"
          stroke="#22c55e"
          strokeWidth={2}
          dot={{ r: 3 }}
          name="new_conversions"
        />
        <Line
          type="monotone"
          dataKey="conversion_rate"
          stroke="#f59e0b"
          strokeWidth={2}
          dot={{ r: 3 }}
          name="conversion_rate"
        />
      </LineChart>
    </ResponsiveContainer>
  );
}

