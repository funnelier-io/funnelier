/** Predictive Analytics TypeScript types — mirrors backend Pydantic models */

export interface ChurnPrediction {
  contact_id: string;
  phone_number: string;
  name: string | null;
  segment: string | null;
  churn_probability: number;
  risk_level: "low" | "medium" | "high" | "critical";
  risk_factors: string[];
  recommended_action: string;
  days_since_last_activity: number | null;
  last_activity_date: string | null;
}

export interface ChurnSummary {
  analysis_date: string;
  total_contacts: number;
  at_risk_count: number;
  at_risk_percentage: number;
  risk_distribution: Record<string, number>;
  top_risk_contacts: ChurnPrediction[];
  estimated_revenue_at_risk: number;
  recommendations: string[];
}

export interface LeadScore {
  contact_id: string;
  phone_number: string;
  name: string | null;
  category: string | null;
  score: number;
  grade: "A" | "B" | "C" | "D" | "F";
  scoring_factors: Record<string, number>;
  recommended_action: string;
}

export interface LeadScoringResult {
  analysis_date: string;
  total_scored: number;
  grade_distribution: Record<string, number>;
  average_score: number;
  top_leads: LeadScore[];
}

export interface ABTestResult {
  test_name: string;
  variant_a_name: string;
  variant_b_name: string;
  variant_a_conversions: number;
  variant_a_total: number;
  variant_b_conversions: number;
  variant_b_total: number;
  variant_a_rate: number;
  variant_b_rate: number;
  absolute_difference: number;
  relative_improvement: number;
  z_score: number;
  p_value: number;
  confidence_level: number;
  is_significant: boolean;
  winner: string | null;
  required_sample_size: number;
  recommendation: string;
}

export interface CampaignROI {
  campaign_id: string | null;
  campaign_name: string;
  total_cost: number;
  total_revenue: number;
  roi_percent: number;
  cost_per_lead: number;
  cost_per_conversion: number;
  leads_generated: number;
  conversions: number;
  conversion_rate: number;
  revenue_per_lead: number;
  break_even_conversions: number;
}

export interface RetentionCohort {
  cohort_label: string;
  cohort_start: string;
  cohort_size: number;
  retention_by_period: Record<string, number>;
}

export interface RetentionAnalysis {
  analysis_date: string;
  period_type: string;
  cohorts: RetentionCohort[];
  average_retention_by_period: Record<string, number>;
  overall_churn_rate: number;
  average_lifetime_value: number;
}

