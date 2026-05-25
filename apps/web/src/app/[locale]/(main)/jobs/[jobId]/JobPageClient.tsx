"use client";

import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useJobQueryWithOptions, useJobLogsQueryWithOptions, useRetryJobMutation } from "@/lib/api/jobQueries";
import { useJobSse } from "@/lib/sse/useJobSse";
import { JobLogs } from "@/components/JobLogs";
import { AnalysisProgressPanel } from "@/components/features/analysis/AnalysisProgressPanel";
import { cancelJob } from "@/lib/api/jobApi";
import { queryKeys } from "@/lib/api/queryKeys";
import { useTranslations } from "next-intl";

const JOB_LOGS_SECTION_ID = "job-logs-section";

export function JobPageClient({ jobId }: { jobId: string }) {
    const t = useTranslations("Job");
    const tCommon = useTranslations("Results");
    const queryClient = useQueryClient();
    const retryMutation = useRetryJobMutation(jobId);

    const { connectionMode, isConnected } = useJobSse({
        jobId,
        enabled: true,
    });

    const pollingEnabled = connectionMode !== "sse";
    const { data: job, isLoading, error } = useJobQueryWithOptions(jobId, { pollingEnabled });
    const { data: logs } = useJobLogsQueryWithOptions(jobId, undefined, { pollingEnabled });

    const [actionError, setActionError] = useState<string | null>(null);
    const [isCanceling, setIsCanceling] = useState(false);

    if (isLoading) {
        return (
            <div className="min-h-screen flex items-center justify-center bg-[#FDFBF7]">
                <div className="text-stone-500">{tCommon("loading")}</div>
            </div>
        );
    }

    if (error) {
        return (
            <div className="min-h-screen flex items-center justify-center bg-[#FDFBF7]">
                <div className="text-red-600">
                    {tCommon("loadFailed")}：{(error as Error).message}
                </div>
            </div>
        );
    }

    if (!job) {
        return (
            <div className="min-h-screen flex items-center justify-center bg-[#FDFBF7]">
                <div className="text-stone-500">{t("notFound")}</div>
            </div>
        );
    }

    const handleResume = async () => {
        setActionError(null);
        try {
            await retryMutation.mutateAsync();
        } catch (e) {
            const msg = (e as { message?: unknown } | null)?.message;
            setActionError(typeof msg === "string" && msg.trim() ? msg : String(e));
        }
    };

    const handleCancel = async () => {
        if (isCanceling) return;
        setIsCanceling(true);
        setActionError(null);
        try {
            await cancelJob(jobId);
            queryClient.invalidateQueries({ queryKey: queryKeys.job(jobId) });
            queryClient.invalidateQueries({ queryKey: queryKeys.logs(jobId) });
        } catch (e) {
            const msg = (e as { message?: unknown } | null)?.message;
            setActionError(typeof msg === "string" && msg.trim() ? msg : String(e));
        } finally {
            setIsCanceling(false);
        }
    };

    return (
        <div className="min-h-screen bg-[#FDFBF7] py-8">
            <div className="max-w-5xl mx-auto px-4 space-y-6">
                <div className="bg-white rounded-2xl border border-stone-200 shadow-sm p-6">
                    <div className="flex items-center justify-between mb-4">
                        <h1 className="text-2xl font-bold text-stone-900">{t("title")}</h1>
                        <div className="text-sm text-stone-500">
                            {t("connection")}: {isConnected ? "✓" : "—"} {connectionMode}
                        </div>
                    </div>

                    <div className="text-sm text-stone-600 space-y-1 font-mono">
                        <div>
                            Job ID: <span className="text-stone-800">{job.jobId}</span>
                        </div>
                        <div>
                            Project ID: <span className="text-stone-800">{job.projectId}</span>
                        </div>
                        <div>
                            {t("type")}: {job.type}
                        </div>
                    </div>
                </div>

                <div className="bg-white rounded-2xl border border-stone-200 shadow-sm p-6">
                    <AnalysisProgressPanel
                        job={job}
                        logs={logs}
                        connectionMode={connectionMode}
                        projectId={job.projectId}
                        jobId={jobId}
                        variant="compact"
                        onResume={handleResume}
                        onCancel={handleCancel}
                        isResuming={retryMutation.isPending}
                        isCanceling={isCanceling}
                        actionError={actionError}
                        logsAnchorId={JOB_LOGS_SECTION_ID}
                    />
                </div>

                <div id={JOB_LOGS_SECTION_ID} className="bg-white rounded-2xl border border-stone-200 shadow-sm p-6 scroll-mt-6">
                    <h2 className="text-lg font-semibold text-stone-900 mb-4">Logs</h2>
                    <JobLogs jobId={jobId} pollingEnabled={pollingEnabled} />
                </div>
            </div>
        </div>
    );
}
