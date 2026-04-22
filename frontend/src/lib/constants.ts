export const API_BASE = "/api/v1";

/** Translation keys for funnel stages — use with t(`stages.${key}`) */
export const STAGE_KEYS = [
  "lead_acquired",
  "sms_sent",
  "sms_delivered",
  "call_attempted",
  "call_answered",
  "invoice_issued",
  "payment_received",
] as const;

/** Fallback Persian labels for funnel stages (used when translations are unavailable) */
export const STAGE_LABELS: Record<string, string> = {
  lead_acquired: "سرنخ",
  sms_sent: "پیامک ارسالی",
  sms_delivered: "تحویل پیامک",
  call_attempted: "تماس",
  call_answered: "پاسخ تماس",
  invoice_issued: "پیش‌فاکتور",
  payment_received: "پرداخت",
};

/** Colors for funnel stages */
export const STAGE_COLORS: Record<string, string> = {
  lead_acquired: "#3b82f6",
  sms_sent: "#8b5cf6",
  sms_delivered: "#a78bfa",
  call_attempted: "#f59e0b",
  call_answered: "#22c55e",
  invoice_issued: "#06b6d4",
  payment_received: "#059669",
};

/** Fallback Persian labels for RFM segments (used when translations are unavailable) */
export const SEGMENT_LABELS: Record<string, string> = {
  champions: "قهرمانان",
  loyal: "وفادار",
  potential_loyalist: "بالقوه وفادار",
  new_customers: "مشتریان جدید",
  promising: "امیدوار",
  need_attention: "نیاز به توجه",
  about_to_sleep: "رو به خواب",
  at_risk: "در خطر",
  cant_lose: "از دست ندهید",
  hibernating: "خواب",
  lost: "از دست رفته",
};

/** Colors for RFM segments */
export const SEGMENT_COLORS: string[] = [
  "#059669",
  "#22c55e",
  "#3b82f6",
  "#06b6d4",
  "#8b5cf6",
  "#f59e0b",
  "#f97316",
  "#ef4444",
  "#dc2626",
  "#9ca3af",
  "#6b7280",
];

/** Persian labels for campaign statuses */
export const CAMPAIGN_STATUS_LABELS: Record<string, string> = {
  draft: "پیش‌نویس",
  scheduled: "زمان‌بندی شده",
  running: "در حال اجرا",
  paused: "متوقف",
  completed: "تکمیل شده",
  cancelled: "لغو شده",
};

/** Persian labels for campaign types */
export const CAMPAIGN_TYPE_LABELS: Record<string, string> = {
  sms: "پیامکی",
  call: "تماسی",
  mixed: "ترکیبی",
};

/** Severity colors and icons */
export const SEVERITY_CONFIG: Record<string, { color: string; icon: string; bg: string }> = {
  critical: { color: "text-red-700", icon: "🔴", bg: "bg-red-50" },
  warning: { color: "text-amber-700", icon: "🟡", bg: "bg-amber-50" },
  info: { color: "text-blue-700", icon: "🔵", bg: "bg-blue-50" },
};

/** Persian labels for invoice statuses */
export const INVOICE_STATUS_LABELS: Record<string, string> = {
  draft: "پیش‌نویس",
  issued: "صادر شده",
  sent: "ارسال شده",
  partially_paid: "پرداخت جزئی",
  paid: "پرداخت شده",
  overdue: "سررسید گذشته",
  cancelled: "لغو شده",
};

/** Colors for invoice statuses */
export const INVOICE_STATUS_COLORS: Record<string, string> = {
  draft: "bg-gray-100 text-gray-700",
  issued: "bg-blue-50 text-blue-700",
  sent: "bg-purple-50 text-purple-700",
  partially_paid: "bg-amber-50 text-amber-700",
  paid: "bg-green-50 text-green-700",
  overdue: "bg-red-50 text-red-700",
  cancelled: "bg-gray-100 text-gray-500",
};

/** Navigation items for sidebar — label is a translation key in "nav" namespace */
export const NAV_ITEMS = [
  { href: "/", labelKey: "dashboard", icon: "📊" },
  { href: "/leads", labelKey: "leads", icon: "📋" },
  { href: "/funnel", labelKey: "funnel", icon: "🔻" },
  { href: "/segments", labelKey: "segments", icon: "🎯" },
  { href: "/communications", labelKey: "communications", icon: "💬" },
  { href: "/sales", labelKey: "sales", icon: "💰" },
  { href: "/campaigns", labelKey: "campaigns", icon: "📣" },
  { href: "/imports", labelKey: "imports", icon: "📂" },
  { href: "/reports", labelKey: "reports", icon: "📥" },
  { href: "/data-sync", labelKey: "dataSync", icon: "🔄" },
  { href: "/processes", labelKey: "processes", icon: "⚙️" },
  { href: "/predictive", labelKey: "predictive", icon: "🔮" },
  { href: "/alerts", labelKey: "alerts", icon: "🔔" },
  { href: "/team", labelKey: "team", icon: "👥" },
  { href: "/users", labelKey: "users", icon: "🔑" },
  { href: "/usage", labelKey: "usage", icon: "📊" },
  { href: "/activity", labelKey: "activity", icon: "📜" },
  { href: "/settings", labelKey: "settings", icon: "⚙️" },
] as const;

