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
import { STAGE_LABELS, STAGE_COLORS } from "@/lib/constants";
import { fmtNum } from "@/lib/utils";
import type { StageCount } from "@/types/analytics";

interface FunnelBarChartProps {
  data: StageCount[];
}

export default function FunnelBarChart({ data }: FunnelBarChartProps) {
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
          tick={{ fontSize: 12, fontFamily: "Shabnam" }}
        />
        <Tooltip
          formatter={(value) => [fmtNum(value as number), "تعداد"]}
          labelStyle={{ fontFamily: "Shabnam" }}
          contentStyle={{ fontFamily: "Shabnam", direction: "rtl" }}
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

