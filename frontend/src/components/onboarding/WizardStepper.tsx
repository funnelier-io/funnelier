"use client";

import { useTranslations } from "next-intl";

interface WizardStepperProps {
  currentStep: number;
  totalSteps: number;
}

const STEP_KEYS = ["company", "plan", "account", "review"] as const;

export default function WizardStepper({ currentStep, totalSteps }: WizardStepperProps) {
  const t = useTranslations("onboarding.steps");

  return (
    <div className="flex items-center justify-center w-full max-w-2xl mx-auto mb-8">
      {Array.from({ length: totalSteps }, (_, i) => {
        const step = i + 1;
        const isCompleted = step < currentStep;
        const isActive = step === currentStep;

        return (
          <div key={step} className="flex items-center flex-1 last:flex-none">
            {/* Step circle + label */}
            <div className="flex flex-col items-center">
              <div
                className={`w-10 h-10 rounded-full flex items-center justify-center text-sm font-bold border-2 transition-colors ${
                  isCompleted
                    ? "bg-blue-600 border-blue-600 text-white"
                    : isActive
                    ? "bg-white border-blue-600 text-blue-600"
                    : "bg-white border-gray-300 text-gray-400"
                }`}
              >
                {isCompleted ? "✓" : step}
              </div>
              <span
                className={`mt-2 text-xs font-medium whitespace-nowrap ${
                  isActive ? "text-blue-600" : isCompleted ? "text-blue-600" : "text-gray-400"
                }`}
              >
                {t(STEP_KEYS[i])}
              </span>
            </div>

            {/* Connector line (not after last step) */}
            {step < totalSteps && (
              <div
                className={`flex-1 h-0.5 mx-2 mt-[-1rem] ${
                  isCompleted ? "bg-blue-600" : "bg-gray-300"
                }`}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}

