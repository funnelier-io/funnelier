export interface Contact {
  id: string;
  tenant_id: string;
  phone_number: string;
  name: string | null;
  category: string | null;
  source: string | null;
  current_stage: string;
  assigned_to: string | null;
  total_calls: number;
  answered_calls: number;
  total_call_duration: number;
  sms_count: number;
  created_at: string;
  updated_at: string | null;
}

export interface ContactListResponse {
  contacts: Contact[];
  total_count: number;
  page: number;
  page_size: number;
}

export interface LeadStatsSummary {
  total_contacts: number;
  by_stage: Record<string, number>;
  by_category: Record<string, number>;
  by_source: Record<string, number>;
}

