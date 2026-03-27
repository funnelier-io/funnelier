"use client";

import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer, Legend } from "recharts";
import { SEGMENT_LABELS, SEGMENT_COLORS } from "@/lib/constants";
import { fmtNum } from "@/lib/utils";
import type { SegmentCount } from "@/types/segments";

interface RFMDoughnutChartProps {
  data: SegmentCount[];
}

export default function RFMDoughnutChart({ data }: RFMDoughnutChartProps) {
  const chartData = data
    .filter((s) => s.count > 0)
    .map((s) => ({
      name: SEGMENT_LABELS[s.segment] || s.segment_name_fa || s.segment,
      value: s.count,
      segment: s.segment,
    }));

  if (chartData.length === 0) {
    return (
      <div className="flex items-center justify-center h-[280px] text-gray-400 text-sm">
        داده‌ای برای نمایش وجود ندارد
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={280}>
      <PieChart>
        <Pie
          data={chartData}
          cx="50%"
          cy="50%"
          innerRadius={50}
          outerRadius={100}
          dataKey="value"
          nameKey="name"
          paddingAngle={2}
        >
          {chartData.map((_, index) => (
            <Cell
              key={index}
              fill={SEGMENT_COLORS[index % SEGMENT_COLORS.length]}
            />
          ))}
        </Pie>
        <Tooltip
          formatter={(value) => [fmtNum(value as number), "تعداد"]}
          contentStyle={{ fontFamily: "Shabnam", direction: "rtl" }}
        />
        <Legend
          layout="vertical"
          align="right"
          verticalAlign="middle"
          wrapperStyle={{ fontFamily: "Shabnam", fontSize: 11 }}
        />
      </PieChart>
    </ResponsiveContainer>
  );
}

