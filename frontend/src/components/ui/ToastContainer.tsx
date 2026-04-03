"use client";

import { useState, useEffect, useCallback } from "react";

export interface Toast {
  id: string;
  type: "success" | "error" | "info" | "warning";
  title: string;
  message?: string;
  duration?: number;
}

const ICONS: Record<Toast["type"], string> = {
  success: "✅",
  error: "❌",
  info: "ℹ️",
  warning: "⚠️",
};

const COLORS: Record<Toast["type"], string> = {
  success: "bg-green-50 border-green-200 text-green-800",
  error: "bg-red-50 border-red-200 text-red-800",
  info: "bg-blue-50 border-blue-200 text-blue-800",
  warning: "bg-amber-50 border-amber-200 text-amber-800",
};

let globalAddToast: ((toast: Omit<Toast, "id">) => void) | null = null;

/**
 * Show a toast notification from anywhere in the app.
 */
export function showToast(toast: Omit<Toast, "id">) {
  globalAddToast?.(toast);
}

/**
 * Toast container component - place once in the app layout.
 */
export default function ToastContainer() {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const addToast = useCallback((toast: Omit<Toast, "id">) => {
    const id = `${Date.now()}-${Math.random().toString(36).slice(2)}`;
    setToasts((prev) => [...prev, { ...toast, id }]);

    // Auto-dismiss
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, toast.duration || 5000);
  }, []);

  const removeToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  // Register global handler
  useEffect(() => {
    globalAddToast = addToast;
    return () => {
      globalAddToast = null;
    };
  }, [addToast]);

  if (toasts.length === 0) return null;

  return (
    <div className="fixed top-4 left-4 z-50 space-y-2 max-w-sm" dir="rtl">
      {toasts.map((toast) => (
        <div
          key={toast.id}
          className={`flex items-start gap-2 p-3 rounded-lg border shadow-lg animate-slide-in ${COLORS[toast.type]}`}
        >
          <span className="text-base shrink-0 mt-0.5">{ICONS[toast.type]}</span>
          <div className="flex-1 min-w-0">
            <div className="text-sm font-medium">{toast.title}</div>
            {toast.message && (
              <div className="text-xs mt-0.5 opacity-80">{toast.message}</div>
            )}
          </div>
          <button
            onClick={() => removeToast(toast.id)}
            className="text-xs opacity-50 hover:opacity-100 shrink-0"
          >
            ✕
          </button>
        </div>
      ))}
    </div>
  );
}

