"use client";

import { useJobQuery } from "@/lib/api/jobQueries";
import { useJobSse } from "@/lib/sse/useJobSse";
import { JobProgress } from "@/components/JobProgress";
import { JobError } from "@/components/JobError";
import { JobLogs } from "@/components/JobLogs";

export function JobPageClient({ jobId }: { jobId: string }) {
    const { data: job, isLoading, error } = useJobQuery(jobId);
    const { connectionMode, isConnected } = useJobSse({
        jobId,
        enabled: true,
    });

    if (isLoading) {
        return (
            <div className="min-h-screen flex items-center justify-center">
                <div className="text-gray-500">加载中...</div>
            </div>
        );
    }

    if (error) {
        return (
            <div className="min-h-screen flex items-center justify-center">
                <div className="text-red-600">加载失败：{(error as Error).message}</div>
            </div>
        );
    }

    if (!job) {
        return (
            <div className="min-h-screen flex items-center justify-center">
                <div className="text-gray-500">Job 不存在</div>
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-gray-50 py-8">
            <div className="max-w-4xl mx-auto px-4 space-y-6">
                <div className="bg-white rounded-lg shadow p-6">
                    <div className="flex items-center justify-between mb-4">
                        <h1 className="text-2xl font-bold text-gray-900">任务详情</h1>
                        <div className="text-sm text-gray-500">
                            连接: {isConnected ? "✅" : "❌"} {connectionMode}
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
                        <div>类型: {job.type}</div>
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
                    <JobLogs jobId={jobId} />
                </div>
            </div>
        </div>
    );
}
