"use client";

import type { Chapter } from "@/lib/contracts/resultTypes";
import { formatTime, msToSeconds, formatDuration } from "@/lib/utils/timeUtils";

type ChapterListProps = {
    chapters: Chapter[];
    onChapterClick: (timeMs: number) => void;
    currentTimeMs?: number;
    isLoading?: boolean;
};

export function ChapterList({ chapters, onChapterClick, currentTimeMs = 0, isLoading = false }: ChapterListProps) {
    // 根据当前时间判断当前章节
    const getCurrentChapterIdx = () => {
        if (!currentTimeMs) return -1;
        return chapters.findIndex(
            (ch) => currentTimeMs >= ch.startMs && currentTimeMs < ch.endMs
        );
    };

    const currentIdx = getCurrentChapterIdx();

    if (isLoading) {
        return (
            <div className="space-y-3">
                {[1, 2, 3].map((i) => (
                    <div key={i} className="bg-stone-100 rounded-lg h-20 animate-pulse" />
                ))}
            </div>
        );
    }

    if (chapters.length === 0) {
        return (
            <div className="text-center py-8 text-stone-500">
                暂无章节信息
            </div>
        );
    }

    return (
        <div className="space-y-2">
            {chapters.map((chapter, idx) => {
                const isActive = idx === currentIdx;
                return (
                    <button
                        key={chapter.chapterId}
                        onClick={() => onChapterClick(chapter.startMs)}
                        className={`w-full text-left p-4 rounded-xl border transition-all duration-200 ${isActive
                                ? "bg-orange-50 border-orange-200 shadow-sm"
                                : "bg-white border-stone-200 hover:border-stone-300 hover:shadow-md"
                            }`}
                    >
                        <div className="flex items-start justify-between gap-3">
                            <div className="flex-1 min-w-0">
                                <div className="flex items-center gap-2 mb-1">
                                    <span className="text-xs font-mono text-stone-500">
                                        {formatTime(msToSeconds(chapter.startMs))}
                                    </span>
                                    <span className="text-xs text-stone-400">•</span>
                                    <span className="text-xs text-stone-500">
                                        {formatDuration(chapter.startMs, chapter.endMs)}
                                    </span>
                                </div>
                                <h3 className={`text-base font-semibold mb-1 ${isActive ? "text-stone-900" : "text-stone-800"
                                    }`}>
                                    {chapter.title}
                                </h3>
                                {chapter.summary && (
                                    <p className="text-sm text-stone-600 line-clamp-2">
                                        {chapter.summary}
                                    </p>
                                )}
                            </div>

                            {isActive && (
                                <div className="flex-shrink-0">
                                    <div className="w-2 h-2 bg-orange-600 rounded-full animate-pulse" />
                                </div>
                            )}
                        </div>
                    </button>
                );
            })}
        </div>
    );
}
