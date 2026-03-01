"use client";

import { useJobQueryWithOptions } from "@/lib/api/jobQueries";
import { useJobSse } from "@/lib/sse/useJobSse";
import { JobProgress } from "@/components/JobProgress";
import { JobError } from "@/components/JobError";
import { JobLogs } from "@/components/JobLogs";
import { useTranslations } from "next-intl";

export function JobPageClient({ jobId }: { jobId: string }) {
    const t = useTranslations("Job");
    const tCommon = useTranslations("Results");

    const { connectionMode, isConnected } = useJobSse({
        jobId,
        enabled: true,
    });

    const pollingEnabled = connectionMode !== "sse";
    const { data: job, isLoading, error } = useJobQueryWithOptions(jobId, { pollingEnabled });

    if (isLoading) {
        return (
            <div className="min-h-screen flex items-center justify-center">
                <div className="text-gray-500">{tCommon("loading")}</div>
            </div>
        );
    }

    if (error) {
        return (
            <div className="min-h-screen flex items-center justify-center">
                <div className="text-red-600">{tCommon("loadFailed")}：{(error as Error).message}</div>
            </div>
        );
    }

    if (!job) {
        return (
            <div className="min-h-screen flex items-center justify-center">
                <div className="text-gray-500">{t("notFound")}</div>
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-gray-50 py-8">
            <div className="max-w-4xl mx-auto px-4 space-y-6">
                <div className="bg-white rounded-lg shadow p-6">
                    <div className="flex items-center justify-between mb-4">
                        <h1 className="text-2xl font-bold text-gray-900">{t("title")}</h1>
                        <div className="text-sm text-gray-500">
                            {t("connection")}: {isConnected ? "✅" : "❌"} {connectionMode}
                        </div>
                    </div>

                    <div className="text-sm text-gray-600 space-y-1">
                        <div>
                            Job ID:{" "}
                            <code className="bg-gray-100 px-2 py-1 rounded">{job.jobId}</code>
                        </div>
                        <div>
                            Project ID:{" "}
                            <code className="bg-gray-100 px-2 py-1 rounded">
                                {job.projectId}
                            </code>
                        </div>
                        <div>{t("type")}: {job.type}</div>
                    </div>
                </div>

                <div className="bg-white rounded-lg shadow p-6">
                    <JobProgress job={job} />
                </div>

                {job.status === "failed" && job.error && (
                    <div className="bg-white rounded-lg shadow p-6">
                        <JobError job={job} />
                    </div>
                )}

                <div className="bg-white rounded-lg shadow p-6">
                    <JobLogs jobId={jobId} pollingEnabled={pollingEnabled} />
                </div>
            </div>
        </div>
    );
}
