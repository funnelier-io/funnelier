/**
 * Export & Reporting types — Phase 20
 */

export type ExportFormat = "csv" | "xlsx" | "pdf";

export type ReportType =
  | "funnel_summary"
  | "team_performance"
  | "rfm_breakdown"
  | "contacts"
  | "invoices"
  | "call_logs"
  | "sms_logs"
  | "payments"
  | "campaign_results"
  | "custom";

export type ScheduleFrequency = "daily" | "weekly" | "monthly";

/* ── Request bodies ─────────────────────────────────────────────── */

export interface ExportRequest {
  report_type: ReportType;
  format: ExportFormat;
  start_date?: string | null;
  end_date?: string | null;
  filters?: Record<string, unknown>;
  columns?: string[] | null;
}

export interface ScheduledReportRequest {
  name: string;
  report_type: ReportType;
  format: ExportFormat;
  frequency: ScheduleFrequency;
  recipients: string[];
  filters?: Record<string, unknown>;
  columns?: string[] | null;
  is_active?: boolean;
}

export interface CustomReportRequest {
  name: string;
  data_sources: ReportType[];
  format: ExportFormat;
  start_date?: string | null;
  end_date?: string | null;
  filters?: Record<string, unknown>;
  columns?: Record<string, string[]>;
  group_by?: string | null;
  order_by?: string | null;
}

/* ── Response bodies ────────────────────────────────────────────── */

export interface ReportColumnInfo {
  key: string;
  label: string;
  label_fa: string;
  type: string;
}

export interface ScheduledReportResponse {
  id: string;
  name: string;
  report_type: string;
  format: string;
  frequency: string;
  recipients: string[];
  filters: Record<string, unknown>;
  columns: string[] | null;
  is_active: boolean;
  last_run_at: string | null;
  next_run_at: string | null;
  created_at: string;
}

export interface ScheduledReportListResponse {
  items: ScheduledReportResponse[];
  total: number;
}

