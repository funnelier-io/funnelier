/** ERP/CRM Connector info */
export interface ConnectorInfo {
  name: string;
  display_name: string;
  supports_invoices: boolean;
  supports_payments: boolean;
  supports_customers: boolean;
  supports_products: boolean;
  sync_direction: string;
}

/** Data source configuration */
export interface DataSource {
  id: string;
  tenant_id: string;
  name: string;
  source_type: string;
  connection_config: Record<string, unknown>;
  field_mappings: Record<string, string>;
  sync_interval_minutes: number;
  sync_enabled: boolean;
  is_active: boolean;
  last_sync_at: string | null;
  last_sync_status: string | null;
  last_sync_records: number;
  created_at: string;
  updated_at: string | null;
}

export interface DataSourceListResponse {
  sources: DataSource[];
  total_count: number;
}

/** Sync log entry */
export interface SyncLog {
  id: string;
  tenant_id: string;
  data_source_id: string | null;
  sync_type: string;
  direction: string;
  status: string;
  records_fetched: number;
  records_created: number;
  records_updated: number;
  records_skipped: number;
  records_failed: number;
  started_at: string;
  completed_at: string | null;
  duration_seconds: number | null;
  error_message: string | null;
  errors: string[];
  details: Record<string, unknown>;
  triggered_by: string;
  created_at: string;
}

export interface SyncHistoryResponse {
  logs: SyncLog[];
  total_count: number;
}

/** Sync status for a data source */
export interface SyncStatus {
  source_id: string;
  source_name: string;
  source_type: string;
  is_active: boolean;
  last_sync_at: string | null;
  last_sync_status: string | null;
  last_sync_records: number;
  recent_logs: SyncLog[];
  connector_info: Record<string, unknown>;
}

/** Sync trigger result */
export interface SyncResult {
  success: boolean;
  records_synced: number;
  records_created: number;
  records_updated: number;
  records_failed: number;
  errors: string[];
  duration_seconds: number | null;
  details: Record<string, unknown>;
}

/** Connection test result */
export interface ConnectionTestResult {
  success: boolean;
  message: string;
  connector?: Record<string, unknown>;
}

/** Dedup strategy */
export interface DedupStrategy {
  name: string;
  display_name: string;
  description: string;
  is_default: boolean;
}

/** Create data source request */
export interface DataSourceCreateRequest {
  name: string;
  source_type: string;
  connection_config: Record<string, unknown>;
  field_mappings?: Record<string, string>;
  sync_interval_minutes?: number;
  is_active?: boolean;
  description?: string;
}

/** Update data source request */
export interface DataSourceUpdateRequest {
  name?: string;
  connection_config?: Record<string, unknown>;
  field_mappings?: Record<string, string>;
  sync_interval_minutes?: number;
  is_active?: boolean;
  description?: string;
}

/** Schedule update request */
export interface ScheduleUpdateRequest {
  sync_interval_minutes: number;
  sync_enabled: boolean;
}

