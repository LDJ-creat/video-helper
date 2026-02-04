"use client";

import type { Keyframe } from "@/lib/contracts/resultTypes";
import { formatTime, msToSeconds } from "@/lib/utils/timeUtils";
import { endpoints } from "@/lib/api/endpoints";
import Image from "next/image";
type KeyframeGridProps = {
    keyframes: Keyframe[];
    onKeyframeClick: (timeMs: number) => void;
    isLoading?: boolean;
};

export function KeyframeGrid({ keyframes, onKeyframeClick, isLoading = false }: KeyframeGridProps) {
    if (isLoading) {
        return (
            <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                {[1, 2, 3, 4, 5, 6].map((i) => (
                    <div key={i} className="bg-stone-100 rounded-lg aspect-video animate-pulse" />
                ))}
            </div>
        );
    }

    if (keyframes.length === 0) {
        return (
            <div className="text-center py-8 text-stone-500">
                暂无关键帧
            </div>
        );
    }

    return (
        <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
            {keyframes.map((keyframe) => (
                <button
                    key={`${keyframe.assetId}-${keyframe.idx}`}
                    onClick={() => onKeyframeClick(keyframe.timeMs)}
                    className="group relative bg-white rounded-lg border border-stone-200 overflow-hidden hover:border-stone-300 hover:shadow-md transition-all duration-200"
                >
                    {/* 关键帧图片 */}
                    <div className="aspect-video bg-stone-100 overflow-hidden">
                        <img
                            src={endpoints.assetContent(keyframe.assetId)}
                            alt={keyframe.caption || "关键帧"}
                            className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-200"
                            loading="lazy"
                        />
                        {/* <Image
                            src={endpoints.assetContent(keyframe.assetId)}
                            alt={keyframe.caption || "关键帧"}
                            fill
                            className="object-cover group-hover:scale-105 transition-transform duration-200"
                            loading="lazy"
                            sizes="(max-width: 768px) 100vw, (max-width: 1200px) 50vw, 33vw"
                        /> */}
                    </div>

                    {/* 时间标签（左上角） */}
                    <div className="absolute top-2 left-2 px-2 py-1 bg-black/70 rounded text-xs font-mono text-white">
                        {formatTime(msToSeconds(keyframe.timeMs))}
                    </div>

                    {/* Caption（底部） */}
                    {keyframe.caption && (
                        <div className="p-2 bg-white">
                            <p className="text-sm text-stone-700 line-clamp-2">
                                {keyframe.caption}
                            </p>
                        </div>
                    )}
                </button>
            ))}
        </div>
    );
}
