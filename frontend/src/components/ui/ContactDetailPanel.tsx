"use client";

import { useTranslations } from "next-intl";
import { useFormat } from "@/lib/use-format";
import { useApi } from "@/lib/hooks";

import { STAGE_LABELS, STAGE_COLORS, SEGMENT_LABELS } from "@/lib/constants";
import type { Contact } from "@/types/leads";

interface ContactDetailPanelProps {
  contact: Contact;
  onClose: () => void;
}

function Badge({ label, color }: { label: string; color: string }) {
  return (
    <span className={`inline-block px-2.5 py-1 rounded-full text-xs font-medium ${color}`}>
      {label}
    </span>
  );
}

function InfoRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-start justify-between py-2 border-b border-gray-50">
      <span className="text-xs text-gray-400 shrink-0">{label}</span>
      <span className="text-sm text-gray-800 text-left" dir="ltr">
        {value || "—"}
      </span>
    </div>
  );
}

const SEGMENT_BG: Record<string, string> = {
  champions: "bg-emerald-100 text-emerald-800",
  loyal: "bg-green-100 text-green-800",
  potential_loyalist: "bg-blue-100 text-blue-800",
  new_customers: "bg-cyan-100 text-cyan-800",
  promising: "bg-purple-100 text-purple-800",
  need_attention: "bg-amber-100 text-amber-800",
  about_to_sleep: "bg-orange-100 text-orange-800",
  at_risk: "bg-red-100 text-red-800",
  cant_lose: "bg-rose-100 text-rose-800",
  hibernating: "bg-gray-100 text-gray-600",
  lost: "bg-gray-200 text-gray-500",
};

interface TimelineEvent {
  type: "call" | "sms";
  timestamp: string | null;
  duration_seconds?: number;
  call_type?: string;
  status?: string;
  is_successful?: boolean;
  salesperson_name?: string;
  notes?: string;
  message?: string;
  provider?: string;
}

interface TimelineResponse {
  contact_id: string;
  phone_number: string;
  events: TimelineEvent[];
}

