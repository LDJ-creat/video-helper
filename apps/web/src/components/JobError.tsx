"use client";

import type { Job } from "@/lib/contracts/types";
import { getErrorSuggestion } from "@/lib/constants/errorMessages";
import { useRetryJobMutation } from "@/lib/api/jobQueries";

interface JobErrorProps {
    job: Job;
}

export function JobError({ job }: JobErrorProps) {
    const retryMutation = useRetryJobMutation(job.jobId);

    if (!job.error) return null;

    const suggestion = getErrorSuggestion(job.error.code);

    return (
        <div className="border-l-4 border-red-500 bg-red-50 p-4 rounded">
            <div className="flex items-start">
                <div className="flex-1">
                    <h3 className="text-sm font-medium text-red-800">任务失败</h3>
                    <div className="mt-2 text-sm text-red-700">
                        <p className="font-medium">{job.error.message}</p>
                        <p className="mt-1 text-red-600">{suggestion}</p>
                    </div>
                    {job.error.details ? (
                        <details className="mt-2 text-xs text-red-600">
                            <summary className="cursor-pointer">查看详情</summary>
                            <pre className="mt-1 overflow-auto">
                                {JSON.stringify(job.error.details, null, 2)}
                            </pre>
                        </details>
                    ) : null}
                </div>
                <div className="ml-4">
                    <button
                        onClick={() => retryMutation.mutate()}
                        disabled={retryMutation.isPending}
                        className="px-3 py-1 bg-red-600 text-white text-sm rounded hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                        {retryMutation.isPending ? "重试中..." : "重试"}
                    </button>
                </div>
            </div>
        </div>
    );
}
