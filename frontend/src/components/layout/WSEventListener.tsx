"use client";

import { useCallback } from "react";
import { useTranslations } from "next-intl";
import { useWebSocket, WSEvent } from "@/lib/use-websocket";
import { showToast } from "@/components/ui/ToastContainer";
import { useNotificationStore } from "@/stores/notification-store";

const EVENT_TYPE_MAP: Record<string, { key: string; type: "success" | "info" | "warning" | "error" }> = {
  import_started: { key: "importStarted", type: "info" },
  import_completed: { key: "importCompleted", type: "success" },
  batch_import_completed: { key: "batchImportCompleted", type: "success" },
  funnel_snapshot_completed: { key: "funnelSnapshotCompleted", type: "success" },
  rfm_calculation_completed: { key: "rfmCalculationCompleted", type: "success" },
  daily_report_generated: { key: "dailyReportGenerated", type: "info" },
  alerts_triggered: { key: "alertsTriggered", type: "warning" },
  sync_completed: { key: "syncCompleted", type: "success" },
};

/**
 * WebSocket event listener component.
 * Renders a small connection status indicator and listens for events.
 */
export default function WSEventListener() {
  const t = useTranslations("wsEvents");
  const addNotification = useNotificationStore((s) => s.addNotification);
  const fetchUnreadCount = useNotificationStore((s) => s.fetchUnreadCount);

  const handleWSEvent = useCallback((event: WSEvent) => {
    // Handle notification_new event from backend
    if (event.type === "notification_new") {
      const p = event.payload || {};
      addNotification({
        id: String(p.notification_id || ""),
        tenant_id: String(p.tenant_id || ""),
        user_id: String(p.user_id || ""),
        type: String(p.type || "system") as import("@/types/notifications").NotificationType,
        severity: String(p.severity || "info") as import("@/types/notifications").NotificationSeverity,
        title: String(p.title || ""),
        body: p.body ? String(p.body) : null,
        is_read: false,
        created_at: new Date().toISOString(),
      });
      // Also refresh the count from server
      fetchUnreadCount();
    }

    const cfg = EVENT_TYPE_MAP[event.type];
    if (cfg) {
      const payload = event.payload || {};
      let message = "";

      if (event.type === "import_completed") {
        const result = payload.result as Record<string, unknown> | undefined;
        if (result) {
          message = t("fileImportDetail", {
            file: String(payload.file || "—"),
            imported: String(result.imported ?? 0),
            errors: String(result.errors ?? 0),
          });
        }
      } else if (event.type === "alerts_triggered") {
        const alerts = payload.alerts as Array<Record<string, string>> | undefined;
        if (alerts) {
          message = t("alertsActivated", { count: alerts.length });
        }
      } else if (event.type === "rfm_calculation_completed") {
        message = t("segmentsUpdated");
      }

      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      showToast({ type: cfg.type, title: t(cfg.key as any), message });
    }
  }, [t]);

  const { isConnected } = useWebSocket({ onEvent: handleWSEvent });

  return (
    <div className="fixed bottom-4 left-4 z-40">
      <div
        className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs shadow-sm border ${
          isConnected
            ? "bg-green-50 border-green-200 text-green-700"
            : "bg-gray-50 border-gray-200 text-gray-400"
        }`}
        title={isConnected ? t("connectedToServer") : t("connecting")}
      >
        <div
          className={`w-1.5 h-1.5 rounded-full ${
            isConnected ? "bg-green-500 animate-pulse" : "bg-gray-300"
          }`}
        />
        {isConnected ? t("online") : t("offline")}
      </div>
    </div>
  );
}

