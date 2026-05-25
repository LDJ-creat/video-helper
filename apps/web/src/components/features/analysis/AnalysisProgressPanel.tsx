"use client";

import { useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import type { Job, LogsResponse } from "@/lib/contracts/types";
import { resolveErrorPresentation } from "@/lib/constants/errorMessages";
import { getPublicStageDisplay } from "@/lib/constants/stageMapping";
import { getAnalysisViewMode, isDuplicateAnalyzedBlocked } from "@/lib/utils/analysisViewMode";
import { pickUserFacingLog } from "@/lib/utils/jobLogDisplay";
import { AnalysisStepper } from "./AnalysisStepper";
import { AnalysisProgressBar } from "./AnalysisProgressBar";

export type AnalysisProgressPanelProps = {
    job: Job | undefined;
    logs?: LogsResponse;
    connectionMode: "sse" | "polling" | "disconnected";
    projectId: string;
    jobId: string;
    variant?: "default" | "compact";
    onResume: () => void | Promise<void>;
    onCancel: () => void | Promise<void>;
    onNavigateToResult?: () => void;
    isResuming?: boolean;
    isCanceling?: boolean;
    actionError?: string | null;
    /** When true, show brief success state before parent navigates away */
    showSuccessTransition?: boolean;
    logsAnchorId?: string;
};

export function AnalysisProgressPanel({
    job,
    logs,
    connectionMode,
    projectId: _projectId,
    jobId: _jobId,
    variant = "default",
    onResume,
    onCancel,
    onNavigateToResult,
    isResuming = false,
    isCanceling = false,
    actionError = null,
    showSuccessTransition = false,
    logsAnchorId,
}: AnalysisProgressPanelProps) {
    const t = useTranslations("Results.progress");
    const router = useRouter();
    const viewMode = getAnalysisViewMode(job);
    const isDuplicateBlocked = isDuplicateAnalyzedBlocked(job);
    const progressPercent = Math.round((job?.progress ?? 0) * 100);
    const userLog = pickUserFacingLog(logs?.items);

    const stageLabel = !job?.stage
        ? t("preparing")
        : t("processing", { stage: getPublicStageDisplay(job.stage) });

    const canCancel = job?.status === "running" || job?.status === "queued" || (job?.status === "blocked" && !isDuplicateBlocked);
    const canResume =
        job?.status === "failed" || job?.status === "canceled" || (job?.status === "blocked" && isDuplicateBlocked);
    const resumeLabel = isDuplicateBlocked
        ? t("reanalyze")
        : job?.status === "failed"
          ? t("retry")
          : t("resume");

    const successVisible = showSuccessTransition || viewMode === "succeeded";

    const connectionLabel =
        connectionMode === "sse" ? t("connectionSse") : connectionMode === "polling" ? t("connectionPolling") : null;

    const isLarge = variant === "default";
    const containerClass =
        variant === "compact"
            ? "w-full space-y-5"
            : "flex flex-col items-center justify-center min-h-[55vh] max-w-4xl mx-auto px-8 py-10 w-full space-y-8";

    if (viewMode === "loading" || !job) {
        return (
            <div className={containerClass}>
                <div className={`flex flex-col items-center ${isLarge ? "gap-4" : "gap-3"} py-12`}>
                    <div
                        className={`${isLarge ? "w-10 h-10 border-[3px]" : "w-8 h-8 border-2"} border-stone-200 border-t-orange-500 rounded-full animate-spin`}
                    />
                    <p className={`${isLarge ? "text-base" : "text-sm"} text-stone-500`}>{t("loadingJob")}</p>
                </div>
            </div>
        );
    }

    if (successVisible && (viewMode === "succeeded" || showSuccessTransition)) {
        return (
            <div className={containerClass}>
                <div className={`flex flex-col items-center ${isLarge ? "gap-5" : "gap-4"} py-12 text-center`}>
                    <div className={`${isLarge ? "w-16 h-16" : "w-14 h-14"} rounded-full bg-emerald-100 flex items-center justify-center`}>
                        <svg className={`${isLarge ? "w-9 h-9" : "w-8 h-8"} text-emerald-600`} fill="currentColor" viewBox="0 0 20 20" aria-hidden>
                            <path
                                fillRule="evenodd"
                                d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
                                clipRule="evenodd"
                            />
                        </svg>
                    </div>
                    <h2 className={`${isLarge ? "text-2xl" : "text-xl"} font-semibold text-stone-900`}>{t("succeededTitle")}</h2>
                    <p className={`${isLarge ? "text-base" : "text-sm"} text-stone-500`}>{t("succeededHint")}</p>
                </div>
            </div>
        );
    }

    return (
        <div className={containerClass}>
            {connectionLabel && viewMode === "running" ? (
                <div className="w-full flex justify-end">
                    <span className={`${isLarge ? "text-sm px-3 py-1" : "text-xs px-2 py-0.5"} text-stone-500 rounded-full bg-stone-100 border border-stone-200`}>
                        {connectionLabel}
                    </span>
                </div>
            ) : null}

            {viewMode === "running" && (
                <>
                    <AnalysisStepper currentStage={job.stage} size={isLarge ? "lg" : "md"} />
                    <AnalysisProgressBar percent={progressPercent} stageLabel={stageLabel} animated size={isLarge ? "lg" : "md"} />
                    {userLog ? (
                        <p className={`w-full text-stone-600 bg-stone-50 rounded-xl border border-stone-200 ${isLarge ? "text-base px-5 py-3" : "text-sm px-4 py-2"}`}>
                            {userLog}
                        </p>
                    ) : null}
                    {canCancel ? (
                        <button
                            type="button"
                            onClick={onCancel}
                            disabled={isCanceling}
                            className={`bg-white border border-stone-300 rounded-xl shadow-sm hover:bg-stone-50 disabled:opacity-50 disabled:cursor-not-allowed font-medium text-stone-700 ${isLarge ? "px-6 py-2.5 text-base" : "px-4 py-2 text-sm"}`}
                        >
                            {isCanceling ? t("canceling") : t("cancel")}
                        </button>
                    ) : null}
                </>
            )}

            {viewMode === "blocked" && isDuplicateBlocked && (
                <>
                    <div className="w-full rounded-2xl border border-amber-200 bg-amber-50 p-5 text-amber-900">
                        <p className="font-semibold text-lg">{t("alreadyAnalyzedTitle")}</p>
                        <p className="mt-2 text-sm text-amber-800">{t("alreadyAnalyzedBody")}</p>
                    </div>
                    <div className="flex flex-wrap gap-3 justify-center">
                        {onNavigateToResult ? (
                            <button
                                type="button"
                                onClick={onNavigateToResult}
                                className="px-4 py-2 bg-white border border-stone-300 rounded-xl shadow-sm hover:bg-stone-50 text-sm font-medium"
                            >
                                {t("viewExisting")}
                            </button>
                        ) : null}
                        <button
                            type="button"
                            onClick={onResume}
                            disabled={isResuming}
                            className="px-4 py-2 bg-stone-800 text-white rounded-xl hover:bg-stone-900 disabled:opacity-50 disabled:cursor-not-allowed text-sm font-medium"
                        >
                            {isResuming ? t("reanalyzing") : resumeLabel}
                        </button>
                    </div>
                </>
            )}

            {viewMode === "failed" && (
                <FailedAnalysisCard
                    job={job}
                    canResume={canResume}
                    resumeLabel={resumeLabel}
                    isResuming={isResuming}
                    onResume={onResume}
                    onBack={() => router.push("/projects")}
                    actionError={actionError}
                    logsAnchorId={logsAnchorId}
                />
            )}

            {viewMode === "running" && actionError ? (
                <p className="text-sm text-red-600 wrap-break-word max-w-full text-center">{actionError}</p>
            ) : null}
        </div>
    );
}

function FailedAnalysisCard({
    job,
    canResume,
    resumeLabel,
    isResuming,
    onResume,
    onBack,
    actionError,
    logsAnchorId,
}: {
    job: Job;
    canResume: boolean;
    resumeLabel: string;
    isResuming: boolean;
    onResume: () => void | Promise<void>;
    onBack: () => void;
    actionError: string | null;
    logsAnchorId?: string;
}) {
    const t = useTranslations("Results.progress");
    const presentation = job.error
        ? resolveErrorPresentation(job.error, (key, values) => t(key, values as Record<string, string>))
        : null;

    return (
        <div className="w-full rounded-2xl border border-red-200 bg-red-50 p-6 text-red-900 shadow-sm">
            <div className="flex items-start gap-3">
                <div className="flex-shrink-0 w-10 h-10 rounded-xl bg-red-100 flex items-center justify-center">
                    <svg className="w-5 h-5 text-red-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
                        />
                    </svg>
                </div>
                <div className="flex-1 min-w-0">
                    <h3 className="text-lg font-bold text-red-800">{t("failed")}</h3>
                    {presentation ? (
                        <>
                            <p className="mt-2 text-base font-medium text-red-900">{presentation.summary}</p>
                            <p className="mt-2 text-sm text-stone-700 leading-relaxed">{presentation.suggestion}</p>
                        </>
                    ) : (
                        <p className="mt-2 text-sm text-red-800">{t("error.canceled.summary")}</p>
                    )}
                </div>
            </div>

            <div className="mt-5 flex flex-wrap gap-3">
                {canResume ? (
                    <button
                        type="button"
                        onClick={onResume}
                        disabled={isResuming}
                        className="px-4 py-2.5 bg-stone-800 text-white rounded-xl hover:bg-stone-900 disabled:opacity-50 disabled:cursor-not-allowed text-sm font-semibold"
                    >
                        {isResuming ? t("resuming") : resumeLabel}
                    </button>
                ) : null}
                <button
                    type="button"
                    onClick={onBack}
                    className="px-4 py-2.5 bg-white border border-red-200 rounded-xl hover:bg-red-50/80 text-sm font-medium text-red-800"
                >
                    {t("backToProjects")}
                </button>
                {logsAnchorId ? (
                    <a
                        href={`#${logsAnchorId}`}
                        className="px-4 py-2.5 text-sm font-medium text-red-700 hover:underline self-center"
                    >
                        {t("viewLogs")}
                    </a>
                ) : null}
            </div>

            {actionError ? (
                <p className="mt-3 text-sm text-red-700 bg-red-100/60 border border-red-200 rounded-lg px-3 py-2">{actionError}</p>
            ) : null}

            {presentation ? (
                <details className="mt-4 text-sm text-red-800">
                    <summary className="cursor-pointer font-medium select-none">{t("error.technicalDetails")}</summary>
                    <div className="mt-3 space-y-2">
                        {presentation.technical.httpStatus != null ? (
                            <div>
                                <span className="font-medium">{t("error.httpStatus")}: </span>
                                <span className="font-mono">{String(presentation.technical.httpStatus)}</span>
                            </div>
                        ) : null}
                        {presentation.technical.outputTail?.trim() ? (
                            <div>
                                <div className="font-medium">{t("error.ytdlpOutput")}</div>
                                <pre className="mt-1 text-xs font-mono whitespace-pre-wrap overflow-auto bg-white/70 border border-red-200 rounded-lg p-2 max-h-40">
                                    {presentation.technical.outputTail}
                                </pre>
                            </div>
                        ) : null}
                        <pre className="text-xs font-mono whitespace-pre-wrap overflow-auto bg-white/70 border border-red-200 rounded-lg p-2 max-h-48">
                            {JSON.stringify(presentation.technical.raw, null, 2)}
                        </pre>
                    </div>
                </details>
            ) : null}
        </div>
    );
}
