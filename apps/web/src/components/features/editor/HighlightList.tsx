"use client";

import type { Highlight } from "@/lib/contracts/resultTypes";
import { formatTime, msToSeconds } from "@/lib/utils/timeUtils";

type HighlightListProps = {
    highlights: Highlight[];
    onHighlightClick?: (timeMs: number) => void;
    isLoading?: boolean;
};

export function HighlightList({ highlights, onHighlightClick, isLoading = false }: HighlightListProps) {
    if (isLoading) {
        return (
            <div className="space-y-3">
                {[1, 2, 3, 4].map((i) => (
                    <div key={i} className="bg-stone-100 rounded-lg h-16 animate-pulse" />
                ))}
            </div>
        );
    }

    if (highlights.length === 0) {
        return (
            <div className="text-center py-8 text-stone-500">
                暂无重点内容
            </div>
        );
    }

    return (
        <div className="space-y-2">
            {highlights.map((highlight) => {
                const hasTimeMs = typeof highlight.startMs === "number";
                const Component = hasTimeMs && onHighlightClick ? "button" : "div";

                return (
                    <Component
                        key={highlight.highlightId}
                        onClick={hasTimeMs && onHighlightClick ? () => onHighlightClick(highlight.startMs) : undefined}
                        className={`w-full text-left p-4 rounded-xl border border-stone-200 bg-white ${hasTimeMs && onHighlightClick
                            ? "hover:border-orange-200 hover:shadow-md cursor-pointer transition-all duration-200"
                            : ""
                            }`}
                    >
                        <div className="flex items-start gap-3">
                            {/* 重点标记 */}
                            <div className="flex-shrink-0 w-1 h-full bg-orange-400 rounded-full" />

                            <div className="flex-1 min-w-0">
                                {/* 时间戳（如果有） */}
                                {hasTimeMs && (
                                    <div className="text-xs font-mono text-stone-500 mb-1">
                                        {formatTime(msToSeconds(highlight.startMs))}
                                    </div>
                                )}

                                {/* 重点文本 */}
                                <p className="text-base text-stone-800 leading-relaxed">
                                    {highlight.text}
                                </p>
                            </div>
                        </div>
                    </Component>
                );
            })}
        </div>
    );
}
