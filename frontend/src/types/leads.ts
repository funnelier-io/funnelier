export interface Contact {
  id: string;
  tenant_id: string;
  phone_number: string;
  name: string | null;
  email: string | null;

  // Source and categorization
  source_id: string | null;
  source_name: string | null;
  category_id: string | null;
  category_name: string | null;

  // Assignment
  assigned_to: string | null;
  assigned_at: string | null;

  // Funnel tracking
  current_stage: string;
  stage_entered_at: string;

  // RFM data
  rfm_segment: string | null;
  rfm_score: string | null;

  // Engagement metrics
  total_sms_sent: number;
  total_sms_delivered: number;
  total_calls: number;
  total_answered_calls: number;
  total_call_duration: number;

  // Sales metrics
  total_invoices: number;
  total_paid_invoices: number;
  total_revenue: number;
  last_purchase_at: string | null;
  first_purchase_at: string | null;

  // Status
  is_active: boolean;
  is_blocked: boolean;
  blocked_reason: string | null;

  // Additional data
  tags: string[];
  custom_fields: Record<string, unknown>;
  notes: string | null;

  // Timestamps
  created_at: string;
  updated_at: string | null;
}

export interface ContactListResponse {
  contacts: Contact[];
  total_count: number;
  page: number;
  page_size: number;
  has_next: boolean;
  has_prev: boolean;
}

export interface LeadStatsSummary {
  total_contacts: number;
  active_contacts: number;
  blocked_contacts: number;
  by_stage: Record<string, number>;
  by_category: Record<string, number>;
  by_source: Record<string, number>;
  by_segment: Record<string, number>;
}
