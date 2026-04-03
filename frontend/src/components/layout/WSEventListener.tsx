"use client";

import { useWebSocket, WSEvent } from "@/lib/use-websocket";
import { showToast } from "@/components/ui/ToastContainer";

const EVENT_LABELS: Record<string, { title: string; type: "success" | "info" | "warning" | "error" }> = {
  import_started: { title: "واردسازی شروع شد", type: "info" },
  import_completed: { title: "واردسازی تکمیل شد", type: "success" },
  batch_import_completed: { title: "واردسازی دسته‌ای تکمیل شد", type: "success" },
  funnel_snapshot_completed: { title: "عکس فانل ذخیره شد", type: "success" },
  rfm_calculation_completed: { title: "محاسبه RFM تکمیل شد", type: "success" },
  daily_report_generated: { title: "گزارش روزانه ایجاد شد", type: "info" },
  alerts_triggered: { title: "هشدار جدید!", type: "warning" },
  sync_completed: { title: "همگام‌سازی تکمیل شد", type: "success" },
};

function handleWSEvent(event: WSEvent) {
  const cfg = EVENT_LABELS[event.type];
  if (cfg) {
    const payload = event.payload || {};
    let message = "";

    if (event.type === "import_completed") {
      const result = payload.result as Record<string, unknown> | undefined;
      if (result) {
        message = `فایل: ${payload.file || "—"} | وارد: ${result.imported ?? 0} | خطا: ${result.errors ?? 0}`;
      }
    } else if (event.type === "alerts_triggered") {
      const alerts = payload.alerts as Array<Record<string, string>> | undefined;
      if (alerts) {
        message = `${alerts.length} هشدار فعال شد`;
      }
    } else if (event.type === "rfm_calculation_completed") {
      message = "بخش‌بندی مخاطبین بروزرسانی شد";
    }

    showToast({ type: cfg.type, title: cfg.title, message });
  }
}

/**
 * WebSocket event listener component.
 * Renders a small connection status indicator and listens for events.
 */
export default function WSEventListener() {
  const { isConnected } = useWebSocket({ onEvent: handleWSEvent });

  return (
    <div className="fixed bottom-4 left-4 z-40">
      <div
        className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs shadow-sm border ${
          isConnected
            ? "bg-green-50 border-green-200 text-green-700"
            : "bg-gray-50 border-gray-200 text-gray-400"
        }`}
        title={isConnected ? "متصل به سرور" : "در حال اتصال..."}
      >
        <div
          className={`w-1.5 h-1.5 rounded-full ${
            isConnected ? "bg-green-500 animate-pulse" : "bg-gray-300"
          }`}
        />
        {isConnected ? "آنلاین" : "آفلاین"}
      </div>
    </div>
  );
}

