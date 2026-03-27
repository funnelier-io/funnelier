export interface AlertRule {
  id: string;
  name: string;
  metric_name: string;
  condition: string; // above, below, change_percent
  threshold_value: number;
  severity: string; // warning, critical, info
  notification_channels: string[];
  recipient_emails: string[];
  recipient_phones: string[];
  webhook_url: string | null;
  is_active: boolean;
}

export interface AlertInstance {
  id: string;
  rule_id: string;
  rule_name: string;
  triggered_at: string;
  metric_name: string;
  metric_value: number;
  threshold_value: number;
  severity: string;
  message: string;
  is_acknowledged: boolean;
  acknowledged_at: string | null;
}

export interface AlertListResponse {
  alerts: AlertInstance[];
  total_count: number;
  unacknowledged_count: number;
}

export interface CreateAlertRuleRequest {
  name: string;
  metric_name: string;
  condition: string;
  threshold_value: number;
  severity?: string;
  notification_channels?: string[];
}

