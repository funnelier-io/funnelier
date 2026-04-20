"use client";

import { useTranslations } from "next-intl";
import type { OnboardingStep1Data, OnboardingStep3Data } from "@/types/onboarding";

interface Props {
  companyData: OnboardingStep1Data;
  plan: string;
  accountData: OnboardingStep3Data;
  onBack: () => void;
  onSubmit: () => void;
  onGoToStep: (step: number) => void;
  submitting: boolean;
  error: string | null;
}

export default function StepReviewConfirm({
  companyData,
  plan,
  accountData,
  onBack,
  onSubmit,
  onGoToStep,
  submitting,
  error,
}: Props) {
  const t = useTranslations("onboarding.review");
  const tComp = useTranslations("onboarding.company");
  const tAct = useTranslations("onboarding.actions");

  const Section = ({
    title,
    step,
    children,
  }: {
    title: string;
    step: number;
    children: React.ReactNode;
  }) => (
    <div className="bg-white rounded-lg border border-gray-200 p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-semibold text-gray-800">{title}</h3>
        <button
          type="button"
          onClick={() => onGoToStep(step)}
          className="text-blue-600 text-sm hover:underline"
        >
          {t("edit")}
        </button>
      </div>
      <dl className="space-y-2 text-sm">{children}</dl>
    </div>
  );

  const Row = ({ label, value }: { label: string; value: string }) => (
    <div className="flex justify-between">
      <dt className="text-gray-500">{label}</dt>
      <dd className="font-medium text-gray-800">{value}</dd>
    </div>
  );

  return (
    <div className="max-w-lg mx-auto space-y-5">
      <h2 className="text-xl font-bold text-gray-800">{t("title")}</h2>

      {/* Company Info */}
      <Section title={t("companySection")} step={1}>
        <Row label={t("companyName")} value={companyData.company_name} />
        <Row label={t("slug")} value={companyData.slug} />
        <Row
          label={t("industry")}
          value={tComp(`industryOptions.${companyData.industry}`)}
        />
        <Row
          label={t("companySize")}
          value={tComp(`sizeOptions.${companyData.company_size}`)}
        />
      </Section>

      {/* Plan */}
      <Section title={t("planSection")} step={2}>
        <Row label={t("selectedPlan")} value={plan} />
      </Section>

      {/* Admin Account */}
      <Section title={t("accountSection")} step={3}>
        <Row label={t("adminName")} value={accountData.admin_full_name} />
        <Row label={t("adminUsername")} value={accountData.admin_username} />
        <Row label={t("adminEmail")} value={accountData.admin_email} />
      </Section>

      {/* Error */}
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg p-3 text-sm text-center">
          {error}
        </div>
      )}

      {/* Navigation */}
      <div className="flex justify-between pt-4">
        <button
          type="button"
          onClick={onBack}
          disabled={submitting}
          className="px-8 py-2.5 border border-gray-300 rounded-lg text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors disabled:opacity-50"
        >
          {tAct("back")}
        </button>
        <button
          type="button"
          onClick={onSubmit}
          disabled={submitting}
          className="px-8 py-2.5 bg-blue-600 text-white rounded-lg text-sm font-semibold hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {submitting ? tAct("submitting") : tAct("submit")}
        </button>
      </div>
    </div>
  );
}

