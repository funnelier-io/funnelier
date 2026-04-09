"use client";

import { useTranslations } from "next-intl";
import { useFormat } from "@/lib/use-format";
import { useApi } from "@/lib/hooks";
import StatCard from "@/components/ui/StatCard";
import { cn } from "@/lib/utils";

interface UsageData {
  tenant_id: string;
  period_start: string;
  period_end: string;
  contacts_count: number;
  contacts_limit: number;
  contacts_percent: number;
  sms_sent: number;
  sms_limit: number;
  sms_percent: number;
  api_calls_today: number;
  api_calls_limit: number;
  api_calls_percent: number;
  users_count: number;
  users_limit: number;
  users_percent: number;
  data_sources_count: number;
  data_sources_limit: number;
  plan: string;
  plan_features: string[];
  warnings: string[];
}

interface PlanInfo {
  name: string;
  display_name: string;
  display_name_fa: string;
  price_monthly: number;
  price_yearly: number;
  is_popular: boolean;
  limits: {
    max_contacts: number;
    max_sms_per_month: number;
    max_users: number;
    max_api_calls_per_day: number;
    max_data_sources: number;
    features: string[];
  };
}

interface PlansResponse {
  plans: PlanInfo[];
  current_plan: string;
}

export default function UsagePage() {
  const t = useTranslations("usage");
  const fmt = useFormat();
  const tc = useTranslations("common");

  const usage = useApi<UsageData>("/tenants/me/usage/detailed");
  const plans = useApi<PlansResponse>("/tenants/me/billing/plans");

  if (usage.isLoading) {
    return (
      <div className="flex items-center justify-center h-64 text-gray-400 text-sm">
        {tc("loading")}
      </div>
    );
  }

  const data = usage.data;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-bold">{t("title")}</h1>
        <p className="text-sm text-gray-500">{t("subtitle")}</p>
      </div>

      {/* Warnings */}
      {data?.warnings && data.warnings.length > 0 && (
        <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 space-y-1">
          {data.warnings.map((w, i) => (
            <div key={i} className="text-sm text-amber-700">⚠️ {t(`warning_${w}`)}</div>
          ))}
        </div>
      )}

      {/* Usage Summary Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title={t("contacts")}
          value={`${fmt.number(data?.contacts_count || 0)} / ${fmt.number(data?.contacts_limit || 0)}`}
          subtitle={fmt.percentRaw(data?.contacts_percent || 0)}
          icon="👥"
          color="text-blue-600"
        />
        <StatCard
          title={t("smsSent")}
          value={`${fmt.number(data?.sms_sent || 0)} / ${fmt.number(data?.sms_limit || 0)}`}
          subtitle={fmt.percentRaw(data?.sms_percent || 0)}
          icon="💬"
          color="text-green-600"
        />
        <StatCard
          title={t("apiCalls")}
          value={`${fmt.number(data?.api_calls_today || 0)} / ${fmt.number(data?.api_calls_limit || 0)}`}
          subtitle={t("today")}
          icon="🔌"
          color="text-purple-600"
        />
        <StatCard
          title={t("users")}
          value={`${fmt.number(data?.users_count || 0)} / ${fmt.number(data?.users_limit || 0)}`}
          subtitle={fmt.percentRaw(data?.users_percent || 0)}
          icon="👤"
          color="text-amber-600"
        />
      </div>

      {/* Usage Bars */}
      <div className="bg-white rounded-lg shadow p-5 space-y-4">
        <h2 className="text-sm font-semibold text-gray-700">{t("usageDetails")}</h2>
        <UsageBar label={t("contacts")} current={data?.contacts_count || 0} limit={data?.contacts_limit || 1} percent={data?.contacts_percent || 0} />
        <UsageBar label={t("smsSent")} current={data?.sms_sent || 0} limit={data?.sms_limit || 1} percent={data?.sms_percent || 0} />
        <UsageBar label={t("apiCalls")} current={data?.api_calls_today || 0} limit={data?.api_calls_limit || 1} percent={data?.api_calls_percent || 0} />
        <UsageBar label={t("users")} current={data?.users_count || 0} limit={data?.users_limit || 1} percent={data?.users_percent || 0} />
        <UsageBar label={t("dataSources")} current={data?.data_sources_count || 0} limit={data?.data_sources_limit || 1} percent={data?.data_sources_count && data?.data_sources_limit ? (data.data_sources_count / data.data_sources_limit * 100) : 0} />
      </div>

      {/* Current Plan Features */}
      {data?.plan_features && (
        <div className="bg-white rounded-lg shadow p-5">
          <h2 className="text-sm font-semibold text-gray-700 mb-3">{t("currentPlan")}: <span className="text-blue-600">{data.plan}</span></h2>
          <div className="flex flex-wrap gap-2">
            {data.plan_features.map((f) => (
              <span key={f} className="text-xs bg-blue-50 text-blue-700 px-2 py-1 rounded-full">
                ✓ {t(`feature_${f}`, { defaultValue: f })}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Plans Comparison */}
      {plans.data?.plans && (
        <div className="space-y-4">
          <h2 className="text-lg font-semibold">{t("availablePlans")}</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
            {plans.data.plans.map((plan) => (
              <div
                key={plan.name}
                className={cn(
                  "bg-white rounded-lg shadow p-5 space-y-3 border-2",
                  plan.name === plans.data?.current_plan
                    ? "border-blue-500"
                    : plan.is_popular
                      ? "border-green-300"
                      : "border-transparent"
                )}
              >
                {plan.is_popular && (
                  <span className="text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded-full">{t("popular")}</span>
                )}
                {plan.name === plans.data?.current_plan && (
                  <span className="text-xs bg-blue-100 text-blue-700 px-2 py-0.5 rounded-full">{t("currentPlanBadge")}</span>
                )}

                <h3 className="text-lg font-bold">{plan.display_name_fa}</h3>

                <div>
                  <span className="text-2xl font-bold text-gray-900">
                    {plan.price_monthly === 0
                      ? t("free")
                      : fmt.currency(plan.price_monthly)}
                  </span>
                  {plan.price_monthly > 0 && (
                    <span className="text-xs text-gray-400"> / {t("perMonth")}</span>
                  )}
                </div>

                <div className="space-y-1 text-xs text-gray-600 pt-2 border-t">
                  <div>👥 {fmt.number(plan.limits.max_contacts)} {t("contacts")}</div>
                  <div>💬 {fmt.number(plan.limits.max_sms_per_month)} {t("smsPerMonth")}</div>
                  <div>👤 {fmt.number(plan.limits.max_users)} {t("users")}</div>
                  <div>🔌 {fmt.number(plan.limits.max_api_calls_per_day)} {t("apiPerDay")}</div>
                  <div>📦 {fmt.number(plan.limits.max_data_sources)} {t("dataSources")}</div>
                </div>

                <div className="text-xs text-gray-500 pt-2">
                  {plan.limits.features.length} {t("features")}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function UsageBar({ label, current, limit, percent }: { label: string; current: number; limit: number; percent: number }) {
  const fmt = useFormat();
  const barColor = percent >= 90 ? "bg-red-500" : percent >= 70 ? "bg-amber-500" : "bg-blue-500";

  return (
    <div>
      <div className="flex justify-between text-sm mb-1">
        <span className="text-gray-600">{label}</span>
        <span className="text-gray-400">{fmt.number(current)} / {fmt.number(limit)}</span>
      </div>
      <div className="w-full bg-gray-200 rounded-full h-2.5">
        <div
          className={cn("h-2.5 rounded-full transition-all", barColor)}
          style={{ width: `${Math.min(percent, 100)}%` }}
        />
      </div>
    </div>
  );
}

