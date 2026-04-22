"use client";

import { useState, useCallback } from "react";
import { useTranslations } from "next-intl";
import { useWebSocket, type WSEvent } from "@/lib/use-websocket";

interface KPISnapshot {
  total_contacts: number;
  active_campaigns: number;
  sms_sent_today: number;
}

export default function RealtimeKPITicker() {
  const t = useTranslations("wsEvents");
  const [kpi, setKpi] = useState<KPISnapshot | null>(null);
  const [lastEvent, setLastEvent] = useState<string | null>(null);

  const onEvent = useCallback((event: WSEvent) => {
    if (event.type === "kpi_snapshot") {
      setKpi(event.payload as KPISnapshot);
    } else if (event.type === "new_lead") {
      setLastEvent(t("newLead"));
    } else if (event.type === "sms_sent") {
      setLastEvent(t("smsSent"));
    } else if (event.type === "campaign_complete") {
      setLastEvent(t("campaignComplete"));
    }
  }, [t]);

  const { isConnected } = useWebSocket({ onEvent });

  if (!kpi && !isConnected) return null;

  return (
    <div className={`flex items-center gap-4 px-4 py-2 rounded-xl text-xs border ${isConnected ? "bg-green-50 border-green-200" : "bg-gray-50 border-gray-200"}`}>
      {/* Live indicator */}
      <span className="flex items-center gap-1.5 font-medium text-gray-600">
        <span className={`w-2 h-2 rounded-full ${isConnected ? "bg-green-500 animate-pulse" : "bg-gray-400"}`} />
        {isConnected ? t("live") : t("disconnected")}
      </span>

      {kpi && (
        <>
          <span className="text-gray-400">|</span>
          <span className="text-gray-700">{t("contacts")}: <strong>{kpi.total_contacts.toLocaleString()}</strong></span>
          <span className="text-gray-700">{t("activeCampaigns")}: <strong>{kpi.active_campaigns}</strong></span>
          <span className="text-gray-700">{t("smsToday")}: <strong>{kpi.sms_sent_today.toLocaleString()}</strong></span>
        </>
      )}

      {lastEvent && (
        <>
          <span className="text-gray-400">|</span>
          <span className="text-blue-600 animate-pulse">⚡ {lastEvent}</span>
        </>
      )}
    </div>
  );
}

