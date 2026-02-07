"use client";

import { useRef, useState, useEffect } from "react";
import { useParams } from "next/navigation";
import { useLatestResult } from "@/lib/api/resultQueries";
import { ResultLayout } from "@/components/layout/ResultLayout";
import { VideoPlayer, type VideoPlayerRef } from "@/components/features/VideoPlayer";
import { MindmapEditor } from "@/components/features/MindmapEditor";
import { FloatingPlayer } from "@/components/features/FloatingPlayer";
import { NoteEditor, NoteEditorRef } from "@/components/features/NoteEditor";
import { endpoints } from "@/lib/api/endpoints";

export default function ResultPage() {
    const params = useParams();
    const projectId = params?.projectId as string;

    // Data fetching
    const { data: result, isLoading, error } = useLatestResult(projectId);

    // Refs
    const videoPlayerRef = useRef<VideoPlayerRef>(null);
    const noteEditorRef = useRef<NoteEditorRef>(null);
    const playerContainerRef = useRef<HTMLDivElement>(null);
    const [videoElement, setVideoElement] = useState<HTMLVideoElement | null>(null);

    // State
    const [isFloatingVisible, setIsFloatingVisible] = useState(false);

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

    // Handle seek
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

    // Mindmap Navigation
    const handleMindmapNavigation = (targetBlockId: string) => {
        noteEditorRef.current?.scrollToBlock(targetBlockId);
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
                        <h2 className="text-xl font-semibold text-stone-900 mb-2">加载失败</h2>
                        <p className="text-stone-600 mb-4">
                            {error instanceof Error ? error.message : "未找到分析结果"}
                        </p>
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

    // 获取视频资源 URL
    const videoAsset = result.assetRefs?.find((ref) => ref.kind === "video");
    const videoSrc = videoAsset ? endpoints.assetContent(videoAsset.assetId) : undefined;

    return (
        <ResultLayout>
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 h-[calc(100vh-100px)]">
                {/* Left Pane: Mindmap */}
                <div className="bg-white rounded-xl border border-stone-200 overflow-hidden flex flex-col">
                    <div className="p-4 border-b border-stone-200">
                        <h3 className="font-semibold text-stone-700">思维导图</h3>
                    </div>
                    <div className="flex-1 relative">
                        <MindmapEditor
                            projectId={projectId}
                            resultId={result.resultId}
                            initialMindmap={result.mindmap}
                            onNodeNavigation={handleMindmapNavigation}
                            onSaveSuccess={() => console.log("Mindmap saved successfully")}
                            onSaveError={(error) => console.error("Failed to save mindmap:", error instanceof Error ? error.message : error)}
                        />
                    </div>
                </div>

                {/* Right Pane: Video + Note */}
                <div className="flex flex-col space-y-6 h-full overflow-y-auto pr-2">
                    {/* Video Player Container */}
                    <div ref={playerContainerRef} className="shrink-0 bg-black rounded-xl overflow-hidden shadow-sm">
                        <VideoPlayer
                            ref={videoPlayerRef}
                            src={videoSrc}
                        />
                    </div>

                    {/* Note Editor */}
                    <div className="bg-white rounded-xl border border-stone-200 overflow-hidden flex-1 flex flex-col">
                        <NoteEditor
                            ref={noteEditorRef}
                            projectId={projectId}
                            resultId={result.resultId}
                            contentBlocks={result.contentBlocks || []}
                            onBlockNavigation={handleSeek}
                            onSaveSuccess={() => console.log("ContentBlocks saved successfully")}
                            onSaveError={(error) => console.error("Failed to save content blocks:", error instanceof Error ? error.message : error)}
                        />
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

