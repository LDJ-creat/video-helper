"use client";

import { useRef, useState, useEffect } from "react";
import { useParams } from "next/navigation";
import { useLatestResult } from "@/lib/api/resultQueries";
import { ResultLayout } from "@/components/layout/ResultLayout";
import { VideoPlayer, type VideoPlayerRef } from "@/components/features/VideoPlayer";
import { ChapterList } from "@/components/features/ChapterList";
import { KeyframeGrid } from "@/components/features/KeyframeGrid";
import { HighlightList } from "@/components/features/HighlightList";
import { MindmapViewer } from "@/components/features/MindmapViewer";
import { FloatingPlayer } from "@/components/features/FloatingPlayer";
import { endpoints } from "@/lib/api/endpoints";

export default function ResultPage() {
    const params = useParams();
    const projectId = params?.projectId as string;

    // Data fetching
    const { data: result, isLoading, error } = useLatestResult(projectId);

    // Refs
    const videoPlayerRef = useRef<VideoPlayerRef>(null);
    const playerContainerRef = useRef<HTMLDivElement>(null);
    const [videoElement, setVideoElement] = useState<HTMLVideoElement | null>(null);

    // State
    const [isFloatingVisible, setIsFloatingVisible] = useState(false);
    const [currentTimeMs, setCurrentTimeMs] = useState(0);
    const [activeTab, setActiveTab] = useState<"mindmap" | "keyframes" | "highlights">("mindmap");

    // Intersection Observer for floating player
    useEffect(() => {
        if (!playerContainerRef.current) return;

        const observer = new IntersectionObserver(
            ([entry]) => {
                setIsFloatingVisible(!entry.isIntersecting);
            },
            { threshold: 0.1 }
        );

        observer.observe(playerContainerRef.current);
        return () => observer.disconnect();
    }, []);

    // Get video element reference
    useEffect(() => {
        const video = videoPlayerRef.current?.getVideoElement();
        if (video) {
            setVideoElement(video);
        }
    }, [result]);

    // Handle seek (章节/关键帧跳转)
    const handleSeek = (timeMs: number) => {
        videoPlayerRef.current?.seekTo(timeMs);
        videoPlayerRef.current?.play();
    };

    // Handle expand (回到顶部)
    const handleExpand = () => {
        playerContainerRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    };

    // Handle close floating player
    const handleCloseFloating = () => {
        setIsFloatingVisible(false);
    };

    // Loading state
    if (isLoading) {
        return (
            <ResultLayout>
                <div className="flex items-center justify-center min-h-[60vh]">
                    <div className="text-center">
                        <div className="inline-block w-12 h-12 border-4 border-stone-300 border-t-orange-600 rounded-full animate-spin mb-4" />
                        <p className="text-stone-600">加载中...</p>
                    </div>
                </div>
            </ResultLayout>
        );
    }

    // Error state
    if (error) {
        return (
            <ResultLayout>
                <div className="flex items-center justify-center min-h-[60vh]">
                    <div className="text-center max-w-md">
                        <svg className="w-16 h-16 text-rose-500 mx-auto mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                        </svg>
                        <h2 className="text-xl font-semibold text-stone-900 mb-2">加载失败</h2>
                        <p className="text-stone-600 mb-4">
                            {error instanceof Error ? error.message : "未找到分析结果"}
                        </p>
                        <button
                            onClick={() => window.location.reload()}
                            className="px-4 py-2 bg-stone-800 text-white rounded-lg hover:bg-stone-900 transition-colors"
                        >
                            重试
                        </button>
                    </div>
                </div>
            </ResultLayout>
        );
    }

    if (!result) {
        return (
            <ResultLayout>
                <div className="flex items-center justify-center min-h-[60vh]">
                    <p className="text-stone-600">暂无分析结果</p>
                </div>
            </ResultLayout>
        );
    }

    // 获取视频资源 URL（假设是第一个 assetRef）
    const videoAsset = result.assetRefs.find((ref) => ref.kind !== "screenshot");
    const videoSrc = videoAsset ? endpoints.assetContent(videoAsset.assetId) : "";

    // 收集所有章节的关键帧（用于 Keyframes Tab）
    const allKeyframes = result.chapters.flatMap((ch) => ch.keyframes);

    return (
        <ResultLayout>
            {/* Tri-Pane Grid */}
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
                {/* Left Pane: 视频 + 导图/关键帧 (7 cols) */}
                <div className="lg:col-span-7 space-y-6">
                    {/* Video Player Container */}
                    <div ref={playerContainerRef}>
                        <VideoPlayer
                            ref={videoPlayerRef}
                            src={videoSrc}
                            onTimeUpdate={setCurrentTimeMs}
                        />
                    </div>

                    {/* Tabs for Mindmap / Keyframes / Highlights */}
                    <div className="bg-white rounded-xl border border-stone-200 overflow-hidden">
                        {/* Tab Headers */}
                        <div className="flex border-b border-stone-200">
                            <button
                                onClick={() => setActiveTab("mindmap")}
                                className={`flex-1 px-4 py-3 text-sm font-medium transition-colors ${activeTab === "mindmap"
                                        ? "bg-orange-50 text-orange-700 border-b-2 border-orange-600"
                                        : "text-stone-600 hover:bg-stone-50"
                                    }`}
                            >
                                思维导图
                            </button>
                            <button
                                onClick={() => setActiveTab("keyframes")}
                                className={`flex-1 px-4 py-3 text-sm font-medium transition-colors ${activeTab === "keyframes"
                                        ? "bg-orange-50 text-orange-700 border-b-2 border-orange-600"
                                        : "text-stone-600 hover:bg-stone-50"
                                    }`}
                            >
                                关键帧 ({allKeyframes.length})
                            </button>
                            <button
                                onClick={() => setActiveTab("highlights")}
                                className={`flex-1 px-4 py-3 text-sm font-medium transition-colors ${activeTab === "highlights"
                                        ? "bg-orange-50 text-orange-700 border-b-2 border-orange-600"
                                        : "text-stone-600 hover:bg-stone-50"
                                    }`}
                            >
                                重点 ({result.highlights.length})
                            </button>
                        </div>

                        {/* Tab Content */}
                        <div className="p-6">
                            {activeTab === "mindmap" && <MindmapViewer mindmap={result.mindmap} />}
                            {activeTab === "keyframes" && (
                                <KeyframeGrid keyframes={allKeyframes} onKeyframeClick={handleSeek} />
                            )}
                            {activeTab === "highlights" && (
                                <HighlightList highlights={result.highlights} onHighlightClick={handleSeek} />
                            )}
                        </div>
                    </div>
                </div>

                {/* Right Pane: 章节 + 笔记 (5 cols) */}
                <div className="lg:col-span-5 space-y-6">
                    {/* Chapters List */}
                    <div className="bg-white rounded-xl border border-stone-200 p-6">
                        <h2 className="text-lg font-semibold text-stone-800 mb-4">章节</h2>
                        <ChapterList
                            chapters={result.chapters}
                            onChapterClick={handleSeek}
                            currentTimeMs={currentTimeMs}
                        />
                    </div>

                    {/* Note (暂时占位) */}
                    <div className="bg-white rounded-xl border border-stone-200 p-6">
                        <h2 className="text-lg font-semibold text-stone-800 mb-4">笔记</h2>
                        <p className="text-sm text-stone-500">
                            笔记编辑功能将在后续 Story 中实现
                        </p>
                    </div>
                </div>
            </div>

            {/* Floating Player */}
            <FloatingPlayer
                videoElement={videoElement}
                isVisible={isFloatingVisible}
                onExpand={handleExpand}
                onClose={handleCloseFloating}
            />
        </ResultLayout>
    );
}