export default function ContactDetailPanel({ contact, onClose }: ContactDetailPanelProps) {
  const t = useTranslations("contactDetail");
  const fmt = useFormat();
  const tc = useTranslations("common");

  const stageLabel = STAGE_LABELS[contact.current_stage] || contact.current_stage;
  const stageColor = STAGE_COLORS[contact.current_stage] || "#6b7280";
  const segmentLabel = contact.rfm_segment
    ? SEGMENT_LABELS[contact.rfm_segment] || contact.rfm_segment
    : null;
  const segmentBg = contact.rfm_segment
    ? SEGMENT_BG[contact.rfm_segment] || "bg-gray-100 text-gray-600"
    : "";

  const timeline = useApi<TimelineResponse>(
    `/communications/timeline/${contact.id}?limit=20`
  );

  function fmtDuration(seconds: number): string {
    if (!seconds) return "—";
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    if (h > 0) return t("hoursMinutes", { h, m });
    return t("minutes", { m });
  }

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/20 backdrop-blur-sm z-40"
        onClick={onClose}
      />

      {/* Panel */}
      <div className="fixed left-0 top-0 h-full w-full max-w-md bg-white shadow-2xl z-50 overflow-y-auto animate-slide-in-left">
        {/* Header */}
        <div className="sticky top-0 bg-white border-b border-gray-200 px-5 py-4 flex items-center justify-between z-10">
          <div>
            <h2 className="text-base font-bold text-gray-800">
              {contact.name || t("unnamed")}
            </h2>
            <span className="font-mono text-xs text-gray-400" dir="ltr">
              {contact.phone_number}
            </span>
          </div>
          <button
            onClick={onClose}
            className="w-8 h-8 flex items-center justify-center rounded-full hover:bg-gray-100 text-gray-400 hover:text-gray-600 transition-colors"
          >
            ✕
          </button>
        </div>

        <div className="p-5 space-y-5">
          {/* Badges */}
          <div className="flex flex-wrap gap-2">
            {segmentLabel && (
              <Badge label={segmentLabel} color={segmentBg} />
            )}
            {contact.rfm_score && (
              <Badge
                label={`RFM ${contact.rfm_score}`}
                color="bg-indigo-50 text-indigo-700"
              />
            )}
            {contact.is_blocked && (
              <Badge label={t("blocked")} color="bg-red-100 text-red-700" />
            )}
            {!contact.is_active && (
              <Badge label={t("inactive")} color="bg-gray-100 text-gray-500" />
            )}
          </div>

          {/* Stage badge with custom bg */}
          <div className="flex items-center gap-2">
            <div
              className="w-3 h-3 rounded-full"
              style={{ backgroundColor: stageColor }}
            />
            <span className="text-sm font-medium">{stageLabel}</span>
            <span className="text-xs text-gray-400">
              {t("since", { date: fmt.date(contact.stage_entered_at) })}
            </span>
          </div>

          {/* Engagement Stats */}
          <div className="bg-gray-50 rounded-lg p-4">
            <h3 className="text-xs font-semibold text-gray-500 mb-3">{t("engagementStats")}</h3>
            <div className="grid grid-cols-2 gap-3">
              <div className="text-center">
                <div className="text-lg font-bold text-blue-600">{fmt.number(contact.total_calls)}</div>
                <div className="text-xs text-gray-400">{t("calls")}</div>
              </div>
              <div className="text-center">
                <div className="text-lg font-bold text-green-600">{fmt.number(contact.total_answered_calls)}</div>
                <div className="text-xs text-gray-400">{t("answered")}</div>
              </div>
              <div className="text-center">
                <div className="text-lg font-bold text-purple-600">{fmt.number(contact.total_sms_sent)}</div>
                <div className="text-xs text-gray-400">{t("sms")}</div>
              </div>
              <div className="text-center">
                <div className="text-lg font-bold text-amber-600">{fmtDuration(contact.total_call_duration)}</div>
                <div className="text-xs text-gray-400">{t("callDuration")}</div>
              </div>
            </div>
          </div>

          {/* Sales Stats */}
          <div className="bg-gray-50 rounded-lg p-4">
            <h3 className="text-xs font-semibold text-gray-500 mb-3">{t("salesStats")}</h3>
            <div className="grid grid-cols-2 gap-3">
              <div className="text-center">
                <div className="text-lg font-bold text-emerald-600">{fmt.number(contact.total_invoices)}</div>
                <div className="text-xs text-gray-400">{t("invoices")}</div>
              </div>
              <div className="text-center">
                <div className="text-lg font-bold text-green-600">{fmt.number(contact.total_paid_invoices)}</div>
                <div className="text-xs text-gray-400">{t("paid")}</div>
              </div>
              <div className="col-span-2 text-center pt-1">
                <div className="text-lg font-bold text-amber-600">{fmt.currency(contact.total_revenue)}</div>
                <div className="text-xs text-gray-400">{t("totalRevenue")}</div>
              </div>
            </div>
          </div>

          {/* Communication Timeline */}
          <div>
            <h3 className="text-xs font-semibold text-gray-500 mb-3">{t("communicationHistory")}</h3>
            {timeline.isLoading ? (
              <div className="text-xs text-gray-400 text-center py-4">{tc("loading")}</div>
            ) : timeline.data?.events && timeline.data.events.length > 0 ? (
              <div className="space-y-2 max-h-[300px] overflow-y-auto">
                {timeline.data.events.map((ev, i) => (
                  <div key={i} className={`flex items-start gap-2 p-2.5 rounded-lg text-xs ${
                    ev.type === "call" ? "bg-blue-50" : "bg-purple-50"
                  }`}>
                    <span className="shrink-0 mt-0.5">
                      {ev.type === "call" ? (ev.is_successful ? "✅" : "📞") : "💬"}
                    </span>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="font-medium text-gray-700">
                          {ev.type === "call" ? t("call") : t("smsEvent")}
                        </span>
                        {ev.type === "call" && ev.duration_seconds != null && ev.duration_seconds > 0 && (
                          <span className="text-gray-400" dir="ltr">
                            {Math.floor(ev.duration_seconds / 60)}:{String(ev.duration_seconds % 60).padStart(2, "0")}
                          </span>
                        )}
                        {ev.status && (
                          <span className={`px-1.5 py-0.5 rounded text-[10px] ${
                            ev.is_successful ? "bg-green-100 text-green-700" :
                            ev.status === "answered" ? "bg-blue-100 text-blue-700" :
                            "bg-gray-100 text-gray-500"
                          }`}>
                            {ev.status}
                          </span>
                        )}
                      </div>
                      {ev.salesperson_name && (
                        <div className="text-gray-400 mt-0.5">{t("salesperson", { name: ev.salesperson_name })}</div>
                      )}
                      {ev.message && (
                        <div className="text-gray-500 mt-0.5 truncate">{ev.message}</div>
                      )}
                      {ev.timestamp && (
                        <div className="text-gray-300 mt-0.5">{fmt.date(ev.timestamp)}</div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-xs text-gray-400 text-center py-4">
                {t("noHistory")}
              </div>
            )}
          </div>

          {/* Details */}
          <div>
            <h3 className="text-xs font-semibold text-gray-500 mb-2">{t("info")}</h3>
            <InfoRow label={t("email")} value={contact.email} />
            <InfoRow label={t("category")} value={contact.category_name} />
            <InfoRow label={t("source")} value={contact.source_name} />
            <InfoRow label={t("createdAt")} value={fmt.date(contact.created_at)} />
            <InfoRow label={t("lastPurchase")} value={fmt.date(contact.last_purchase_at)} />
            <InfoRow label={t("firstPurchase")} value={fmt.date(contact.first_purchase_at)} />
          </div>

          {/* Tags */}
          {contact.tags && contact.tags.length > 0 && (
            <div>
              <h3 className="text-xs font-semibold text-gray-500 mb-2">{t("tags")}</h3>
              <div className="flex flex-wrap gap-1.5">
                {contact.tags.map((tag) => (
                  <span
                    key={tag}
                    className="px-2 py-0.5 bg-blue-50 text-blue-700 rounded text-xs"
                  >
                    {tag}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Notes */}
          {contact.notes && (
            <div>
              <h3 className="text-xs font-semibold text-gray-500 mb-2">{t("notes")}</h3>
              <p className="text-sm text-gray-600 bg-amber-50 rounded-lg p-3">
                {contact.notes}
              </p>
            </div>
          )}
        </div>
      </div>
    </>
  );
}

