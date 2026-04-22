export interface SegmentRule {
  id: string;
  tenant_id: string;
  name: string;
  color: string;
  priority: number;
  r_min: number;
  r_max: number;
  f_min: number;
  f_max: number;
  m_min: number;
  m_max: number;
  is_active: boolean;
  created_at: string;
  updated_at: string | null;
}

export interface SegmentRuleCreateRequest {
  name: string;
  color: string;
  priority: number;
  r_min: number;
  r_max: number;
  f_min: number;
  f_max: number;
  m_min: number;
  m_max: number;
}

export interface SegmentRulePreviewResponse {
  rule_id: string;
  matched_count: number;
  sample_contacts: Array<{ id: string; phone: string; rfm_score: string }>;
}

export interface BulkAssignResponse {
  rule_id: string;
  assigned_count: number;
}

export interface SegmentRuleListResponse {
  rules: SegmentRule[];
  total: number;
}

