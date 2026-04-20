"use client";

import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import { api } from "@/lib/api-client";
import type { PlanInfo, PlansResponse } from "@/types/onboarding";

interface Props {
  selectedPlan: string;
  onSelect: (plan: string) => void;
  onNext: () => void;
  onBack: () => void;
}

function formatPrice(price: number): string {
  if (price === 0) return "";
  // Convert Rial to Toman
  const toman = Math.round(price / 10);
  return toman.toLocaleString("fa-IR");
}

export default function StepPlanSelection({ selectedPlan, onSelect, onNext, onBack }: Props) {
  const t = useTranslations("onboarding.plan");
  const tAct = useTranslations("onboarding.actions");
  const [plans, setPlans] = useState<PlanInfo[]>([]);
  const [billing, setBilling] = useState<"monthly" | "yearly">("monthly");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchPlans() {
      const res = await api<PlansResponse>(
        "GET",
        "/tenants/onboard/plans",
        undefined,
        { noAuth: true }
      );
      if (res.ok && res.data.plans) {
        setPlans(res.data.plans);
      }
      setLoading(false);
    }
    fetchPlans();
  }, []);

  if (loading) {
    return (
      <div className="flex justify-center py-16">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" />
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <h2 className="text-xl font-bold text-gray-800 text-center">{t("title")}</h2>

      {/* Billing toggle */}
      <div className="flex items-center justify-center gap-3">
        <button
          type="button"
          onClick={() => setBilling("monthly")}
          className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
            billing === "monthly" ? "bg-blue-600 text-white" : "bg-gray-100 text-gray-600"
          }`}
        >
          {t("monthly")}
        </button>
        <button
          type="button"
          onClick={() => setBilling("yearly")}
          className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
            billing === "yearly" ? "bg-blue-600 text-white" : "bg-gray-100 text-gray-600"
          }`}
        >
          {t("yearly")}
          <span className="ms-1 text-xs text-green-600 font-normal">
            {t("yearlyDiscount")}
          </span>
        </button>
      </div>

      {/* Plan cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {plans.map((plan) => {
          const isSelected = selectedPlan === plan.name;
          const price = billing === "monthly" ? plan.price_monthly : plan.price_yearly;
          const priceSuffix = billing === "monthly" ? t("perMonth") : t("perYear");

          return (
            <div
              key={plan.name}
              onClick={() => onSelect(plan.name)}
              className={`relative rounded-xl border-2 p-5 cursor-pointer transition-all hover:shadow-md ${
                isSelected
                  ? "border-blue-500 bg-blue-50 shadow-md"
                  : "border-gray-200 bg-white hover:border-gray-300"
              }`}
            >
              {/* Popular badge */}
              {plan.is_popular && (
                <div className="absolute -top-3 inset-x-0 flex justify-center">
                  <span className="bg-blue-600 text-white text-xs font-bold px-3 py-1 rounded-full">
                    {t("popular")}
                  </span>
                </div>
              )}

              {/* Plan name */}
              <h3 className="text-lg font-bold text-gray-800 mt-1">
                {plan.display_name_fa}
              </h3>
              <p className="text-xs text-gray-500">{plan.display_name}</p>

              {/* Price */}
              <div className="mt-3 mb-4">
                {price === 0 ? (
                  <span className="text-2xl font-bold text-green-600">{t("free")}</span>
                ) : (
                  <div>
                    <span className="text-2xl font-bold text-gray-800">
                      {formatPrice(price)}
                    </span>
                    <span className="text-xs text-gray-500 ms-1">
                      {t("currency")}{priceSuffix}
                    </span>
                  </div>
                )}
              </div>

              {/* Limits */}
              <ul className="space-y-2 text-sm text-gray-600 mb-4">
                <li className="flex justify-between">
                  <span>{t("contacts")}</span>
                  <span className="font-medium" dir="ltr">
                    {plan.limits.max_contacts.toLocaleString()}
                  </span>
                </li>
                <li className="flex justify-between">
                  <span>{t("smsPerMonth")}</span>
                  <span className="font-medium" dir="ltr">
                    {plan.limits.max_sms_per_month.toLocaleString()}
                  </span>
                </li>
                <li className="flex justify-between">
                  <span>{t("users")}</span>
                  <span className="font-medium" dir="ltr">
                    {plan.limits.max_users}
                  </span>
                </li>
                <li className="flex justify-between">
                  <span>{t("dataSources")}</span>
                  <span className="font-medium" dir="ltr">
                    {plan.limits.max_data_sources}
                  </span>
                </li>
              </ul>

              {/* Select button */}
              <button
                type="button"
                className={`w-full py-2 rounded-lg text-sm font-semibold transition-colors ${
                  isSelected
                    ? "bg-blue-600 text-white"
                    : "bg-gray-100 text-gray-700 hover:bg-gray-200"
                }`}
              >
                {isSelected ? t("selected") : t("select")}
              </button>
            </div>
          );
        })}
      </div>

      {/* Navigation */}
      <div className="flex justify-between pt-4">
        <button
          type="button"
          onClick={onBack}
          className="px-8 py-2.5 border border-gray-300 rounded-lg text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors"
        >
          {tAct("back")}
        </button>
        <button
          type="button"
          onClick={onNext}
          className="px-8 py-2.5 bg-blue-600 text-white rounded-lg text-sm font-semibold hover:bg-blue-700 transition-colors"
        >
          {tAct("next")}
        </button>
      </div>
    </div>
  );
}

