export interface SMSLog {
  id: string;
  phone_number: string;
  message: string;
  template_id: string | null;
  status: string;
  delivery_status: string | null;
  sent_at: string;
  delivered_at: string | null;
  provider: string;
}

export interface SMSStats {
  total_sent: number;
  total_delivered: number;
  total_failed: number;
  total_queued: number;
  delivery_rate: number;
}

export interface CallStats {
  total_calls: number;
  total_answered: number;
  total_successful: number;
  answered_calls?: number;
  missed_calls?: number;
  outgoing_calls?: number;
  incoming_calls?: number;
  total_duration: number;
  average_duration: number;
  answer_rate: number;
  success_rate: number;
}

export interface SMSLogListResponse {
  logs: SMSLog[];
  total_count: number;
  page: number;
  page_size: number;
}

export interface CallLog {
  id: string;
  phone_number: string;
  contact_name: string | null;
  call_type: string;
  source: string;
  duration_seconds: number;
  call_time: string;
  salesperson_id: string | null;
  salesperson_name: string | null;
  is_answered: boolean;
  is_successful: boolean;
  created_at: string;
}

export interface CallLogListResponse {
  calls: CallLog[];
  total_count: number;
  page: number;
  page_size: number;
  has_next: boolean;
  has_prev: boolean;
}

