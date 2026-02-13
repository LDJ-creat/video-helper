"use client";

import { useRef, useState, useEffect, useCallback } from "react";
import { useParams, useSearchParams, useRouter } from "next/navigation";
import { useLatestResult } from "@/lib/api/resultQueries";
import { useJobQueryWithOptions, useJobLogsQueryWithOptions } from "@/lib/api/jobQueries";
import { useJobSse } from "@/lib/sse/useJobSse";
import { ResultLayout } from "@/components/layout/ResultLayout";
import { VideoPlayer, type VideoPlayerRef } from "@/components/features/VideoPlayer";
import { MindmapEditor } from "@/components/features/MindmapEditor";
import { FloatingPlayer } from "@/components/features/FloatingPlayer";
import { NoteEditor, NoteEditorRef } from "@/components/features/NoteEditor";
import { endpoints } from "@/lib/api/endpoints";
import { useQueryClient } from "@tanstack/react-query";
import { queryKeys } from "@/lib/api/queryKeys";

function JobProgress({ jobId, projectId }: { jobId: string; projectId: string }) {
    const router = useRouter();
    const queryClient = useQueryClient();

    const { connectionMode } = useJobSse({
        jobId,
        onEvent: (event) => {
            if (event.type === "state" && event.stage === "assemble_result" && event.message === "status=succeeded") {
                queryClient.invalidateQueries({ queryKey: queryKeys.result(projectId) });
            }
        }
    });

    const pollingEnabled = connectionMode !== "sse";
    const { data: job } = useJobQueryWithOptions(jobId, { pollingEnabled });
    const { data: logs } = useJobLogsQueryWithOptions(jobId, undefined, { pollingEnabled });

    // Auto-refresh result when job succeeds via polling (backup to SSE)
    useEffect(() => {
        if (job?.status === "succeeded") {
            queryClient.invalidateQueries({ queryKey: queryKeys.result(projectId) });
        }
    }, [job?.status, projectId, queryClient]);

    const progressPercent = Math.round((job?.progress || 0) * 100);
    const statusMessage = job?.stage ? `正在进行: ${job.stage}...` : "准备中...";
    const latestLog = logs?.items?.[logs.items.length - 1]?.message;

    return (
        <ResultLayout>
            <div className="flex flex-col items-center justify-center min-h-[60vh] max-w-2xl mx-auto p-6">
                <div className="w-full bg-stone-100 rounded-full h-4 mb-4 overflow-hidden">
                    <div
                        className="bg-orange-500 h-full transition-all duration-500 ease-out"
                        style={{ width: `${progressPercent}%` }}
                    />
                </div>

                <h2 className="text-xl font-semibold text-stone-900 mb-2">
                    {progressPercent}% - {statusMessage}
                </h2>

                {latestLog && (
                    <p className="text-stone-500 text-sm font-mono bg-stone-50 px-3 py-1 rounded border border-stone-200">
                        {latestLog}
                    </p>
                )}

                {job?.error && (
                    <div className="mt-6 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700 max-w-full">
                        <h3 className="font-bold mb-1">任务失败</h3>
                        <p className="text-sm font-mono break-all">
                            {JSON.stringify(job.error, null, 2)}
                        </p>
                        <button
                            onClick={() => router.push(`/projects`)}
                            className="mt-4 px-4 py-2 bg-white border border-red-300 rounded shadow-sm hover:bg-red-50 text-sm font-medium"
                        >
                            返回项目列表
                        </button>
                    </div>
                )}
            </div>
        </ResultLayout>
    );
}

export default function ResultPage() {
    const params = useParams();
    const searchParams = useSearchParams();
    const projectId = params?.projectId as string;
    const jobId = searchParams?.get("jobId");

    // Data fetching
    const { data: result, isLoading, error } = useLatestResult(projectId);

    // Refs
    const videoPlayerRef = useRef<VideoPlayerRef>(null);
    const noteEditorRef = useRef<NoteEditorRef>(null);
    const playerContainerRef = useRef<HTMLDivElement>(null);
    const [videoElement, setVideoElement] = useState<HTMLVideoElement | null>(null);

    // State
    const [isFloatingVisible, setIsFloatingVisible] = useState(false);
    const [isDismissed, setIsDismissed] = useState(false); // Track if user dismissed the floating player

    // Callback ref for player container - sets up observer when element is attached
    const playerContainerCallbackRef = useCallback((element: HTMLDivElement | null) => {
        // Store ref for other uses
        (playerContainerRef as React.MutableRefObject<HTMLDivElement | null>).current = element;

        if (!element) return;

        const observer = new IntersectionObserver(
            (entries) => {
                const entry = entries[0];
                // Show floating player when the main player is NOT intersecting (scrolled out of view)
                if (!entry.isIntersecting && entry.boundingClientRect.top < 0 && !isDismissed) {
                    setIsFloatingVisible(true);
                } else if (entry.isIntersecting) {
                    setIsFloatingVisible(false);
                }
            },
            {
                threshold: 0,
                rootMargin: '0px'
            }
        );

        observer.observe(element);

        // Cleanup when component unmounts or element changes
        return () => observer.disconnect();
    }, [isDismissed]); // Re-run when isDismissed changes

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
        setIsDismissed(true); // Mark as dismissed for the session
    };

    // Mindmap Navigation
    const handleMindmapNavigation = (targetBlockId: string, targetHighlightId?: string) => {
        if (targetHighlightId) {
            noteEditorRef.current?.scrollToHighlight(targetHighlightId);
        } else {
            noteEditorRef.current?.scrollToBlock(targetBlockId);
        }
    };

    // Priority: Result > Job Progress (if no result) > Loading > Error

    // 1. If we have a result, show the dashboard (Happy path)
    if (result) {
        // 获取视频资源 URL
        const videoAsset = result.assetRefs?.find((ref) => ref.kind === "video");
        const videoSrc = videoAsset ? endpoints.assetContent(videoAsset.assetId) : undefined;

        return (
            <ResultLayout>

                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 min-h-screen pb-20">
                    {/* Left Pane: Mindmap - Sticky on Desktop */}
                    <div className="lg:sticky lg:top-6 lg:h-[calc(100vh-3rem)] bg-white rounded-xl border border-stone-200 overflow-hidden flex flex-col shadow-sm">
                        <div className="p-4 border-b border-stone-200 bg-stone-50/50">
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

                    {/* Right Pane: Video + Note - Natural Scroll */}
                    <div className="flex flex-col space-y-6">
                        {/* Video Player Container */}
                        <div
                            ref={playerContainerCallbackRef}
                            className={`shrink-0 bg-black rounded-xl overflow-hidden shadow-lg border border-stone-800 transition-opacity duration-300 ${isFloatingVisible ? 'opacity-20 pointer-events-none grayscale' : 'opacity-100'}`}
                        >
                            <VideoPlayer
                                ref={videoPlayerRef}
                                src={videoSrc}
                            />
                        </div>

                        {/* Note Editor */}
                        <div className="bg-white rounded-xl border border-stone-200 shadow-sm flex-1 flex flex-col">
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

    // 2. If no result but we have a valid jobId, show progress
    if (jobId) {
        return <JobProgress jobId={jobId} projectId={projectId} />;
    }

    // 3. Loading (only if fetching result and no jobId provided to fallback to progress)
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

    // 4. Error state
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

    // 5. Fallback for no result and no job
    return (
        <ResultLayout>
            <div className="flex items-center justify-center min-h-[60vh]">
                <p className="text-stone-600">暂无分析结果</p>
            </div>
        </ResultLayout>
    );
}
