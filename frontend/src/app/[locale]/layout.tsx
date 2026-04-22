import { NextIntlClientProvider, hasLocale } from "next-intl";
import { notFound } from "next/navigation";
import { routing } from "@/i18n/routing";
import { isRtl, type Locale } from "@/i18n/config";
import { setRequestLocale } from "next-intl/server";
import ServiceWorkerRegistrar from "@/components/ServiceWorkerRegistrar";

export default async function LocaleLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;

  if (!hasLocale(routing.locales, locale)) {
    notFound();
  }

  setRequestLocale(locale);

  const messages = (await import(`../../../messages/${locale}.json`)).default;

  const dir = isRtl(locale as Locale) ? "rtl" : "ltr";
  const fontClass = locale === "fa" ? "font-shabnam" : "font-sans";

  return (
    <html lang={locale} dir={dir}>
      <body className={`antialiased ${fontClass}`}>
        <NextIntlClientProvider locale={locale} messages={messages}>
          <ServiceWorkerRegistrar />
          {children}
        </NextIntlClientProvider>
      </body>
    </html>
  );
}

export function generateStaticParams() {
  return routing.locales.map((locale) => ({ locale }));
}

