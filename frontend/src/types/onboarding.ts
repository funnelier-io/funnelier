/**
 * Onboarding wizard types — mirrors backend OnboardingRequest/Response
 * and PlanInfo/PlanLimits from billing_service.
 */

export interface OnboardingStep1Data {
  company_name: string;
  slug: string;
  industry: string;
  company_size: string;
  phone?: string;
  email?: string;
  description?: string;
}

export interface OnboardingStep2Data {
  plan: string;
}

export interface OnboardingStep3Data {
  admin_username: string;
  admin_email: string;
  admin_password: string;
  admin_password_confirm: string; // client-only
  admin_full_name: string;
}

export interface OnboardingFormData
  extends OnboardingStep1Data,
    OnboardingStep2Data,
    Omit<OnboardingStep3Data, "admin_password_confirm"> {}

export interface OnboardingResponse {
  tenant_id: string;
  tenant_name: string;
  slug: string;
  plan: string;
  admin_user_id: string;
  admin_username: string;
  access_token: string;
  refresh_token: string;
  message: string;
}

export interface PlanLimits {
  max_contacts: number;
  max_sms_per_month: number;
  max_users: number;
  max_api_calls_per_day: number;
  max_import_size_mb: number;
  max_data_sources: number;
  features: string[];
}

export interface PlanInfo {
  name: string;
  display_name: string;
  display_name_fa: string;
  price_monthly: number;
  price_yearly: number;
  limits: PlanLimits;
  is_popular: boolean;
}

export interface PlansResponse {
  plans: PlanInfo[];
}

export interface SlugCheckResponse {
  slug: string;
  available: boolean;
}

