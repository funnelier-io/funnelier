"use client";

import { fmtNum, fmtDate, fmtCurrency } from "@/lib/utils";
import { STAGE_LABELS, STAGE_COLORS, SEGMENT_LABELS } from "@/lib/constants";
import type { Contact } from "@/types/leads";

interface ContactDetailPanelProps {
  contact: Contact;
  onClose: () => void;
}

function fmtDuration(seconds: number): string {
  if (!seconds) return "—";
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  if (h > 0) return `${h} ساعت ${m} دقیقه`;
  return `${m} دقیقه`;
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

export default function ContactDetailPanel({ contact, onClose }: ContactDetailPanelProps) {
  const stageLabel = STAGE_LABELS[contact.current_stage] || contact.current_stage;
  const stageColor = STAGE_COLORS[contact.current_stage] || "#6b7280";
  const segmentLabel = contact.rfm_segment
    ? SEGMENT_LABELS[contact.rfm_segment] || contact.rfm_segment
    : null;
  const segmentBg = contact.rfm_segment
    ? SEGMENT_BG[contact.rfm_segment] || "bg-gray-100 text-gray-600"
    : "";

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
              {contact.name || "بدون نام"}
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
              <Badge label="مسدود" color="bg-red-100 text-red-700" />
            )}
            {!contact.is_active && (
              <Badge label="غیرفعال" color="bg-gray-100 text-gray-500" />
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
              از {fmtDate(contact.stage_entered_at)}
            </span>
          </div>

          {/* Engagement Stats */}
          <div className="bg-gray-50 rounded-lg p-4">
            <h3 className="text-xs font-semibold text-gray-500 mb-3">📊 آمار تعامل</h3>
            <div className="grid grid-cols-2 gap-3">
              <div className="text-center">
                <div className="text-lg font-bold text-blue-600">{fmtNum(contact.total_calls)}</div>
                <div className="text-xs text-gray-400">تماس</div>
              </div>
              <div className="text-center">
                <div className="text-lg font-bold text-green-600">{fmtNum(contact.total_answered_calls)}</div>
                <div className="text-xs text-gray-400">پاسخ داده</div>
              </div>
              <div className="text-center">
                <div className="text-lg font-bold text-purple-600">{fmtNum(contact.total_sms_sent)}</div>
                <div className="text-xs text-gray-400">پیامک</div>
              </div>
              <div className="text-center">
                <div className="text-lg font-bold text-amber-600">{fmtDuration(contact.total_call_duration)}</div>
                <div className="text-xs text-gray-400">مدت تماس</div>
              </div>
            </div>
          </div>

          {/* Sales Stats */}
          <div className="bg-gray-50 rounded-lg p-4">
            <h3 className="text-xs font-semibold text-gray-500 mb-3">💰 فروش</h3>
            <div className="grid grid-cols-2 gap-3">
              <div className="text-center">
                <div className="text-lg font-bold text-emerald-600">{fmtNum(contact.total_invoices)}</div>
                <div className="text-xs text-gray-400">فاکتور</div>
              </div>
              <div className="text-center">
                <div className="text-lg font-bold text-green-600">{fmtNum(contact.total_paid_invoices)}</div>
                <div className="text-xs text-gray-400">پرداختی</div>
              </div>
              <div className="col-span-2 text-center pt-1">
                <div className="text-lg font-bold text-amber-600">{fmtCurrency(contact.total_revenue)}</div>
                <div className="text-xs text-gray-400">درآمد کل</div>
              </div>
            </div>
          </div>

          {/* Details */}
          <div>
            <h3 className="text-xs font-semibold text-gray-500 mb-2">📋 اطلاعات</h3>
            <InfoRow label="ایمیل" value={contact.email} />
            <InfoRow label="دسته‌بندی" value={contact.category_name} />
            <InfoRow label="منبع" value={contact.source_name} />
            <InfoRow label="تاریخ ایجاد" value={fmtDate(contact.created_at)} />
            <InfoRow label="آخرین خرید" value={fmtDate(contact.last_purchase_at)} />
            <InfoRow label="اولین خرید" value={fmtDate(contact.first_purchase_at)} />
          </div>

          {/* Tags */}
          {contact.tags && contact.tags.length > 0 && (
            <div>
              <h3 className="text-xs font-semibold text-gray-500 mb-2">🏷️ برچسب‌ها</h3>
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
              <h3 className="text-xs font-semibold text-gray-500 mb-2">📝 یادداشت</h3>
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


