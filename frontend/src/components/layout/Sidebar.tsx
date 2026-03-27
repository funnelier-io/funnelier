"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { NAV_ITEMS } from "@/lib/constants";
import { cn } from "@/lib/utils";
import { useAuthStore } from "@/stores/auth-store";

export default function Sidebar() {
  const pathname = usePathname();
  const { user, logout } = useAuthStore();

  return (
    <aside className="fixed right-0 top-0 w-60 h-full bg-white shadow-lg z-10 flex flex-col">
      {/* Logo */}
      <div className="p-4 border-b border-gray-200">
        <h1 className="text-xl font-bold text-blue-600">🎯 فانلیر</h1>
        <p className="text-xs text-gray-400">تحلیل فانل بازاریابی</p>
      </div>

      {/* Navigation */}
      <nav className="p-3 flex-1 overflow-y-auto">
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
  );
}

