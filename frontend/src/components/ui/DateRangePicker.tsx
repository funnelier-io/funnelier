"use client";

import { useState, useCallback } from "react";
import { useTranslations } from "next-intl";

interface DateRangePickerProps {
  startDate: string;
  endDate: string;
  onChange: (start: string, end: string) => void;
}

const PRESETS: { labelKey: string; days: number }[] = [
  { labelKey: "7days", days: 7 },
  { labelKey: "30days", days: 30 },
  { labelKey: "90days", days: 90 },
  { labelKey: "1year", days: 365 },
];

function toISODate(d: Date): string {
  return d.toISOString().split("T")[0];
}

function daysAgo(n: number): string {
  const d = new Date();
  d.setDate(d.getDate() - n);
  return toISODate(d);
}

export default function DateRangePicker({
  startDate,
  endDate,
  onChange,
}: DateRangePickerProps) {
  const [showCustom, setShowCustom] = useState(false);
  const t = useTranslations("dateRange");

  const handlePreset = useCallback(
    (days: number) => {
      onChange(daysAgo(days), toISODate(new Date()));
      setShowCustom(false);
    },
    [onChange]
  );

  const today = toISODate(new Date());
  const activeDays = PRESETS.find(
    (p) => daysAgo(p.days) === startDate && endDate === today
  )?.days;

  return (
    <div className="flex flex-wrap items-center gap-2">
      {PRESETS.map((preset) => (
        <button
          key={preset.days}
          onClick={() => handlePreset(preset.days)}
          className={`px-2.5 py-1 rounded-lg text-xs transition-colors ${
            activeDays === preset.days && !showCustom
              ? "bg-blue-600 text-white"
              : "bg-gray-100 text-gray-600 hover:bg-gray-200"
          }`}
        >
          {t(preset.labelKey)}
        </button>
      ))}

      <button
        onClick={() => setShowCustom(!showCustom)}
        className={`px-2.5 py-1 rounded-lg text-xs transition-colors ${
          showCustom ? "bg-blue-600 text-white" : "bg-gray-100 text-gray-600 hover:bg-gray-200"
        }`}
      >
        📅 {t("custom")}
      </button>

      {showCustom && (
        <div className="flex items-center gap-2">
          <label className="text-xs text-gray-500">{t("from")}</label>
          <input
            type="date"
            value={startDate}
            onChange={(e) => onChange(e.target.value, endDate)}
            className="px-2 py-1 border border-gray-300 rounded-lg text-xs focus:outline-none focus:ring-2 focus:ring-blue-500"
            dir="ltr"
          />
          <label className="text-xs text-gray-500">{t("to")}</label>
          <input
            type="date"
            value={endDate}
            onChange={(e) => onChange(startDate, e.target.value)}
            className="px-2 py-1 border border-gray-300 rounded-lg text-xs focus:outline-none focus:ring-2 focus:ring-blue-500"
            dir="ltr"
          />
        </div>
      )}
    </div>
  );
}

