"use client";

/**
 * React hook providing locale-aware formatting functions.
 *
 * Usage:
 *   const fmt = useFormat();
 *   fmt.number(12345)        // "۱۲,۳۴۵" (fa) or "12,345" (en)
 *   fmt.date("2026-04-09")   // "۱۴۰۵/۰۱/۲۰" (fa) or "2026-04-09" (en)
 *   fmt.percent(0.85)        // "۸۵.۰٪" (fa) or "85.0%" (en)
 *   fmt.currency(50000000)   // "۵ میلیون تومان" (fa) or "5.0 M Toman" (en)
 */

import { useLocale, useTranslations } from "next-intl";
import { useCallback, useMemo } from "react";
import {
  formatNumber,
  formatPercent,
  formatPercentRaw,
  formatCurrency,
  formatDate,
  formatDateOnly,
  formatDateShort,
  formatRelativeTime,
  formatDuration,
  toPersianDigits,
} from "./format";

export function useFormat() {
  const locale = useLocale();
  const tc = useTranslations("common");

  const currencyLabels = useMemo(() => ({
    toman: tc("currency.toman"),
    million: tc("currency.millionToman"),
    billion: tc("currency.billionToman"),
  }), [tc]);

  const number = useCallback(
    (n: number | null | undefined) => formatNumber(n, locale),
    [locale]
  );

  const percent = useCallback(
    (n: number | null | undefined) => formatPercent(n, locale),
    [locale]
  );

  const percentRaw = useCallback(
    (n: number | null | undefined) => formatPercentRaw(n, locale),
    [locale]
  );

  const currency = useCallback(
    (rial: number | null | undefined) => formatCurrency(rial, locale, currencyLabels),
    [locale, currencyLabels]
  );

  const date = useCallback(
    (dateStr: string | null | undefined) => formatDate(dateStr, locale),
    [locale]
  );

  const dateOnly = useCallback(
    (dateStr: string | null | undefined) => formatDateOnly(dateStr, locale),
    [locale]
  );

  const dateShort = useCallback(
    (dateStr: string | null | undefined) => formatDateShort(dateStr, locale),
    [locale]
  );

  const relative = useCallback(
    (dateStr: string | null | undefined) => formatRelativeTime(dateStr, locale),
    [locale]
  );

  const duration = useCallback(
    (seconds: number | null | undefined) => formatDuration(seconds, locale),
    [locale]
  );

  const digits = useCallback(
    (s: string | number) => locale === "fa" ? toPersianDigits(s) : String(s),
    [locale]
  );

  return useMemo(() => ({
    locale,
    number,
    percent,
    percentRaw,
    currency,
    date,
    dateOnly,
    dateShort,
    relative,
    duration,
    digits,
  }), [locale, number, percent, percentRaw, currency, date, dateOnly, dateShort, relative, duration, digits]);
}

