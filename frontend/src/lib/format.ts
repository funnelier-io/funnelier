/**
 * Locale-aware formatting utilities for Funnelier.
 *
 * - Persian (fa): Jalali calendar, Persian digits (۰-۹), RTL
 * - English (en): Gregorian calendar, Latin digits, LTR
 *
 * All functions accept a `locale` parameter so they work in both server and
 * client contexts without relying on a React hook.
 */

import { toJalaali, toGregorian, jalaaliMonthLength, isLeapJalaaliYear } from "jalaali-js";

// ─── Persian digit helpers ───────────────────────────────────────────

const PERSIAN_DIGITS = "۰۱۲۳۴۵۶۷۸۹";

/** Replace ASCII digits with Persian digits. */
export function toPersianDigits(s: string | number): string {
  return String(s).replace(/[0-9]/g, (d) => PERSIAN_DIGITS[parseInt(d)]);
}

/** Replace Persian digits with ASCII digits. */
export function toLatinDigits(s: string): string {
  return s.replace(/[۰-۹]/g, (d) => String(PERSIAN_DIGITS.indexOf(d)));
}

// ─── Jalali month / day names ────────────────────────────────────────

export const JALALI_MONTHS = [
  "فروردین", "اردیبهشت", "خرداد",
  "تیر", "مرداد", "شهریور",
  "مهر", "آبان", "آذر",
  "دی", "بهمن", "اسفند",
] as const;

export const JALALI_MONTHS_SHORT = [
  "فرو", "ارد", "خرد",
  "تیر", "مرد", "شهر",
  "مهر", "آبا", "آذر",
  "دی", "بهم", "اسف",
] as const;

export const JALALI_WEEKDAYS = [
  "شنبه", "یکشنبه", "دوشنبه", "سه‌شنبه", "چهارشنبه", "پنجشنبه", "جمعه",
] as const;

export const JALALI_WEEKDAYS_SHORT = [
  "ش", "ی", "د", "س", "چ", "پ", "ج",
] as const;

const GREGORIAN_MONTHS = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
] as const;

const GREGORIAN_MONTHS_SHORT = [
  "Jan", "Feb", "Mar", "Apr", "May", "Jun",
  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
] as const;

// ─── Jalali conversion helpers ───────────────────────────────────────

export interface JalaliDate {
  jy: number;
  jm: number;
  jd: number;
}

/** Convert a JS Date to Jalali. */
export function dateToJalali(date: Date): JalaliDate {
  return toJalaali(date.getFullYear(), date.getMonth() + 1, date.getDate());
}

/** Convert a Jalali date to JS Date. */
export function jalaliToDate(jy: number, jm: number, jd: number): Date {
  const { gy, gm, gd } = toGregorian(jy, jm, jd);
  return new Date(gy, gm - 1, gd);
}

/** Get day-of-week index (0=Sat … 6=Fri) for a Jalali date. */
export function jalaliDayOfWeek(jy: number, jm: number, jd: number): number {
  const d = jalaliToDate(jy, jm, jd);
  // JS: 0=Sun … 6=Sat → Jalali week: 0=Sat
  return (d.getDay() + 1) % 7;
}

/** Get the number of days in a Jalali month. */
export function jalaliDaysInMonth(jy: number, jm: number): number {
  return jalaaliMonthLength(jy, jm);
}

/** Check if a Jalali year is leap. */
export function isJalaliLeapYear(jy: number): boolean {
  return isLeapJalaaliYear(jy);
}

/** Today as a Jalali date. */
export function jalaliToday(): JalaliDate {
  return dateToJalali(new Date());
}

// ─── Number formatting ───────────────────────────────────────────────

/**
 * Format a number with locale-appropriate digits and thousands separators.
 *
 * fa: ۱۲,۳۴۵  |  en: 12,345
 */
export function formatNumber(n: number | null | undefined, locale: string): string {
  if (n == null) return locale === "fa" ? "۰" : "0";
  const formatted = Number(n).toLocaleString("en-US");
  return locale === "fa" ? toPersianDigits(formatted) : formatted;
}

