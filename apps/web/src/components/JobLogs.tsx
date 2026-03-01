"use client";

import { useJobLogsQueryWithOptions } from "@/lib/api/jobQueries";
import type { LogEntry } from "@/lib/contracts/types";
import { useEffect, useRef, useState } from "react";

interface JobLogsProps {
    jobId: string;
    pollingEnabled?: boolean;
}

const LOG_LEVEL_COLORS: Record<LogEntry["level"], string> = {
    INFO: "text-gray-700",
    WARN: "text-yellow-600",
    ERROR: "text-red-600",
    DEBUG: "text-blue-600",
};

export function JobLogs({ jobId, pollingEnabled = true }: JobLogsProps) {
    const [cursor, setCursor] = useState<string | undefined>(undefined);
    const { data, isLoading, error } = useJobLogsQueryWithOptions(jobId, cursor, { pollingEnabled });
    const logsEndRef = useRef<HTMLDivElement>(null);
    const [autoScroll, setAutoScroll] = useState(true);

    // Auto-scroll to bottom when new logs arrive
    useEffect(() => {
        if (autoScroll && logsEndRef.current) {
            logsEndRef.current.scrollIntoView({ behavior: "smooth" });
        }
    }, [data, autoScroll]);

    if (isLoading) {
        return <div className="text-sm text-gray-500">加载日志中...</div>;
    }

    if (error) {
        return (
            <div className="text-sm text-red-600">
                加载日志失败：{(error as Error).message}
            </div>
        );
    }

    const logs = data?.items ?? [];

    return (
        <div className="space-y-2">
            <div className="flex items-center justify-between">
                <h3 className="text-sm font-medium text-gray-900">任务日志</h3>
                <label className="flex items-center gap-2 text-sm text-gray-600">
                    <input
                        type="checkbox"
                        checked={autoScroll}
                        onChange={(e) => setAutoScroll(e.target.checked)}
                    />
                    自动追尾
                </label>
            </div>

            <div className="bg-gray-50 rounded border border-gray-200 p-3 max-h-96 overflow-y-auto font-mono text-xs">
                {logs.length === 0 ? (
                    <div className="text-gray-500">暂无日志</div>
                ) : (
                    <>
                        {logs.map((log, idx) => (
                            <div key={idx} className="flex gap-2 py-0.5">
                                <span className="text-gray-400 shrink-0">
                                    {new Date(log.tsMs).toLocaleTimeString()}
                                </span>
                                <span className={`shrink-0 ${LOG_LEVEL_COLORS[log.level]}`}>
                                    [{log.level}]
                                </span>
                                {log.stage && (
                                    <span className="text-purple-600 shrink-0">
                                        [{log.stage}]
                                    </span>
                                )}
                                <span className="text-gray-800">{log.message}</span>
                            </div>
                        ))}
                        <div ref={logsEndRef} />
                    </>
                )}
            </div>

            {data?.nextCursor && (
                <button
                    onClick={() => setCursor(data.nextCursor!)}
                    className="text-sm text-blue-600 hover:text-blue-700"
                >
                    加载更多
                </button>
            )}
        </div>
    );
}
