"use client";

import {
    PUBLIC_STAGES_ORDER,
    PUBLIC_STAGE_I18N_KEY,
    getPublicStageIndex,
    type PublicStage,
} from "@/lib/constants/stageMapping";
import { useTranslations } from "next-intl";

type StepState = "completed" | "current" | "upcoming";

function stepState(index: number, currentIndex: number): StepState {
    if (index < currentIndex) return "completed";
    if (index === currentIndex) return "current";
    return "upcoming";
}

export function AnalysisStepper({
    currentStage,
    size = "md",
}: {
    currentStage: string | undefined;
    size?: "md" | "lg";
}) {
    const t = useTranslations("Results.progress");
    const currentIndex = getPublicStageIndex(currentStage);
    const isLarge = size === "lg";

    return (
        <div className="w-full">
            {/* Mobile: compact */}
            <div className={`sm:hidden text-center ${isLarge ? "mb-5" : "mb-4"}`}>
                <p className={`${isLarge ? "text-sm" : "text-xs"} text-stone-500`}>
                    {t("stepCounter", { current: currentIndex + 1, total: PUBLIC_STAGES_ORDER.length })}
                </p>
                <p className={`${isLarge ? "text-base" : "text-sm"} font-semibold text-stone-900 mt-1`}>
                    {t(`stages.${PUBLIC_STAGE_I18N_KEY[PUBLIC_STAGES_ORDER[currentIndex] as PublicStage]}`)}
                </p>
            </div>

            {/* Desktop: full stepper */}
            <ol className="hidden sm:flex items-start justify-between gap-2 w-full" aria-label={t("stepperLabel")}>
                {PUBLIC_STAGES_ORDER.map((stage, index) => {
                    const state = stepState(index, currentIndex);
                    const label = t(`stages.${PUBLIC_STAGE_I18N_KEY[stage]}`);
                    return (
                        <li
                            key={stage}
                            className="flex flex-1 flex-col items-center min-w-0"
                            aria-current={state === "current" ? "step" : undefined}
                        >
                            <div className="flex items-center w-full">
                                {index > 0 ? (
                                    <div
                                        className={`${isLarge ? "h-1" : "h-0.5"} flex-1 ${index <= currentIndex ? "bg-orange-400" : "bg-stone-200"}`}
                                        aria-hidden
                                    />
                                ) : (
                                    <div className="flex-1" aria-hidden />
                                )}
                                <span
                                    className={`flex-shrink-0 rounded-full flex items-center justify-center font-semibold border-2 ${
                                        isLarge ? "w-10 h-10 text-sm" : "w-7 h-7 text-xs"
                                    } ${
                                        state === "completed"
                                            ? "bg-orange-500 border-orange-500 text-white"
                                            : state === "current"
                                              ? "bg-white border-orange-500 text-orange-600"
                                              : "bg-stone-100 border-stone-200 text-stone-400"
                                    }`}
                                >
                                    {state === "completed" ? (
                                        <svg className={`${isLarge ? "w-5 h-5" : "w-3.5 h-3.5"}`} fill="currentColor" viewBox="0 0 20 20" aria-hidden>
                                            <path
                                                fillRule="evenodd"
                                                d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                                                clipRule="evenodd"
                                            />
                                        </svg>
                                    ) : (
                                        index + 1
                                    )}
                                </span>
                                {index < PUBLIC_STAGES_ORDER.length - 1 ? (
                                    <div
                                        className={`${isLarge ? "h-1" : "h-0.5"} flex-1 ${index < currentIndex ? "bg-orange-400" : "bg-stone-200"}`}
                                        aria-hidden
                                    />
                                ) : (
                                    <div className="flex-1" aria-hidden />
                                )}
                            </div>
                            <span
                                className={`${isLarge ? "mt-3 text-sm" : "mt-2 text-[11px]"} font-medium text-center leading-tight px-0.5 ${
                                    state === "current" ? "text-orange-700" : state === "completed" ? "text-stone-600" : "text-stone-400"
                                }`}
                            >
                                {label}
                            </span>
                        </li>
                    );
                })}
            </ol>
        </div>
    );
}