/**
 * Format a percentage value (0–1 ratio).
 *
 * 0.85 → fa: ۸۵.۰٪  |  en: 85.0%
 */
export function formatPercent(n: number | null | undefined, locale: string): string {
  if (n == null) return locale === "fa" ? "۰٪" : "0%";
  const val = (n * 100).toFixed(1);
  if (locale === "fa") return toPersianDigits(val) + "٪";
  return val + "%";
}

/**
 * Format a percentage that is already in 0–100 range.
 */
export function formatPercentRaw(n: number | null | undefined, locale: string): string {
  if (n == null) return locale === "fa" ? "۰٪" : "0%";
  const val = Number(n).toFixed(1);
  if (locale === "fa") return toPersianDigits(val) + "٪";
  return val + "%";
}

/**
 * Format currency in Toman (Rial / 10).
 *
 * fa: ۱.۲ میلیارد تومان  |  en: 1.2B Toman
 */
export function formatCurrency(
  rial: number | null | undefined,
  locale: string,
  labels?: { toman?: string; million?: string; billion?: string }
): string {
  const t = labels ?? (locale === "fa"
    ? { toman: "تومان", million: "میلیون تومان", billion: "میلیارد تومان" }
    : { toman: "Toman", million: "M Toman", billion: "B Toman" });

  if (rial == null || rial === 0) {
    return locale === "fa" ? `۰ ${t.toman}` : `0 ${t.toman}`;
  }

  const toman = Math.round(rial / 10);
  if (toman >= 1_000_000_000) {
    const val = (toman / 1_000_000_000).toFixed(1);
    return (locale === "fa" ? toPersianDigits(val) : val) + " " + t.billion;
  }
  if (toman >= 1_000_000) {
    const val = (toman / 1_000_000).toFixed(1);
    return (locale === "fa" ? toPersianDigits(val) : val) + " " + t.million;
  }
  return formatNumber(toman, locale) + " " + t.toman;
}

// ─── Date formatting ─────────────────────────────────────────────────

/**
 * Format a date string to locale-appropriate format.
 *
 * fa: ۱۴۰۵/۰۱/۱۵ ۱۴:۳۰  (Jalali)
 * en: 2026-04-04 14:30    (Gregorian)
 */
