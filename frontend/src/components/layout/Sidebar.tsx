"use client";

import { useTranslations, useLocale } from "next-intl";
import { Link, usePathname, useRouter } from "@/i18n/navigation";
import { NAV_ITEMS } from "@/lib/constants";
import { cn } from "@/lib/utils";
import { useAuthStore } from "@/stores/auth-store";
import type { Locale } from "@/i18n/config";

interface SidebarProps {
  isOpen?: boolean;
  onClose?: () => void;
}

export default function Sidebar({ isOpen, onClose }: SidebarProps) {
  const pathname = usePathname();
  const locale = useLocale() as Locale;
  const router = useRouter();
  const { user, logout } = useAuthStore();
  const t = useTranslations("nav");
  const tApp = useTranslations("app");

  const isRtl = locale === "fa";

  function switchLocale() {
    const next = locale === "fa" ? "en" : "fa";
    router.replace(pathname, { locale: next });
  }

  return (
    <>
      {/* Mobile backdrop */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-black/30 z-20 lg:hidden"
          onClick={onClose}
        />
      )}

      <aside
        className={cn(
          "fixed top-0 w-60 h-full bg-white shadow-lg z-30 flex flex-col transition-transform duration-200",
          isRtl ? "right-0" : "left-0",
          // On mobile: off-screen by default, slide in when open
          isOpen
            ? "translate-x-0"
            : isRtl
              ? "translate-x-full"
              : "-translate-x-full",
          // On desktop: always visible
          "lg:translate-x-0"
        )}
      >
        {/* Logo */}
        <div className="p-4 border-b border-gray-200 flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold text-blue-600">🎯 {tApp("name")}</h1>
            <p className="text-xs text-gray-400">{tApp("tagline")}</p>
          </div>
          {/* Mobile close button */}
          <button
            onClick={onClose}
            className="lg:hidden w-8 h-8 flex items-center justify-center rounded-full hover:bg-gray-100 text-gray-400"
          >
            ✕
          </button>
        </div>

        {/* Navigation */}
        <nav className="p-3 flex-1 overflow-y-auto">
          {/* Search shortcut */}
          <button
            onClick={() => {
              onClose?.();
              setTimeout(() => {
                window.dispatchEvent(
                  new KeyboardEvent("keydown", { key: "k", metaKey: true })
                );
              }, 100);
            }}
            className="w-full flex items-center gap-2 px-3 py-2 mb-2 text-sm text-gray-400 bg-gray-50 rounded-md hover:bg-gray-100 transition-colors"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
            <span className="flex-1 text-start">{t("search")}</span>
            <kbd className="text-[10px] text-gray-300 bg-white border border-gray-200 rounded px-1.5 py-0.5 font-mono">⌘K</kbd>
          </button>

          <ul className="space-y-1 text-sm">
            {NAV_ITEMS.map((item) => {
              const isActive =
                item.href === "/"
                  ? pathname === "/"
                  : pathname.startsWith(item.href);
              return (
                <li key={item.href}>
                  <Link
                    href={item.href}
                    onClick={onClose}
                    className={cn(
                      "block px-3 py-2 rounded-md transition-colors",
                      isActive
                        ? "bg-blue-100 text-blue-600 font-semibold"
                        : "hover:bg-gray-100 text-gray-700"
                    )}
                  >
                    <span className={isRtl ? "ml-2" : "mr-2"}>{item.icon}</span>
                    {t(item.labelKey)}
                  </Link>
                </li>
              );
            })}
          </ul>
        </nav>

        {/* Language Switcher */}
        <div className="px-3 py-2 border-t border-gray-200">
          <button
            onClick={switchLocale}
            className="w-full flex items-center justify-center gap-2 px-3 py-1.5 text-xs text-gray-500 bg-gray-50 rounded-md hover:bg-gray-100 transition-colors"
          >
            <span className="text-sm">🌐</span>
            <span className={locale === "fa" ? "font-medium" : ""}>فا</span>
            <span className="text-gray-300">|</span>
            <span className={locale === "en" ? "font-medium" : ""}>EN</span>
          </button>
        </div>

        {/* User info */}
        <div className="p-3 border-t border-gray-200 text-xs text-gray-400">
          {user ? (
            <div className="flex items-center justify-between">
              <span>{user.full_name || user.username}</span>
              <button
                onClick={logout}
                className="text-red-400 hover:text-red-600 transition-colors"
              >
                {t("logout")}
              </button>
            </div>
          ) : (
            <Link href="/login" className="text-blue-500 hover:text-blue-700">
              {t("login")}
            </Link>
          )}
        </div>
      </aside>
    </>
  );
}

