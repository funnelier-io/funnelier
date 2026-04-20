"use client";

import { useTranslations } from "next-intl";
import { useState } from "react";
import type { OnboardingStep3Data } from "@/types/onboarding";

interface Props {
  data: OnboardingStep3Data;
  onChange: (data: OnboardingStep3Data) => void;
  onNext: () => void;
  onBack: () => void;
}

export default function StepAdminAccount({ data, onChange, onNext, onBack }: Props) {
  const t = useTranslations("onboarding.account");
  const tErr = useTranslations("onboarding.errors");
  const tAct = useTranslations("onboarding.actions");
  const [errors, setErrors] = useState<Record<string, string>>({});

  const update = (patch: Partial<OnboardingStep3Data>) => {
    onChange({ ...data, ...patch });
  };

  const validate = (): boolean => {
    const errs: Record<string, string> = {};
    if (!data.admin_full_name.trim()) errs.admin_full_name = tErr("required");
    if (data.admin_username.length < 3) errs.admin_username = tErr("usernameMin");
    if (!data.admin_email.match(/^[^@]+@[^@]+\.[^@]+$/)) errs.admin_email = tErr("emailInvalid");
    if (data.admin_password.length < 8) errs.admin_password = tErr("passwordMin");
    if (data.admin_password !== data.admin_password_confirm) errs.admin_password_confirm = t("passwordMismatch");
    setErrors(errs);
    return Object.keys(errs).length === 0;
  };

  const handleNext = () => {
    if (validate()) onNext();
  };

  const fieldClass = (name: string) =>
    `w-full px-3 py-2.5 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 ${
      errors[name] ? "border-red-400" : "border-gray-300"
    }`;

  return (
    <div className="max-w-lg mx-auto space-y-5">
      <h2 className="text-xl font-bold text-gray-800">{t("title")}</h2>

      {/* Full Name */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">{t("fullName")}</label>
        <input
          type="text"
          value={data.admin_full_name}
          onChange={(e) => update({ admin_full_name: e.target.value })}
          placeholder={t("fullNamePlaceholder")}
          className={fieldClass("admin_full_name")}
          autoFocus
        />
        {errors.admin_full_name && <p className="text-red-500 text-xs mt-1">{errors.admin_full_name}</p>}
      </div>

      {/* Username */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">{t("username")}</label>
        <input
          type="text"
          dir="ltr"
          value={data.admin_username}
          onChange={(e) => update({ admin_username: e.target.value })}
          placeholder={t("usernamePlaceholder")}
          className={fieldClass("admin_username")}
        />
        {errors.admin_username && <p className="text-red-500 text-xs mt-1">{errors.admin_username}</p>}
      </div>

      {/* Email */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">{t("email")}</label>
        <input
          type="email"
          dir="ltr"
          value={data.admin_email}
          onChange={(e) => update({ admin_email: e.target.value })}
          placeholder={t("emailPlaceholder")}
          className={fieldClass("admin_email")}
        />
        {errors.admin_email && <p className="text-red-500 text-xs mt-1">{errors.admin_email}</p>}
      </div>

      {/* Password */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">{t("password")}</label>
        <input
          type="password"
          dir="ltr"
          value={data.admin_password}
          onChange={(e) => update({ admin_password: e.target.value })}
          placeholder={t("passwordPlaceholder")}
          className={fieldClass("admin_password")}
        />
        {errors.admin_password && <p className="text-red-500 text-xs mt-1">{errors.admin_password}</p>}
      </div>

      {/* Confirm Password */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">{t("passwordConfirm")}</label>
        <input
          type="password"
          dir="ltr"
          value={data.admin_password_confirm}
          onChange={(e) => update({ admin_password_confirm: e.target.value })}
          placeholder={t("passwordConfirmPlaceholder")}
          className={fieldClass("admin_password_confirm")}
        />
        {errors.admin_password_confirm && (
          <p className="text-red-500 text-xs mt-1">{errors.admin_password_confirm}</p>
        )}
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
          onClick={handleNext}
          className="px-8 py-2.5 bg-blue-600 text-white rounded-lg text-sm font-semibold hover:bg-blue-700 transition-colors"
        >
          {tAct("next")}
        </button>
      </div>
    </div>
  );
}

