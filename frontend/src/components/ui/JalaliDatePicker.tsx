"use client";

/**
 * Locale-aware date picker:
 * - Persian locale: Jalali (Shamsi) calendar
 * - English locale: Gregorian calendar
 */

import { useState, useMemo, useCallback } from "react";
import { useLocale, useTranslations } from "next-intl";
import {
  dateToJalali,
  jalaliToDate,
  jalaliDaysInMonth,
  jalaliDayOfWeek,
  JALALI_MONTHS,
  JALALI_WEEKDAYS_SHORT,
  toPersianDigits,
} from "@/lib/format";
import { cn } from "@/lib/utils";

interface JalaliDatePickerProps {
  /** ISO date string "YYYY-MM-DD" (Gregorian) */
  value?: string;
  onChange: (isoDate: string) => void;
  /** Placeholder text */
  placeholder?: string;
  /** Additional className */
  className?: string;
}

const GREG_MONTHS = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];
const GREG_WEEKDAYS_SHORT = ["Su", "Mo", "Tu", "We", "Th", "Fr", "Sa"];

export default function JalaliDatePicker({
  value,
  onChange,
  placeholder,
  className,
}: JalaliDatePickerProps) {
  const locale = useLocale();
  const t = useTranslations("dateRange");
  const isFa = locale === "fa";

  const [open, setOpen] = useState(false);

  // Current viewed month/year (Jalali for fa, Gregorian for en)
  const today = new Date();
  const todayJalali = dateToJalali(today);

  const [viewYear, setViewYear] = useState(() =>
    isFa ? todayJalali.jy : today.getFullYear()
  );
  const [viewMonth, setViewMonth] = useState(() =>
    isFa ? todayJalali.jm : today.getMonth() + 1
  );

  // Display value
  const displayValue = useMemo(() => {
    if (!value) return "";
    if (isFa) {
      const d = new Date(value);
      if (isNaN(d.getTime())) return "";
      const j = dateToJalali(d);
      return toPersianDigits(
        `${j.jy}/${String(j.jm).padStart(2, "0")}/${String(j.jd).padStart(2, "0")}`
      );
    }
    return value;
  }, [value, isFa]);

  // Generate calendar grid
  const calendarDays = useMemo(() => {
    if (isFa) {
      const daysInMonth = jalaliDaysInMonth(viewYear, viewMonth);
      const firstDayOfWeek = jalaliDayOfWeek(viewYear, viewMonth, 1);
      const days: (number | null)[] = [];
      for (let i = 0; i < firstDayOfWeek; i++) days.push(null);
      for (let d = 1; d <= daysInMonth; d++) days.push(d);
      return days;
    } else {
      const firstDay = new Date(viewYear, viewMonth - 1, 1).getDay();
      const daysInMonth = new Date(viewYear, viewMonth, 0).getDate();
      const days: (number | null)[] = [];
      for (let i = 0; i < firstDay; i++) days.push(null);
      for (let d = 1; d <= daysInMonth; d++) days.push(d);
      return days;
    }
  }, [viewYear, viewMonth, isFa]);

  const monthNames = isFa ? JALALI_MONTHS : GREG_MONTHS;
  const weekdayHeaders = isFa ? JALALI_WEEKDAYS_SHORT : GREG_WEEKDAYS_SHORT;

  const prevMonth = useCallback(() => {
    if (viewMonth === 1) {
      setViewMonth(12);
      setViewYear((y) => y - 1);
    } else {
      setViewMonth((m) => m - 1);
    }
  }, [viewMonth]);

  const nextMonth = useCallback(() => {
    if (viewMonth === 12) {
      setViewMonth(1);
      setViewYear((y) => y + 1);
    } else {
      setViewMonth((m) => m + 1);
    }
  }, [viewMonth]);

  const selectDay = useCallback(
    (day: number) => {
      if (isFa) {
        const d = jalaliToDate(viewYear, viewMonth, day);
        const iso = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
        onChange(iso);
      } else {
        const iso = `${viewYear}-${String(viewMonth).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
        onChange(iso);
      }
      setOpen(false);
    },
    [viewYear, viewMonth, isFa, onChange]
  );

  // Check if a day is selected
  const isSelected = useCallback(
    (day: number) => {
      if (!value) return false;
      const d = new Date(value);
      if (isNaN(d.getTime())) return false;
      if (isFa) {
        const j = dateToJalali(d);
        return j.jy === viewYear && j.jm === viewMonth && j.jd === day;
      }
      return (
        d.getFullYear() === viewYear &&
        d.getMonth() + 1 === viewMonth &&
        d.getDate() === day
      );
    },
    [value, viewYear, viewMonth, isFa]
  );

  // Check if a day is today
  const isToday = useCallback(
    (day: number) => {
      if (isFa) {
        return (
          todayJalali.jy === viewYear &&
          todayJalali.jm === viewMonth &&
          todayJalali.jd === day
        );
      }
      return (
        today.getFullYear() === viewYear &&
        today.getMonth() + 1 === viewMonth &&
        today.getDate() === day
      );
    },
    [viewYear, viewMonth, isFa, todayJalali, today]
  );

  const yearDisplay = isFa ? toPersianDigits(viewYear) : String(viewYear);

  return (
    <div className={cn("relative inline-block", className)}>
      {/* Input */}
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="w-full flex items-center gap-2 px-3 py-2 text-sm border border-gray-300 rounded-lg bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500 text-start"
      >
        <svg className="w-4 h-4 text-gray-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
        </svg>
        <span className={displayValue ? "text-gray-900" : "text-gray-400"}>
          {displayValue || placeholder || t("custom")}
        </span>
      </button>

      {/* Calendar dropdown */}
      {open && (
        <>
          {/* Backdrop */}
          <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} />

          <div
            className={cn(
              "absolute z-50 mt-1 p-3 bg-white rounded-xl shadow-xl border border-gray-200 w-72",
              isFa ? "right-0" : "left-0"
            )}
          >
            {/* Month navigation */}
            <div className="flex items-center justify-between mb-3">
              <button
                onClick={isFa ? nextMonth : prevMonth}
                className="w-7 h-7 flex items-center justify-center rounded-full hover:bg-gray-100 text-gray-500"
              >
                {isFa ? "›" : "‹"}
              </button>
              <span className="text-sm font-semibold">
                {monthNames[viewMonth - 1]} {yearDisplay}
              </span>
              <button
                onClick={isFa ? prevMonth : nextMonth}
                className="w-7 h-7 flex items-center justify-center rounded-full hover:bg-gray-100 text-gray-500"
              >
                {isFa ? "‹" : "›"}
              </button>
            </div>

            {/* Weekday headers */}
            <div className="grid grid-cols-7 gap-0.5 mb-1">
              {weekdayHeaders.map((wd) => (
                <div
                  key={wd}
                  className="text-center text-[10px] font-medium text-gray-400 py-1"
                >
                  {wd}
                </div>
              ))}
            </div>

            {/* Days grid */}
            <div className="grid grid-cols-7 gap-0.5">
              {calendarDays.map((day, i) =>
                day === null ? (
                  <div key={`e-${i}`} />
                ) : (
                  <button
                    key={day}
                    onClick={() => selectDay(day)}
                    className={cn(
                      "w-9 h-9 flex items-center justify-center rounded-full text-sm transition-colors",
                      isSelected(day)
                        ? "bg-blue-600 text-white font-semibold"
                        : isToday(day)
                          ? "bg-blue-50 text-blue-600 font-medium"
                          : "hover:bg-gray-100 text-gray-700"
                    )}
                  >
                    {isFa ? toPersianDigits(day) : day}
                  </button>
                )
              )}
            </div>

            {/* Today button */}
            <div className="mt-2 pt-2 border-t border-gray-100">
              <button
                onClick={() => {
                  const iso = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}-${String(today.getDate()).padStart(2, "0")}`;
                  onChange(iso);
                  if (isFa) {
                    setViewYear(todayJalali.jy);
                    setViewMonth(todayJalali.jm);
                  } else {
                    setViewYear(today.getFullYear());
                    setViewMonth(today.getMonth() + 1);
                  }
                  setOpen(false);
                }}
                className="w-full text-center text-xs text-blue-600 hover:text-blue-700 py-1"
              >
                {isFa ? "امروز" : "Today"}
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

