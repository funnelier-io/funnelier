"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { NAV_ITEMS } from "@/lib/constants";
import { cn } from "@/lib/utils";
import { useAuthStore } from "@/stores/auth-store";

interface SidebarProps {
  isOpen?: boolean;
  onClose?: () => void;
}

export default function Sidebar({ isOpen, onClose }: SidebarProps) {
  const pathname = usePathname();
  const { user, logout } = useAuthStore();

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
          "fixed right-0 top-0 w-60 h-full bg-white shadow-lg z-30 flex flex-col transition-transform duration-200",
          // On mobile: off-screen by default, slide in when open
          isOpen ? "translate-x-0" : "translate-x-full",
          // On desktop: always visible
          "lg:translate-x-0"
        )}
      >
        {/* Logo */}
        <div className="p-4 border-b border-gray-200 flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold text-blue-600">🎯 فانلیر</h1>
            <p className="text-xs text-gray-400">تحلیل فانل بازاریابی</p>
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
            <span className="flex-1 text-right">جستجو...</span>
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
                    <span className="ml-2">{item.icon}</span>
                    {item.label}
                  </Link>
                </li>
              );
            })}
          </ul>
        </nav>

        {/* User info */}
        <div className="p-3 border-t border-gray-200 text-xs text-gray-400">
          {user ? (
            <div className="flex items-center justify-between">
              <span>{user.full_name || user.username}</span>
              <button
                onClick={logout}
                className="text-red-400 hover:text-red-600 transition-colors"
              >
                خروج
              </button>
            </div>
          ) : (
            <Link href="/login" className="text-blue-500 hover:text-blue-700">
              ورود
            </Link>
          )}
        </div>
      </aside>
    </>
  );
}

