"use client";

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from "recharts";
import { useTranslations } from "next-intl";
import { fmtCurrency } from "@/lib/utils";

interface SalesBarChartProps {
  data: { label: string; value: number; color?: string }[];
  height?: number;
}

/**
 * Simple horizontal bar chart for sales/revenue data.
 */
export default function SalesBarChart({
  data,
  height = 220,
}: SalesBarChartProps) {
  const t = useTranslations("charts");

  if (data.length === 0) {
    return (
      <div
        className="flex items-center justify-center text-gray-400 text-sm"
        style={{ height }}
      >
        {t("noDataToDisplay")}
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} margin={{ right: 10, left: 0, top: 5, bottom: 5 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
        <XAxis
          dataKey="label"
          tick={{ fontSize: 11 }}
        />
        <YAxis
          tick={{ fontSize: 10 }}
          tickFormatter={(v) => {
            if (v >= 1_000_000_000) return `${(v / 1_000_000_000).toFixed(0)}B`;
            if (v >= 1_000_000) return `${(v / 1_000_000).toFixed(0)}M`;
            if (v >= 1_000) return `${(v / 1_000).toFixed(0)}K`;
            return String(v);
          }}
        />
        <Tooltip
          formatter={(value) => [fmtCurrency(value as number), t("revenue")]}
        />
        <Bar dataKey="value" fill="#059669" radius={[4, 4, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}

