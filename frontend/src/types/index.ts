export type { LoginRequest, UserResponse, TokenResponse, RefreshRequest } from "./auth";
export type {
  StageCount,
  ConversionRate,
  FunnelMetrics,
  DailySnapshot,
  FunnelTrend,
  DailyReport,
  OptimizationOpportunity,
  OptimizationResponse,
} from "./analytics";
export type { Contact, ContactListResponse, LeadStatsSummary } from "./leads";
export type {
  SegmentCount,
  SegmentDistribution,
  SegmentRecommendation,
  AllRecommendationsResponse,
} from "./segments";
export type {
  SMSLog,
  SMSStats,
  SMSBalance,
  CallStats,
  SMSLogListResponse,
  TemplateVariable,
  TemplatePreviewResponse,
} from "./communications";
export type {
  Salesperson,
  PerformanceMetrics,
  SalespersonPerformance,
  TeamPerformance,
  SalespersonListResponse,
} from "./team";
export type {
  Campaign,
  CampaignListResponse,
  CampaignStats,
  CreateCampaignRequest,
} from "./campaigns";
export type {
  AlertRule,
  AlertInstance,
  AlertListResponse,
  CreateAlertRuleRequest,
} from "./alerts";
export type {
  Product,
  ProductListResponse,
  Invoice,
  InvoiceLineItem,
  InvoiceListResponse,
  Payment,
  PaymentListResponse,
  SalesStats,
} from "./sales";
export type {
  ConnectorInfo,
  DataSource,
  DataSourceListResponse,
  SyncLog,
  SyncHistoryResponse,
  SyncStatus,
  SyncResult,
  ConnectionTestResult,
  DedupStrategy,
  DataSourceCreateRequest,
  DataSourceUpdateRequest,
  ScheduleUpdateRequest,
} from "./erp-sync";
export type {
  ExportFormat,
  ReportType,
  ScheduleFrequency,
  ExportRequest,
  ScheduledReportRequest,
  CustomReportRequest,
  ReportColumnInfo,
  ScheduledReportResponse,
  ScheduledReportListResponse,
} from "./export";
export type {
  Notification,
  NotificationType,
  NotificationSeverity,
  NotificationListResponse,
  UnreadCountResponse,
  MarkReadResponse,
  NotificationPreference,
  NotificationPreferenceUpdate,
  CreateNotificationRequest,
} from "./notifications";
export type {
  OnboardingStep1Data,
  OnboardingStep2Data,
  OnboardingStep3Data,
  OnboardingFormData,
  OnboardingResponse,
  PlanInfo,
  PlanLimits,
  PlansResponse,
  SlugCheckResponse,
} from "./onboarding";
