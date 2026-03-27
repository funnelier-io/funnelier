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
import { fmtNum, fmtDate } from "@/lib/utils";
import type { DailySnapshot } from "@/types/analytics";

interface TrendLineChartProps {
  data: DailySnapshot[];
}

export default function TrendLineChart({ data }: TrendLineChartProps) {
  if (data.length === 0) {
    return (
      <div className="flex items-center justify-center h-[300px] text-gray-400 text-sm">
        داده‌ای برای نمایش وجود ندارد
      </div>
    );
  }

  const chartData = data.map((s) => ({
    date: fmtDate(s.date),
    سرنخ_جدید: s.new_leads,
    تبدیل_جدید: s.new_conversions,
    نرخ_تبدیل: +(s.conversion_rate * 100).toFixed(1),
  }));

  return (
    <ResponsiveContainer width="100%" height={300}>
      <LineChart data={chartData} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
        <XAxis
          dataKey="date"
          tick={{ fontSize: 11, fontFamily: "Shabnam" }}
        />
        <YAxis tick={{ fontSize: 11 }} />
        <Tooltip
          contentStyle={{ fontFamily: "Shabnam", direction: "rtl" }}
          formatter={(value, name) => [fmtNum(value as number), String(name).replace(/_/g, " ")]}
        />
        <Legend wrapperStyle={{ fontFamily: "Shabnam", fontSize: 12 }} />
        <Line
          type="monotone"
          dataKey="سرنخ_جدید"
          stroke="#3b82f6"
          strokeWidth={2}
          dot={{ r: 3 }}
          name="سرنخ جدید"
        />
        <Line
          type="monotone"
          dataKey="تبدیل_جدید"
          stroke="#22c55e"
          strokeWidth={2}
          dot={{ r: 3 }}
          name="تبدیل جدید"
        />
        <Line
          type="monotone"
          dataKey="نرخ_تبدیل"
          stroke="#f59e0b"
          strokeWidth={2}
          dot={{ r: 3 }}
          name="نرخ تبدیل (%)"
        />
      </LineChart>
    </ResponsiveContainer>
  );
}

