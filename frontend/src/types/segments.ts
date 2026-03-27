export interface SegmentCount {
  segment: string;
  segment_name_fa: string;
  count: number;
  percentage: number;
}

export interface SegmentDistribution {
  tenant_id: string;
  analysis_date: string;
  total_contacts: number;
  segments: SegmentCount[];
}

export interface SegmentRecommendation {
  segment: string;
  segment_name_fa: string;
  description_fa: string;
  recommended_message_types: string[];
  recommended_products: string[];
  contact_frequency: string;
  channel_priority: string[];
  discount_allowed: boolean;
  max_discount_percent: number;
}

export interface AllRecommendationsResponse {
  recommendations: SegmentRecommendation[];
}

