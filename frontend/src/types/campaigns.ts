export interface CampaignTargeting {
  segments: string[];
  categories: string[];
  sources: string[];
  stages: string[];
  tags: string[];
  exclude_contacted_within_days: number | null;
  max_contacts: number | null;
}

export interface CampaignSchedule {
  start_at: string;
  end_at: string | null;
  send_times: string[];
  days_of_week: number[];
  timezone: string;
}

export interface Campaign {
  id: string;
  tenant_id: string;
  name: string;
  description: string | null;
  campaign_type: string; // sms, call, mixed
  template_id: string | null;
  content: string | null;
  targeting: CampaignTargeting;
  schedule: CampaignSchedule | null;
  status: string; // draft, scheduled, running, paused, completed, cancelled
  is_active: boolean;
  total_recipients: number;
  sent_count: number;
  delivered_count: number;
  failed_count: number;
  response_count: number;
  conversion_count: number;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
  updated_at: string | null;
}

export interface CampaignListResponse {
  campaigns: Campaign[];
  total_count: number;
  page: number;
  page_size: number;
}

export interface CampaignStats {
  campaign_id: string;
  campaign_name: string;
  status: string;
  total_recipients: number;
  sent_count: number;
  delivered_count: number;
  delivery_rate: number;
  failed_count: number;
  response_count: number;
  response_rate: number;
  conversion_count: number;
  conversion_rate: number;
  cost: number;
  revenue: number;
  roi: number;
}

export interface CreateCampaignRequest {
  name: string;
  description?: string;
  campaign_type: string;
  content?: string;
  template_id?: string;
  targeting?: Partial<CampaignTargeting>;
  is_active?: boolean;
}

