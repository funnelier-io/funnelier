/**
 * Utility functions for Funnelier frontend.
 *
 * NOTE: The locale-hardcoded helpers (fmtNum, fmtDate, etc.) are kept for
 * backward compatibility but deprecated. New code should use the locale-aware
 * `useFormat()` hook or the functions in `@/lib/format`.
 */

// Re-export everything from the new format module
export {
  toPersianDigits as toPersianNum,
  toPersianDigits,
  toLatinDigits,
  formatNumber,
  formatPercent,
  formatPercentRaw,
  formatCurrency,
  formatDate,
  formatDateOnly,
  formatDateShort,
  formatRelativeTime,
  formatDuration,
  // Backward-compat aliases (Persian-hardcoded)
  fmtNum,
  fmtPercent,
  fmtPercentRaw,
  fmtDate,
  fmtCurrency,
} from "./format";

/**
 * Classnames utility — joins truthy class strings.
 */
export function cn(...classes: (string | false | null | undefined)[]): string {
  return classes.filter(Boolean).join(" ");
}
