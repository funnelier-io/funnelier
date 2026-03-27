export interface Salesperson {
  id: string;
  tenant_id: string;
  name: string;
  phone_number: string;
  email: string | null;
  role: string;
  regions: string[];
  is_active: boolean;
  assigned_leads: number;
  active_leads: number;
  created_at: string;
}

export interface PerformanceMetrics {
  total_calls: number;
  answered_calls: number;
  successful_calls: number;
  total_call_duration: number;
  average_call_duration: number;
  answer_rate: number;
  success_rate: number;
  assigned_leads: number;
  contacted_leads: number;
  contact_rate: number;
  invoices_created: number;
  invoices_paid: number;
  conversion_rate: number;
  total_revenue: number;
  average_deal_size: number;
}

export interface SalespersonPerformance {
  salesperson_id: string;
  salesperson_name: string;
  period_start: string;
  period_end: string;
  metrics: PerformanceMetrics;
  rank_by_revenue: number | null;
  rank_by_conversions: number | null;
  rank_by_calls: number | null;
}

export interface TeamPerformance {
  period_start: string;
  period_end: string;
  total_metrics: PerformanceMetrics;
  by_salesperson: SalespersonPerformance[];
  top_performers: Record<string, unknown>[];
  improvement_needed: Record<string, unknown>[];
}

export interface SalespersonListResponse {
  salespeople: Salesperson[];
  total_count: number;
}

