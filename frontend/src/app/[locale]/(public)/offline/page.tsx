"use client";

import { useTranslations } from "next-intl";
import Link from "next/link";

export default function OfflinePage() {
  const t = useTranslations("offline");

  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-gray-50 px-4 text-center">
      {/* Icon */}
      <div className="text-7xl mb-6">📡</div>

      <h1 className="text-2xl font-bold text-gray-800 mb-3">{t("title")}</h1>
      <p className="text-gray-500 max-w-sm mb-8">{t("description")}</p>

      <button
        onClick={() => window.location.reload()}
        className="px-6 py-2.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors font-medium mb-4"
      >
        {t("retry")}
      </button>

      <Link
        href="/"
        className="text-sm text-blue-500 hover:underline"
      >
        {t("home")}
      </Link>
    </div>
  );
}

