export interface StageCount {
  stage: string;
  count: number;
  percentage: number;
}

export interface ConversionRate {
  from_stage: string;
  to_stage: string;
  rate: number;
}

export interface FunnelMetrics {
  period_start: string;
  period_end: string;
  tenant_id: string;
  stage_counts: StageCount[];
  conversion_rates: ConversionRate[];
  total_leads: number;
  total_conversions: number;
  overall_conversion_rate: number;
  average_days_to_convert: number | null;
  total_revenue: number;
  average_order_value: number;
  leads_change_percent: number | null;
  conversions_change_percent: number | null;
  revenue_change_percent: number | null;
}

export interface DailySnapshot {
  date: string;
  new_leads: number;
  new_conversions: number;
  daily_revenue: number;
  conversion_rate: number;
}

export interface FunnelTrend {
  period_start: string;
  period_end: string;
  snapshots: DailySnapshot[];
}

export interface DailyReport {
  report_date: string;
  tenant_id: string;
  leads: {
    today: number;
    yesterday: number;
    change: number;
    change_percent: number;
  };
  sms: {
    sent_today: number;
    delivered_today: number;
    delivery_rate: number;
  };
  calls: {
    total_today: number;
    answered_today: number;
    successful_today: number;
    answer_rate: number;
    success_rate: number;
  };
  revenue: {
    today: number;
    yesterday: number;
    change: number;
  };
}

export interface OptimizationOpportunity {
  type: string;
  severity: string;
  details: Record<string, unknown>;
  recommendation: string;
}

export interface OptimizationResponse {
  opportunities: OptimizationOpportunity[];
  analysis_date: string;
}

