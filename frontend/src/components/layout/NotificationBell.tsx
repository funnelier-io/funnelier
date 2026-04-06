"use client";

import { useEffect, useRef } from "react";
import { useTranslations } from "next-intl";
import { useNotificationStore } from "@/stores/notification-store";
import { fmtNum } from "@/lib/utils";

const SEVERITY_ICON: Record<string, string> = {
  info: "ℹ️",
  success: "✅",
  warning: "⚠️",
  error: "❌",
  critical: "🔴",
};

const TYPE_ICON: Record<string, string> = {
  alert: "🔔",
  import: "📥",
  campaign: "📢",
  system: "⚙️",
  sync: "🔄",
  report: "📊",
  sms: "💬",
};

function timeAgo(dateStr: string): string {
  const now = Date.now();
  const then = new Date(dateStr).getTime();
  const diff = Math.max(0, now - then);
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "الان";
  if (mins < 60) return `${mins} دقیقه پیش`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours} ساعت پیش`;
  const days = Math.floor(hours / 24);
  return `${days} روز پیش`;
}

export default function NotificationBell() {
  const t = useTranslations("notifications");
  const {
    notifications,
    unreadCount,
    isOpen,
    isLoading,
    toggle,
    setOpen,
    fetchUnreadCount,
    markRead,
    markAllRead,
  } = useNotificationStore();

  const panelRef = useRef<HTMLDivElement>(null);

  // Fetch unread count on mount and every 30 seconds
  useEffect(() => {
    fetchUnreadCount();
    const interval = setInterval(fetchUnreadCount, 30000);
    return () => clearInterval(interval);
  }, [fetchUnreadCount]);

  // Close on outside click
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (panelRef.current && !panelRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    if (isOpen) {
      document.addEventListener("mousedown", handleClickOutside);
    }
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [isOpen, setOpen]);

  return (
    <div className="relative" ref={panelRef}>
      {/* Bell Button */}
      <button
        onClick={toggle}
        className="relative p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
        title={t("title")}
      >
        <svg
          className="w-5 h-5 text-gray-600 dark:text-gray-300"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9"
          />
        </svg>
        {unreadCount > 0 && (
          <span className="absolute -top-0.5 -right-0.5 bg-red-500 text-white text-[10px] font-bold rounded-full min-w-[18px] h-[18px] flex items-center justify-center px-1 animate-pulse">
            {unreadCount > 99 ? "99+" : fmtNum(unreadCount)}
          </span>
        )}
      </button>

      {/* Dropdown Panel */}
      {isOpen && (
        <div className="absolute left-0 top-full mt-2 w-80 max-h-[70vh] bg-white dark:bg-gray-800 rounded-xl shadow-2xl border border-gray-200 dark:border-gray-700 z-50 overflow-hidden flex flex-col animate-in slide-in-from-top-2">
          {/* Header */}
          <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100 dark:border-gray-700">
            <h3 className="font-semibold text-sm text-gray-900 dark:text-white">
              {t("title")}
              {unreadCount > 0 && (
                <span className="mr-2 text-xs bg-red-100 text-red-600 rounded-full px-2 py-0.5">
                  {fmtNum(unreadCount)}
                </span>
              )}
            </h3>
            {unreadCount > 0 && (
              <button
                onClick={markAllRead}
                className="text-xs text-blue-600 hover:text-blue-800 dark:text-blue-400"
              >
                {t("markAllRead")}
              </button>
            )}
          </div>

          {/* List */}
          <div className="overflow-y-auto flex-1 max-h-[50vh]">
            {isLoading && notifications.length === 0 ? (
              <div className="p-6 text-center text-gray-400 text-sm">
                {t("loading")}
              </div>
            ) : notifications.length === 0 ? (
              <div className="p-8 text-center">
                <div className="text-3xl mb-2">🔔</div>
                <p className="text-gray-400 text-sm">{t("empty")}</p>
              </div>
            ) : (
              notifications.map((n) => (
                <button
                  key={n.id}
                  onClick={() => {
                    if (!n.is_read) markRead(n.id);
                  }}
                  className={`w-full text-right px-4 py-3 border-b border-gray-50 dark:border-gray-700/50 hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors ${
                    !n.is_read
                      ? "bg-blue-50/50 dark:bg-blue-900/10"
                      : ""
                  }`}
                >
                  <div className="flex items-start gap-2.5">
                    <span className="text-lg flex-shrink-0 mt-0.5">
                      {TYPE_ICON[n.type] || SEVERITY_ICON[n.severity] || "🔔"}
                    </span>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-1.5">
                        {!n.is_read && (
                          <span className="w-2 h-2 rounded-full bg-blue-500 flex-shrink-0" />
                        )}
                        <p className="text-sm font-medium text-gray-900 dark:text-white truncate">
                          {n.title}
                        </p>
                      </div>
                      {n.body && (
                        <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5 line-clamp-2">
                          {n.body}
                        </p>
                      )}
                      <p className="text-[10px] text-gray-400 mt-1">
                        {timeAgo(n.created_at)}
                      </p>
                    </div>
                  </div>
                </button>
              ))
            )}
          </div>

          {/* Footer */}
          {notifications.length > 0 && (
            <div className="px-4 py-2 border-t border-gray-100 dark:border-gray-700 text-center">
              <button
                onClick={() => setOpen(false)}
                className="text-xs text-blue-600 hover:text-blue-800 dark:text-blue-400"
              >
                {t("close")}
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

