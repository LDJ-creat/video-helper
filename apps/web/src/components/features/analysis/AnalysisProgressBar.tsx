"use client";

import { getPublicStageDisplay } from "@/lib/constants/stageMapping";

export function AnalysisProgressBar({
    percent,
    stageLabel,
    animated = true,
}: {
    percent: number;
    stageLabel: string;
    animated?: boolean;
}) {
    const clamped = Math.max(0, Math.min(100, percent));

    return (
        <div className="w-full space-y-3">
            <div className="flex items-end justify-between gap-3">
                <p className="text-sm text-stone-600">{stageLabel}</p>
                <span className="text-2xl font-bold tabular-nums text-stone-900">{clamped}%</span>
            </div>
            <div
                className={`rounded-full p-[3px] ${animated ? "animated-border-glow" : "bg-stone-200"}`}
                role="progressbar"
                aria-valuenow={clamped}
                aria-valuemin={0}
                aria-valuemax={100}
                aria-label={stageLabel}
            >
                <div className="h-3 rounded-full bg-stone-100 overflow-hidden">
                    <div
                        className="h-full bg-orange-500 rounded-full transition-all duration-500 ease-out"
                        style={{ width: `${clamped}%` }}
                    />
                </div>
            </div>
        </div>
    );
}

export function formatRunningStageLabel(stage: string | undefined, processingTemplate: (values: { stage: string }) => string): string {
    const display = getPublicStageDisplay(stage);
    return processingTemplate({ stage: display });
}
