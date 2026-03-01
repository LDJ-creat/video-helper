"use client";

import { useHealthQuery } from "@/lib/api/healthQueries";
import type { DependencyPayload, HealthCheck } from "@/lib/contracts/healthTypes";
import { useState } from "react";

/**
 * Health Banner Component
 * Displays system health status and dependency warnings
 * - Shows loading state during initial fetch
 * - Displays warnings when dependencies are missing
 * - Provides actionable suggestions for resolving issues
 * - Can be dismissed by user
 */
export function HealthBanner() {
    const { data, isLoading, error } = useHealthQuery();
    const [dismissed, setDismissed] = useState(false);

    // Don't show if dismissed or if healthy and no issues
    if (dismissed || (data?.status === "ok" && !error)) {
        return null;
    }

    // Loading state
    if (isLoading) {
        return (
            <div className="rounded-lg border border-zinc-200 bg-zinc-50 p-4 dark:border-zinc-800 dark:bg-zinc-900">
                <div className="flex items-center gap-3">
                    <div className="h-5 w-5 animate-spin rounded-full border-2 border-zinc-300 border-t-zinc-600 dark:border-zinc-700 dark:border-t-zinc-400" />
                    <p className="text-sm text-zinc-600 dark:text-zinc-400">
                        检查系统依赖...
                    </p>
                </div>
            </div>
        );
    }

    // Network error state
    if (error) {
        return (
            <div className="rounded-lg border border-red-200 bg-red-50 p-4 dark:border-red-900 dark:bg-red-950">
                <div className="flex items-start justify-between gap-3">
                    <div className="flex items-start gap-3">
                        <svg
                            className="mt-0.5 h-5 w-5 shrink-0 text-red-600 dark:text-red-400"
                            fill="none"
                            viewBox="0 0 24 24"
                            stroke="currentColor"
                        >
                            <path
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                strokeWidth={2}
                                d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
                            />
                        </svg>
                        <div>
                            <p className="font-medium text-red-900 dark:text-red-100">
                                无法连接到后端服务
                            </p>
                            <p className="mt-1 text-sm text-red-700 dark:text-red-300">
                                请确认后端服务已启动并可访问
                            </p>
                        </div>
                    </div>
                    <button
                        onClick={() => setDismissed(true)}
                        className="rounded p-1 text-red-600 hover:bg-red-100 dark:text-red-400 dark:hover:bg-red-900"
                        aria-label="关闭"
                    >
                        <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                        </svg>
                    </button>
                </div>
            </div>
        );
    }

    if (!data) return null;

    // Collect issues
    const issues = collectIssues(data);

    // Don't show if no issues
    if (issues.length === 0 && data.status === "ok") {
        return null;
    }

    const variant = data.ready ? "warning" : "error";

    return (
        <div
            className={`rounded-lg border p-4 ${variant === "error"
                ? "border-red-200 bg-red-50 dark:border-red-900 dark:bg-red-950"
                : "border-yellow-200 bg-yellow-50 dark:border-yellow-900 dark:bg-yellow-950"
                }`}
        >
            <div className="flex items-start justify-between gap-3">
                <div className="flex items-start gap-3">
                    <svg
                        className={`mt-0.5 h-5 w-5 shrink-0 ${variant === "error"
                            ? "text-red-600 dark:text-red-400"
                            : "text-yellow-600 dark:text-yellow-400"
                            }`}
                        fill="none"
                        viewBox="0 0 24 24"
                        stroke="currentColor"
                    >
                        <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth={2}
                            d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
                        />
                    </svg>
                    <div>
                        <p
                            className={`font-medium ${variant === "error"
                                ? "text-red-900 dark:text-red-100"
                                : "text-yellow-900 dark:text-yellow-100"
                                }`}
                        >
                            {variant === "error" ? "系统依赖缺失" : "部分功能受限"}
                        </p>
                        <div className="mt-2 space-y-2">
                            {issues.map((issue, index) => (
                                <div
                                    key={index}
                                    className={`text-sm ${variant === "error"
                                        ? "text-red-700 dark:text-red-300"
                                        : "text-yellow-700 dark:text-yellow-300"
                                        }`}
                                >
                                    <p className="font-medium">{issue.name}:</p>
                                    <p className="mt-0.5">{issue.suggestion}</p>
                                    {issue.message && (
                                        <p className="mt-0.5 text-xs opacity-75">{issue.message}</p>
                                    )}
                                </div>
                            ))}
                        </div>
                    </div>
                </div>
                <button
                    onClick={() => setDismissed(true)}
                    className={`rounded p-1 ${variant === "error"
                        ? "text-red-600 hover:bg-red-100 dark:text-red-400 dark:hover:bg-red-900"
                        : "text-yellow-600 hover:bg-yellow-100 dark:text-yellow-400 dark:hover:bg-yellow-900"
                        }`}
                    aria-label="关闭"
                >
                    <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                    </svg>
                </button>
            </div>
        </div>
    );
}

type Issue = {
    name: string;
    suggestion: string;
    message?: string;
};

function collectIssues(health: HealthCheck): Issue[] {
    const issues: Issue[] = [];

    const deps: Array<[string, DependencyPayload | undefined, string]> = [
        ["FFmpeg", health.dependencies?.ffmpeg, "请安装 FFmpeg 以支持视频处理"],
        ["yt-dlp", health.dependencies?.ytDlp, "请安装 yt-dlp 以支持在线视频下载"],
    ];

    for (const [name, dep, suggestion] of deps) {
        if (dep && dep.ok === false) {
            issues.push({
                name,
                suggestion: dep.actions?.[0] || suggestion,
                message: dep.message ?? undefined,
            });
        }
    }

    return issues;
}
