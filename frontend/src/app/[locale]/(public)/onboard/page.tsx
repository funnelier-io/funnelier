"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { useRouter } from "@/i18n/navigation";
import { Link } from "@/i18n/navigation";
import { api, setTokens } from "@/lib/api-client";
import { useAuthStore } from "@/stores/auth-store";
import type {
  OnboardingStep1Data,
  OnboardingStep3Data,
  OnboardingFormData,
  OnboardingResponse,
} from "@/types/onboarding";

import WizardStepper from "@/components/onboarding/WizardStepper";
import StepCompanyInfo from "@/components/onboarding/StepCompanyInfo";
import StepPlanSelection from "@/components/onboarding/StepPlanSelection";
import StepAdminAccount from "@/components/onboarding/StepAdminAccount";
import StepReviewConfirm from "@/components/onboarding/StepReviewConfirm";

const INITIAL_STEP1: OnboardingStep1Data = {
  company_name: "",
  slug: "",
  industry: "building_materials",
  company_size: "small",
};

const INITIAL_STEP3: OnboardingStep3Data = {
  admin_full_name: "",
  admin_username: "",
  admin_email: "",
  admin_password: "",
  admin_password_confirm: "",
};

export default function OnboardPage() {
  const t = useTranslations("onboarding");
  const tApp = useTranslations("app");
  const router = useRouter();
  const { checkAuth } = useAuthStore();

  const [step, setStep] = useState(1);
  const [step1, setStep1] = useState<OnboardingStep1Data>(INITIAL_STEP1);
  const [plan, setPlan] = useState("basic");
  const [step3, setStep3] = useState<OnboardingStep3Data>(INITIAL_STEP3);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const handleSubmit = async () => {
    setError(null);
    setSubmitting(true);

    const payload: OnboardingFormData = {
      company_name: step1.company_name,
      slug: step1.slug,
      industry: step1.industry,
      company_size: step1.company_size,
      phone: step1.phone,
      email: step1.email,
      description: step1.description,
      plan,
      admin_full_name: step3.admin_full_name,
      admin_username: step3.admin_username,
      admin_email: step3.admin_email,
      admin_password: step3.admin_password,
    };

    try {
      const res = await api<OnboardingResponse>(
        "POST",
        "/tenants/onboard",
        payload,
        { noAuth: true }
      );

      if (res.ok) {
        // Store tokens and redirect
        setTokens(res.data.access_token, res.data.refresh_token);
        setSuccess(true);
        // Load user from the new token
        await checkAuth();
        // Redirect to dashboard after a brief moment
        setTimeout(() => router.push("/"), 1500);
      } else {
        const detail =
          (res.data as unknown as { detail?: string })?.detail || t("errors.generic");
        setError(detail);
      }
    } catch {
      setError(t("errors.generic"));
    } finally {
      setSubmitting(false);
    }
  };

  // Success screen
  if (success) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-50">
        <div className="text-center bg-white rounded-xl shadow-lg p-10 max-w-md">
          <div className="text-6xl mb-4">🎉</div>
          <h1 className="text-2xl font-bold text-gray-800 mb-2">{t("success.title")}</h1>
          <p className="text-gray-500">{t("success.message")}</p>
          <div className="mt-6">
            <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-600 mx-auto" />
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b border-gray-200 py-4 px-6">
        <div className="max-w-4xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="text-3xl">🎯</span>
            <span className="text-xl font-bold text-blue-600">{tApp("name")}</span>
          </div>
          <div className="text-sm text-gray-500">
            {t("actions.loginLink")}{" "}
            <Link href="/login" className="text-blue-600 hover:underline font-medium">
              {t("actions.login")}
            </Link>
          </div>
        </div>
      </div>

      {/* Wizard content */}
      <div className="max-w-4xl mx-auto py-8 px-6">
        {/* Title */}
        <div className="text-center mb-6">
          <h1 className="text-2xl font-bold text-gray-800">{t("title")}</h1>
          <p className="text-gray-500 text-sm mt-1">{t("subtitle")}</p>
        </div>

        {/* Stepper */}
        <WizardStepper currentStep={step} totalSteps={4} />

        {/* Steps */}
        {step === 1 && (
          <StepCompanyInfo
            data={step1}
            onChange={setStep1}
            onNext={() => setStep(2)}
          />
        )}

        {step === 2 && (
          <StepPlanSelection
            selectedPlan={plan}
            onSelect={setPlan}
            onNext={() => setStep(3)}
            onBack={() => setStep(1)}
          />
        )}

        {step === 3 && (
          <StepAdminAccount
            data={step3}
            onChange={setStep3}
            onNext={() => setStep(4)}
            onBack={() => setStep(2)}
          />
        )}

        {step === 4 && (
          <StepReviewConfirm
            companyData={step1}
            plan={plan}
            accountData={step3}
            onBack={() => setStep(3)}
            onSubmit={handleSubmit}
            onGoToStep={setStep}
            submitting={submitting}
            error={error}
          />
        )}
      </div>

      {/* Footer */}
      <div className="text-center py-6">
        <p className="text-xs text-gray-400">{tApp("copyright")}</p>
      </div>
    </div>
  );
}

