"use client";

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";
import { useTranslations } from "next-intl";
import { useFormat } from "@/lib/use-format";
import { STAGE_LABELS, STAGE_COLORS } from "@/lib/constants";

import type { StageCount } from "@/types/analytics";

interface FunnelBarChartProps {
  data: StageCount[];
}

export default function FunnelBarChart({ data }: FunnelBarChartProps) {
  const t = useTranslations("charts");
  const fmt = useFormat();

  const chartData = data.map((s) => ({
    name: STAGE_LABELS[s.stage] || s.stage,
    value: s.count,
    stage: s.stage,
    percentage: s.percentage,
  }));

  return (
    <ResponsiveContainer width="100%" height={280}>
      <BarChart data={chartData} layout="vertical" margin={{ right: 40 }}>
        <XAxis type="number" tick={{ fontSize: 11 }} />
        <YAxis
          type="category"
          dataKey="name"
          width={100}
          tick={{ fontSize: 12 }}
        />
        <Tooltip
          formatter={(value) => [fmt.number(value as number), t("count")]}
        />
        <Bar dataKey="value" radius={[0, 6, 6, 0]}>
          {chartData.map((entry) => (
            <Cell
              key={entry.stage}
              fill={STAGE_COLORS[entry.stage] || "#6b7280"}
            />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

