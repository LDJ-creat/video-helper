"use client";

import { useEffect, useMemo, useState } from "react";

function formatBytes(bytes: number): string {
    if (!Number.isFinite(bytes) || bytes <= 0) return "0 B";
    const units = ["B", "KB", "MB", "GB"] as const;
    let value = bytes;
    let unitIndex = 0;
    while (value >= 1024 && unitIndex < units.length - 1) {
        value /= 1024;
        unitIndex += 1;
    }
    const digits = unitIndex === 0 ? 0 : unitIndex === 1 ? 0 : 1;
    return `${value.toFixed(digits)} ${units[unitIndex]}`;
}

export function UpdateBanner() {
    const isElectron = typeof window !== "undefined" && Boolean(window.electronAPI?.isElectron);

    const [state, setState] = useState<UpdateState | null>(null);
    const [dismissed, setDismissed] = useState(false);
    const [installing, setInstalling] = useState(false);

    const visible = useMemo(() => {
        if (!isElectron || dismissed || !state) return false;
        return state.status === "available" || state.status === "downloading" || state.status === "downloaded" || state.status === "error";
    }, [dismissed, isElectron, state]);

    useEffect(() => {
        if (!isElectron) return;

        let cancelled = false;
        const cleanupFns: Array<() => void> = [];

        // Initialize from a snapshot (covers cases where events fire before the UI mounts).
        window.electronAPI?.getUpdateState?.()
            .then((s) => {
                if (cancelled) return;
                setState(s);
            })
            .catch(() => {
                // ignore
            });

        const unsubAvailable = window.electronAPI?.onUpdateAvailable?.((version) => {
            setState({ status: "available", version });
        });
        if (typeof unsubAvailable === "function") cleanupFns.push(unsubAvailable);

        const unsubProgress = window.electronAPI?.onUpdateProgress?.((progress) => {
            setState((prev) => ({
                status: "downloading",
                version: prev?.version,
                progress,
            }));
        });
        if (typeof unsubProgress === "function") cleanupFns.push(unsubProgress);

        const unsubDownloaded = window.electronAPI?.onUpdateDownloaded?.((version) => {
            setState({ status: "downloaded", version });
        });
        if (typeof unsubDownloaded === "function") cleanupFns.push(unsubDownloaded);

        const unsubError = window.electronAPI?.onUpdateError?.((message) => {
            setState((prev) => ({
                status: "error",
                version: prev?.version,
                error: message,
            }));
        });
        if (typeof unsubError === "function") cleanupFns.push(unsubError);

        return () => {
            cancelled = true;
            for (const fn of cleanupFns) {
                try {
                    fn();
                } catch {
                    // ignore
                }
            }
        };
    }, [isElectron]);

    if (!visible) return null;

    const s = state as UpdateState;

    const version = s.version;

    const title =
        s.status === "downloaded"
            ? "更新已下载"
            : s.status === "error"
                ? "更新失败"
                : "正在更新";

    const message =
        s.status === "available"
            ? `检测到新版本 ${version ?? ""}，正在开始下载...`
            : s.status === "downloading"
                ? (() => {
                    const p = s.progress;
                    const percent = p ? `${p.percent.toFixed(1)}%` : "下载中";
                    const detail = p ? `（${formatBytes(p.transferred)} / ${formatBytes(p.total)}）` : "";
                    const speed = p?.bytesPerSecond ? `，${formatBytes(p.bytesPerSecond)}/s` : "";
                    return `正在下载新版本 ${version ?? ""}：${percent}${detail}${speed}`;
                })()
                : s.status === "downloaded"
                    ? `新版本 ${version ?? ""} 已准备就绪，可立即重启安装。`
                    : `更新出错：${s.error ?? "未知错误"}`;

    const variantClass =
        s.status === "error"
            ? "border-red-200 bg-red-50 text-red-900 dark:border-red-900 dark:bg-red-950 dark:text-red-100"
            : s.status === "downloaded"
                ? "border-green-200 bg-green-50 text-green-900 dark:border-green-900 dark:bg-green-950 dark:text-green-100"
                : "border-stone-200 bg-white text-stone-900 dark:border-stone-800 dark:bg-stone-900 dark:text-stone-100";

    const subTextClass =
        s.status === "error"
            ? "text-red-700 dark:text-red-300"
            : s.status === "downloaded"
                ? "text-green-700 dark:text-green-300"
                : "text-stone-600 dark:text-stone-300";

    return (
        <div className={`rounded-lg border p-4 ${variantClass}`}>
            <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                    <p className="font-medium">{title}</p>
                    <p className={`mt-1 text-sm ${subTextClass}`}>{message}</p>
                </div>

                <div className="flex shrink-0 items-center gap-2">
                    {s.status === "downloaded" && (
                        <button
                            onClick={async () => {
                                try {
                                    setInstalling(true);
                                    await window.electronAPI?.installUpdate();
                                } finally {
                                    setInstalling(false);
                                }
                            }}
                            disabled={installing}
                            className="rounded-md bg-stone-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-stone-800 disabled:opacity-60 dark:bg-stone-100 dark:text-stone-900 dark:hover:bg-stone-200"
                        >
                            {installing ? "正在重启..." : "立即安装"}
                        </button>
                    )}

                    <button
                        onClick={() => setDismissed(true)}
                        className="rounded p-1 text-stone-500 hover:bg-stone-100 dark:text-stone-400 dark:hover:bg-stone-800"
                        aria-label="关闭"
                    >
                        <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                        </svg>
                    </button>
                </div>
            </div>
        </div>
    );
}
