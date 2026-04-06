/* Notification types for the notification center */

export interface Notification {
  id: string;
  tenant_id: string;
  user_id: string;
  type: NotificationType;
  severity: NotificationSeverity;
  title: string;
  body?: string | null;
  source_type?: string | null;
  source_id?: string | null;
  is_read: boolean;
  read_at?: string | null;
  metadata?: Record<string, unknown> | null;
  created_at: string;
}

export type NotificationType =
  | "alert"
  | "import"
  | "campaign"
  | "system"
  | "sync"
  | "report"
  | "sms";

export type NotificationSeverity =
  | "info"
  | "success"
  | "warning"
  | "error"
  | "critical";

export interface NotificationListResponse {
  items: Notification[];
  total: number;
  unread_count: number;
}

export interface UnreadCountResponse {
  unread_count: number;
}

export interface MarkReadResponse {
  success: boolean;
  marked_count: number;
}

export interface NotificationPreference {
  user_id: string;
  in_app_enabled: boolean;
  email_enabled: boolean;
  sms_enabled: boolean;
  push_enabled: boolean;
  quiet_hours_start?: string | null;
  quiet_hours_end?: string | null;
  disabled_types: string[];
}

export interface NotificationPreferenceUpdate {
  in_app_enabled?: boolean;
  email_enabled?: boolean;
  sms_enabled?: boolean;
  push_enabled?: boolean;
  quiet_hours_start?: string | null;
  quiet_hours_end?: string | null;
  disabled_types?: string[];
}

export interface CreateNotificationRequest {
  user_id?: string | null;
  type?: string;
  severity?: string;
  title: string;
  body?: string | null;
  source_type?: string | null;
  source_id?: string | null;
  metadata?: Record<string, unknown> | null;
}

