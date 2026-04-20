"use client";

import { useTranslations } from "next-intl";
import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api-client";
import type { OnboardingStep1Data, SlugCheckResponse } from "@/types/onboarding";

interface Props {
  data: OnboardingStep1Data;
  onChange: (data: OnboardingStep1Data) => void;
  onNext: () => void;
}

const INDUSTRIES = ["building_materials", "retail", "manufacturing", "services", "other"] as const;
const SIZES = ["small", "medium", "large", "enterprise"] as const;

function toSlug(text: string): string {
  return text
    .toLowerCase()
    .replace(/\s+/g, "-")
    .replace(/[^a-z0-9-]/g, "")
    .replace(/-+/g, "-")
    .replace(/^-|-$/g, "");
}

export default function StepCompanyInfo({ data, onChange, onNext }: Props) {
  const t = useTranslations("onboarding.company");
  const tErr = useTranslations("onboarding.errors");
  const tAct = useTranslations("onboarding.actions");

  const [slugStatus, setSlugStatus] = useState<"idle" | "checking" | "available" | "taken">("idle");
  const [errors, setErrors] = useState<Record<string, string>>({});
  const debounceRef = useRef<NodeJS.Timeout | null>(null);

  const update = (patch: Partial<OnboardingStep1Data>) => {
    onChange({ ...data, ...patch });
  };

  // Auto-generate slug from company name
  const handleNameChange = (name: string) => {
    const newSlug = toSlug(name);
    update({ company_name: name, slug: newSlug });
  };

  // Debounced slug availability check
  const checkSlug = useCallback(async (slug: string) => {
    if (slug.length < 2) {
      setSlugStatus("idle");
      return;
    }
    setSlugStatus("checking");
    try {
      const res = await api<SlugCheckResponse>(
        "GET",
        `/tenants/onboard/check-slug?slug=${encodeURIComponent(slug)}`,
        undefined,
        { noAuth: true }
      );
      if (res.ok) {
        setSlugStatus(res.data.available ? "available" : "taken");
      } else {
        setSlugStatus("idle");
      }
    } catch {
      setSlugStatus("idle");
    }
  }, []);

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      if (data.slug) checkSlug(data.slug);
    }, 400);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [data.slug, checkSlug]);

  const validate = (): boolean => {
    const errs: Record<string, string> = {};
    if (!data.company_name.trim()) errs.company_name = tErr("required");
    if (!data.slug.trim()) errs.slug = tErr("required");
    if (slugStatus === "taken") errs.slug = tErr("slugTaken");
    setErrors(errs);
    return Object.keys(errs).length === 0;
  };

  const handleNext = () => {
    if (validate()) onNext();
  };

  return (
    <div className="max-w-lg mx-auto space-y-6">
      <h2 className="text-xl font-bold text-gray-800">{t("title")}</h2>

      {/* Company Name */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">{t("name")}</label>
        <input
          type="text"
          value={data.company_name}
          onChange={(e) => handleNameChange(e.target.value)}
          placeholder={t("namePlaceholder")}
          className={`w-full px-3 py-2.5 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 ${
            errors.company_name ? "border-red-400" : "border-gray-300"
          }`}
          autoFocus
        />
        {errors.company_name && <p className="text-red-500 text-xs mt-1">{errors.company_name}</p>}
      </div>

      {/* Slug */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">{t("slug")}</label>
        <div className="relative">
          <input
            type="text"
            dir="ltr"
            value={data.slug}
            onChange={(e) => update({ slug: toSlug(e.target.value) })}
            placeholder={t("slugPlaceholder")}
            className={`w-full px-3 py-2.5 border rounded-lg text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500 ${
              errors.slug ? "border-red-400" : slugStatus === "available" ? "border-green-400" : "border-gray-300"
            }`}
          />
          {/* Slug status indicator */}
          <div className="absolute inset-y-0 end-3 flex items-center pointer-events-none">
            {slugStatus === "checking" && (
              <span className="text-gray-400 text-xs">{t("slugChecking")}</span>
            )}
            {slugStatus === "available" && (
              <span className="text-green-600 text-sm">✓</span>
            )}
            {slugStatus === "taken" && (
              <span className="text-red-500 text-sm">✗</span>
            )}
          </div>
        </div>
        <p className="text-gray-400 text-xs mt-1">{t("slugHint")}</p>
        {slugStatus === "available" && (
          <p className="text-green-600 text-xs mt-1">{t("slugAvailable")}</p>
        )}
        {slugStatus === "taken" && (
          <p className="text-red-500 text-xs mt-1">{t("slugTaken")}</p>
        )}
      </div>

      {/* Industry */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">{t("industry")}</label>
        <select
          value={data.industry}
          onChange={(e) => update({ industry: e.target.value })}
          className="w-full px-3 py-2.5 border border-gray-300 rounded-lg text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          {INDUSTRIES.map((key) => (
            <option key={key} value={key}>
              {t(`industryOptions.${key}`)}
            </option>
          ))}
        </select>
      </div>

      {/* Company Size */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">{t("companySize")}</label>
        <div className="grid grid-cols-2 gap-3">
          {SIZES.map((size) => (
            <button
              key={size}
              type="button"
              onClick={() => update({ company_size: size })}
              className={`px-4 py-3 rounded-lg border text-sm text-center transition-colors ${
                data.company_size === size
                  ? "border-blue-500 bg-blue-50 text-blue-700 font-medium"
                  : "border-gray-300 bg-white text-gray-600 hover:border-gray-400"
              }`}
            >
              {t(`sizeOptions.${size}`)}
            </button>
          ))}
        </div>
      </div>

      {/* Optional fields */}
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">{t("phone")}</label>
          <input
            type="tel"
            dir="ltr"
            value={data.phone || ""}
            onChange={(e) => update({ phone: e.target.value })}
            className="w-full px-3 py-2.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">{t("email")}</label>
          <input
            type="email"
            dir="ltr"
            value={data.email || ""}
            onChange={(e) => update({ email: e.target.value })}
            className="w-full px-3 py-2.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
      </div>

      {/* Next button */}
      <div className="flex justify-end pt-4">
        <button
          type="button"
          onClick={handleNext}
          className="px-8 py-2.5 bg-blue-600 text-white rounded-lg text-sm font-semibold hover:bg-blue-700 transition-colors"
        >
          {tAct("next")}
        </button>
      </div>
    </div>
  );
}