export function formatDate(
  dateStr: string | null | undefined,
  locale: string,
  options?: { withTime?: boolean; short?: boolean }
): string {
  if (!dateStr) return "-";
  try {
    const d = new Date(dateStr);
    if (isNaN(d.getTime())) return "-";

    const withTime = options?.withTime ?? true;
    const short = options?.short ?? false;

    if (locale === "fa") {
      const j = dateToJalali(d);
      const datepart = short
        ? `${j.jd} ${JALALI_MONTHS_SHORT[j.jm - 1]}`
        : `${j.jy}/${String(j.jm).padStart(2, "0")}/${String(j.jd).padStart(2, "0")}`;
      if (!withTime) return toPersianDigits(datepart);
      const time = `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
      return toPersianDigits(datepart + " " + time);
    }

    // English
    const datepart = short
      ? `${GREGORIAN_MONTHS_SHORT[d.getMonth()]} ${d.getDate()}`
      : `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
    if (!withTime) return datepart;
    const time = `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
    return datepart + " " + time;
  } catch {
    return "-";
  }
}

/**
 * Format a date to show only the date part (no time).
 */
export function formatDateOnly(dateStr: string | null | undefined, locale: string): string {
  return formatDate(dateStr, locale, { withTime: false });
}

/**
 * Format a date in short form: "15 فرو" or "Apr 15".
 */
export function formatDateShort(dateStr: string | null | undefined, locale: string): string {
  return formatDate(dateStr, locale, { withTime: false, short: true });
}

/**
 * Format a relative time string: "2 روز پیش" or "2 days ago".
 */
export function formatRelativeTime(
  dateStr: string | null | undefined,
  locale: string,
  labels?: { now?: string; ago?: string; inFuture?: string; days?: string; hours?: string; minutes?: string }
): string {
  if (!dateStr) return "-";
  try {
    const d = new Date(dateStr);
    if (isNaN(d.getTime())) return "-";

    const t = labels ?? (locale === "fa"
      ? { now: "همین الان", ago: "پیش", inFuture: "بعد", days: "روز", hours: "ساعت", minutes: "دقیقه" }
      : { now: "just now", ago: "ago", inFuture: "from now", days: "days", hours: "hours", minutes: "minutes" });

    const diffMs = Date.now() - d.getTime();
    const absDiff = Math.abs(diffMs);
    const suffix = diffMs >= 0 ? t.ago : t.inFuture;

    const minutes = Math.floor(absDiff / 60_000);
    if (minutes < 1) return t.now!;

    const hours = Math.floor(absDiff / 3_600_000);
    if (hours < 1) {
      const val = locale === "fa" ? toPersianDigits(minutes) : String(minutes);
      return `${val} ${t.minutes} ${suffix}`;
    }

    const days = Math.floor(absDiff / 86_400_000);
    if (days < 1) {
      const val = locale === "fa" ? toPersianDigits(hours) : String(hours);
      return `${val} ${t.hours} ${suffix}`;
    }

    const val = locale === "fa" ? toPersianDigits(days) : String(days);
    return `${val} ${t.days} ${suffix}`;
  } catch {
    return "-";
  }
}

/**
 * Format duration in seconds to a readable string.
 *
 * fa: ۵ دقیقه ۳۰ ثانیه  |  en: 5m 30s
 */
export function formatDuration(
  seconds: number | null | undefined,
  locale: string
): string {
  if (seconds == null || seconds === 0) {
    return locale === "fa" ? "۰ ثانیه" : "0s";
  }

  const m = Math.floor(seconds / 60);
  const s = seconds % 60;

  if (locale === "fa") {
    if (m === 0) return toPersianDigits(s) + " ثانیه";
    if (s === 0) return toPersianDigits(m) + " دقیقه";
    return toPersianDigits(m) + " دقیقه " + toPersianDigits(s) + " ثانیه";
  }

  if (m === 0) return `${s}s`;
  if (s === 0) return `${m}m`;
  return `${m}m ${s}s`;
}

// ─── Jalali date string helpers ──────────────────────────────────────

/**
 * Convert an ISO date string (or Date) to Jalali "YYYY/MM/DD" string.
 */
export function toJalaliString(dateStr: string | Date): string {
  const d = typeof dateStr === "string" ? new Date(dateStr) : dateStr;
  const j = dateToJalali(d);
  return `${j.jy}/${String(j.jm).padStart(2, "0")}/${String(j.jd).padStart(2, "0")}`;
}

/**
 * Parse a Jalali "YYYY/MM/DD" string to ISO date string "YYYY-MM-DD".
 */
export function fromJalaliString(jalaliStr: string): string {
  const parts = toLatinDigits(jalaliStr).split("/").map(Number);
  if (parts.length !== 3) return "";
  const [jy, jm, jd] = parts;
  const { gy, gm, gd } = toGregorian(jy, jm, jd);
  return `${gy}-${String(gm).padStart(2, "0")}-${String(gd).padStart(2, "0")}`;
}

// ─── Re-exports for backward compatibility ──────────────────────────

/** @deprecated Use formatNumber(n, locale) instead */
export const toPersianNum = toPersianDigits;

/** @deprecated Use formatNumber(n, locale) instead */
export function fmtNum(n: number | null | undefined): string {
  return formatNumber(n, "fa");
}

/** @deprecated Use formatPercent(n, locale) instead */
export function fmtPercent(n: number | null | undefined): string {
  return formatPercent(n, "fa");
}

/** @deprecated Use formatPercentRaw(n, locale) instead */
export function fmtPercentRaw(n: number | null | undefined): string {
  return formatPercentRaw(n, "fa");
}

/** @deprecated Use formatDate(dateStr, locale) instead */
export function fmtDate(dateStr: string | null | undefined): string {
  return formatDate(dateStr, "fa");
}

/** @deprecated Use formatCurrency(rial, locale) instead */
export function fmtCurrency(rial: number | null | undefined): string {
  return formatCurrency(rial, "fa");
}

