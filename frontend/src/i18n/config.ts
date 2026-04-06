export const locales = ["fa", "en"] as const;
export type Locale = (typeof locales)[number];
export const defaultLocale: Locale = "fa";

/** RTL locales */
export const rtlLocales: Locale[] = ["fa"];

export function isRtl(locale: Locale): boolean {
  return rtlLocales.includes(locale);
}

