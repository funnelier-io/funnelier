/**
 * Convert a number string to Persian digits.
 */
export function toPersianNum(n: number | string | null | undefined): string {
  if (n == null) return "۰";
  return String(n).replace(/[0-9]/g, (d) => "۰۱۲۳۴۵۶۷۸۹"[parseInt(d)]);
}

/**
 * Format a number with commas and convert to Persian digits.
 */
export function fmtNum(n: number | null | undefined): string {
  if (n == null) return "۰";
  return toPersianNum(Number(n).toLocaleString("en"));
}

/**
 * Format a percentage with Persian digits.
 * Input is a 0–1 ratio (e.g., 0.85 → ۸۵.۰٪).
 */
export function fmtPercent(n: number | null | undefined): string {
  if (n == null) return "۰٪";
  return toPersianNum((n * 100).toFixed(1)) + "٪";
}

/**
 * Format a percentage that is already in 0–100 range.
 * Input is a direct percentage (e.g., 85 → ۸۵.۰٪).
 */
export function fmtPercentRaw(n: number | null | undefined): string {
  if (n == null) return "۰٪";
  return toPersianNum(Number(n).toFixed(1)) + "٪";
}

/**
 * Format a date to Persian locale string.
 */
export function fmtDate(dateStr: string | null | undefined): string {
  if (!dateStr) return "-";
  try {
    const d = new Date(dateStr);
    if (isNaN(d.getTime())) return "-";
    return d.toLocaleDateString("fa-IR") + " " + d.toLocaleTimeString("fa-IR", { hour: "2-digit", minute: "2-digit" });
  } catch {
    return "-";
  }
}

/**
 * Format currency in Toman (Rial / 10).
 */
export function fmtCurrency(rial: number | null | undefined): string {
  if (rial == null || rial === 0) return "۰ تومان";
  const toman = Math.round(rial / 10);
  if (toman >= 1_000_000_000) {
    return toPersianNum((toman / 1_000_000_000).toFixed(1)) + " میلیارد تومان";
  }
  if (toman >= 1_000_000) {
    return toPersianNum((toman / 1_000_000).toFixed(1)) + " میلیون تومان";
  }
  return fmtNum(toman) + " تومان";
}

/**
 * Classnames utility — joins truthy class strings.
 */
export function cn(...classes: (string | false | null | undefined)[]): string {
  return classes.filter(Boolean).join(" ");
}

