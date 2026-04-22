export interface ABTestVariant {
  variant: "A" | "B";
  template_id: string;
  content: string;
  recipient_count: number;
  sent_count: number;
  delivered_count: number;
  response_count: number;
  conversion_count: number;
  delivery_rate: number;
  response_rate: number;
  conversion_rate: number;
}

export interface ABTestConfig {
  campaign_id: string;
  variant_a: ABTestVariant;
  variant_b: ABTestVariant;
  split_percent: number;
  confidence_level: number;
  winner?: "A" | "B" | null;
  is_complete: boolean;
  started_at: string | null;
}

export interface ABTestLaunchRequest {
  variant_a_content: string;
  variant_b_content: string;
  split_percent?: number;
}

export interface ABTestWinnerResponse {
  campaign_id: string;
  winner: "A" | "B" | null;
  confidence: number;
  message: string;
}

