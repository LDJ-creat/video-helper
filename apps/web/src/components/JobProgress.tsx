"use client";

import type { Job, JobStatus } from "@/lib/contracts/types";
import { getStageDisplay } from "@/lib/constants/stageMapping";

interface JobProgressProps {
    job: Job;
}

const STATUS_COLORS: Record<JobStatus, string> = {
    queued: "bg-gray-200 text-gray-700",
    running: "bg-blue-500 text-white",
    blocked: "bg-gray-200 text-gray-700",
    succeeded: "bg-green-500 text-white",
    failed: "bg-red-500 text-white",
    canceled: "bg-gray-500 text-white",
};

const STATUS_TEXT: Record<JobStatus, string> = {
    queued: "队列中",
    running: "运行中",
    blocked: "等待外部服务完成分析",
    succeeded: "成功",
    failed: "失败",
    canceled: "已取消",
};

export function JobProgress({ job }: JobProgressProps) {
    const progressPercent = (job.progress ?? 0) * 100;

    return (
        <div className="space-y-4">
            {/* Status Badge */}
            <div className="flex items-center gap-3">
                <span
                    className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-medium ${STATUS_COLORS[job.status]
                        }`}
                >
                    {STATUS_TEXT[job.status]}
                </span>
                {job.stage && (
                    <span className="text-sm text-gray-600">
                        {getStageDisplay(job.stage)}
                    </span>
                )}
            </div>

            {/* Progress Bar */}
            {(job.status === "running" || job.status === "queued") && (
                <div>
                    <div className="flex justify-between text-sm text-gray-600 mb-2">
                        <span>进度</span>
                        <span>{progressPercent.toFixed(0)}%</span>
                    </div>
                    <div className="w-full bg-gray-200 rounded-full h-2.5">
                        <div
                            className="bg-blue-600 h-2.5 rounded-full transition-all duration-300"
                            style={{ width: `${progressPercent}%` }}
                        />
                    </div>
                </div>
            )}
        </div>
    );
}
