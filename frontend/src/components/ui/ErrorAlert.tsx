"use client";

import { cn } from "@/lib/utils";

interface ErrorAlertProps {
  message: string | null;
  onRetry?: () => void;
  className?: string;
}

/**
 * Inline error alert with optional retry button.
 */
export default function ErrorAlert({
  message,
  onRetry,
  className,
}: ErrorAlertProps) {
  if (!message) return null;

  return (
    <div
      className={cn(
        "flex items-center gap-3 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700",
        className
      )}
    >
      <span className="shrink-0">⚠️</span>
      <span className="flex-1">{message}</span>
      {onRetry && (
        <button
          onClick={onRetry}
          className="shrink-0 text-xs px-2.5 py-1 bg-red-100 rounded hover:bg-red-200 transition-colors"
        >
          تلاش مجدد
        </button>
      )}
    </div>
  );
}

