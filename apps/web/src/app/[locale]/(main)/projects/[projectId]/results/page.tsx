"use client";

import { useRef, useState, useEffect, useCallback } from "react";
import { useParams, useSearchParams, useRouter } from "next/navigation";
import { useLatestResult } from "@/lib/api/resultQueries";
import { useProjectDetail } from "@/lib/api/projectQueries";
import { useJobQueryWithOptions, useJobLogsQueryWithOptions } from "@/lib/api/jobQueries";
import { useJobSse } from "@/lib/sse/useJobSse";
import { ResultLayout } from "@/components/layout/ResultLayout";
import { VideoPlayer, type VideoPlayerRef } from "@/components/features/player/VideoPlayer";
import { MindmapEditor } from "@/components/features/editor/MindmapEditor";
import { FloatingPlayer } from "@/components/features/player/FloatingPlayer";
import { NoteEditor, NoteEditorRef } from "@/components/features/editor/NoteEditor";
import { endpoints } from "@/lib/api/endpoints";
import { useQueryClient } from "@tanstack/react-query";
import { queryKeys } from "@/lib/api/queryKeys";
import { AIChat } from "@/components/features/editor/AIChat";
import { ExercisesCanvas } from "@/components/features/editor/ExercisesCanvas";
import { fetchQuizSessions } from "@/lib/api/ai";
import { MessageSquare, Layout, BrainCircuit } from "lucide-react";
import { useTranslations } from "next-intl";
import { cancelJob, resumeProjectJob } from "@/lib/api/jobApi";

function JobProgress({ jobId, projectId }: { jobId: string; projectId: string }) {
    const router = useRouter();
    const searchParams = useSearchParams();
    const queryClient = useQueryClient();
    const t = useTranslations("Results.progress");

    const didNavigateRef = useRef(false);

    const buildResultUrl = useCallback(() => {
        const params = new URLSearchParams(searchParams?.toString() || "");
        params.delete("jobId");
        const qs = params.toString();
        return qs ? `/projects/${projectId}/results?${qs}` : `/projects/${projectId}/results`;
    }, [projectId, searchParams]);

    const navigateToResult = useCallback(() => {
        if (didNavigateRef.current) return;
        didNavigateRef.current = true;
        queryClient.invalidateQueries({ queryKey: queryKeys.result(projectId) });
        router.replace(buildResultUrl(), { scroll: false });
    }, [buildResultUrl, projectId, queryClient, router]);

    const { connectionMode } = useJobSse({
        jobId,
        onEvent: (event) => {
            if (event.type === "state" && event.stage === "assemble_result" && event.message === "status=succeeded") {
                navigateToResult();
            }
        }
    });

    const pollingEnabled = connectionMode !== "sse";
    const { data: job } = useJobQueryWithOptions(jobId, { pollingEnabled });
    const { data: logs } = useJobLogsQueryWithOptions(jobId, undefined, { pollingEnabled });

    const [actionError, setActionError] = useState<string | null>(null);
    const [isResuming, setIsResuming] = useState(false);
    const [isCanceling, setIsCanceling] = useState(false);

    // Auto-refresh result when job succeeds via polling (backup to SSE)
    useEffect(() => {
        if (job?.status === "succeeded") {
            navigateToResult();
        }
    }, [job?.status, navigateToResult]);

    const progressPercent = Math.round((job?.progress || 0) * 100);
    const details = job?.error?.details;
    const detailsObj = (details && typeof details === "object") ? (details as Record<string, unknown>) : null;
    const duplicateReason = detailsObj?.reason;
    const isDuplicateBlocked = job?.status === "blocked" && duplicateReason === "already_analyzed";

    const statusMessage = isDuplicateBlocked
        ? t("alreadyAnalyzedStatus")
        : (job?.stage ? t("processing", { stage: job.stage }) : t("preparing"));
    const latestLog = logs?.items?.[logs.items.length - 1]?.message;

    const canCancel = job?.status === "running" || job?.status === "queued" || job?.status === "blocked";
    const canResume = job?.status === "failed" || job?.status === "canceled" || job?.status === "blocked";
    const resumeLabel = isDuplicateBlocked ? t("reanalyze") : (job?.status === "failed" ? t("retry") : t("resume"));

    const handleResume = async () => {
        if (!canResume || isResuming) return;
        setIsResuming(true);
        setActionError(null);
        try {
            await resumeProjectJob(projectId, jobId);
            queryClient.invalidateQueries({ queryKey: queryKeys.job(jobId) });
            queryClient.invalidateQueries({ queryKey: queryKeys.logs(jobId) });
        } catch (e) {
            const msg = (e as { message?: unknown } | null)?.message;
            setActionError(typeof msg === "string" && msg.trim() ? msg : String(e));
        } finally {
            setIsResuming(false);
        }
    };

    const handleCancel = async () => {
        if (!canCancel || isCanceling) return;
        setIsCanceling(true);
        setActionError(null);
        try {
            await cancelJob(jobId);
            queryClient.invalidateQueries({ queryKey: queryKeys.job(jobId) });
            queryClient.invalidateQueries({ queryKey: queryKeys.logs(jobId) });
        } catch (e) {
            const msg = (e as { message?: unknown } | null)?.message;
            setActionError(typeof msg === "string" && msg.trim() ? msg : String(e));
        } finally {
            setIsCanceling(false);
        }
    };

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

                {isDuplicateBlocked ? (
                    <div className="mt-4 w-full rounded-lg border border-amber-200 bg-amber-50 p-4 text-amber-900">
                        <p className="font-semibold">{t("alreadyAnalyzedTitle")}</p>
                        <p className="mt-1 text-sm text-amber-800">{t("alreadyAnalyzedBody")}</p>
                    </div>
                ) : null}

                {isDuplicateBlocked ? (
                    <div className="mt-4 flex gap-3">
                        <button
                            onClick={navigateToResult}
                            className="px-4 py-2 bg-white border border-stone-300 rounded shadow-sm hover:bg-stone-50 text-sm font-medium"
                        >
                            {t("viewExisting")}
                        </button>
                        <button
                            onClick={handleResume}
                            disabled={isResuming}
                            className="px-4 py-2 bg-orange-600 text-white rounded hover:bg-orange-700 disabled:opacity-50 disabled:cursor-not-allowed text-sm font-medium"
                        >
                            {isResuming ? t("reanalyzing") : resumeLabel}
                        </button>
                    </div>
                ) : (canResume || canCancel ? (
                    <div className="mt-4 flex gap-3">
                        {canResume ? (
                            <button
                                onClick={handleResume}
                                disabled={isResuming}
                                className="px-4 py-2 bg-orange-600 text-white rounded hover:bg-orange-700 disabled:opacity-50 disabled:cursor-not-allowed text-sm font-medium"
                            >
                                {isResuming ? t("resuming") : resumeLabel}
                            </button>
                        ) : null}

                        {canCancel ? (
                            <button
                                onClick={handleCancel}
                                disabled={isCanceling}
                                className="px-4 py-2 bg-white border border-stone-300 rounded shadow-sm hover:bg-stone-50 disabled:opacity-50 disabled:cursor-not-allowed text-sm font-medium"
                            >
                                {isCanceling ? t("canceling") : t("cancel")}
                            </button>
                        ) : null}
                    </div>
                ) : null)}

                {actionError ? (
                    <p className="mt-3 text-sm text-red-600 wrap-break-word max-w-full">{actionError}</p>
                ) : null}

                {job?.status === "failed" && job?.error && (
                    <div className="mt-6 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700 max-w-full">
                        <h3 className="font-bold mb-1">{t("failed")}</h3>
                        <p className="text-sm font-medium">{job.error.message}</p>

                        {(() => {
                            const details = job.error?.details;
                            const detailsObj = (details && typeof details === "object") ? (details as Record<string, unknown>) : null;
                            const httpStatus = detailsObj?.httpStatus;
                            const outputTail = detailsObj?.outputTail;

                            return (
                                <div className="mt-3 space-y-2">
                                    {httpStatus != null ? (
                                        <div className="text-sm">
                                            <span className="font-medium">HTTP 状态码：</span>
                                            <span className="font-mono">{String(httpStatus)}</span>
                                        </div>
                                    ) : null}

                                    {typeof outputTail === "string" && outputTail.trim() ? (
                                        <div>
                                            <div className="text-sm font-medium">yt-dlp 输出（截断）</div>
                                            <pre className="mt-1 text-xs font-mono whitespace-pre-wrap overflow-auto bg-red-100/50 border border-red-200 rounded p-2">
                                                {outputTail}
                                            </pre>
                                        </div>
                                    ) : null}

                                    <details className="text-xs">
                                        <summary className="cursor-pointer">原始错误信息</summary>
                                        <pre className="mt-1 font-mono whitespace-pre-wrap overflow-auto bg-red-100/50 border border-red-200 rounded p-2">
                                            {JSON.stringify(job.error, null, 2)}
                                        </pre>
                                    </details>
                                </div>
                            );
                        })()}
                        <button
                            onClick={() => router.push(`/projects`)}
                            className="mt-4 px-4 py-2 bg-white border border-red-300 rounded shadow-sm hover:bg-red-50 text-sm font-medium"
                        >
                            {t("backToProjects")}
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
    const router = useRouter();
    const projectId = params?.projectId as string;
    const jobId = searchParams?.get("jobId");

    const t = useTranslations("Results");

    const queryClient = useQueryClient();

    // Only fetch the result when we do NOT already have a jobId.
    // When jobId is present (freshly redirected from ingest), the analysis is
    // definitely still running, so the result fetch would be a guaranteed 404.
    const resultEnabled = !jobId;
    const { data: result, isLoading: resultLoading, error: resultError } = useLatestResult(projectId, { enabled: resultEnabled });

    // When there's no jobId in the URL and result is absent (404), we need to
    // find the latest job for this project to show progress.
    const resultIs404 = !!resultError;
    const needsJobDiscovery = resultEnabled && resultIs404 && !jobId;

    const { data: projectDetail, isLoading: projectDetailLoading } = useProjectDetail(projectId, { enabled: needsJobDiscovery });
    const discoveredJobId = projectDetail?.latestJobId;

    // Refs
    const videoPlayerRef = useRef<VideoPlayerRef>(null);
    const noteEditorRef = useRef<NoteEditorRef>(null);
    const playerContainerRef = useRef<HTMLDivElement>(null);
    const [videoElement, setVideoElement] = useState<HTMLVideoElement | null>(null);

    const videoPlayerCallbackRef = useCallback((instance: VideoPlayerRef | null) => {
        videoPlayerRef.current = instance;
        const element = instance?.getVideoElement() ?? null;
        setVideoElement((prev) => (prev === element ? prev : element));
    }, []);

    // State
    const [isFloatingVisible, setIsFloatingVisible] = useState(false);
    const [isDismissed, setIsDismissed] = useState(false); // Track if user dismissed the floating player
    const activeTabParam = searchParams?.get("tab");
    const activeTab: "mindmap" | "chat" | "exercises" =
        activeTabParam === "chat" || activeTabParam === "exercises" || activeTabParam === "mindmap"
            ? activeTabParam
            : "mindmap";

    // Handle Tab change with URL updates
    const handleTabChange = (tab: "mindmap" | "chat" | "exercises") => {
        // Update URL
        const params = new URLSearchParams(searchParams?.toString() || "");
        params.set("tab", tab);
        router.replace(`${window.location.pathname}?${params.toString()}`, { scroll: false });

        // Prefetch for exercises
        if (tab === "exercises" && projectId) {
            queryClient.prefetchQuery({
                queryKey: queryKeys.quizSessions(projectId),
                queryFn: () => fetchQuizSessions(projectId),
            });
        }
    };

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

    // ─── State Machine ────────────────────────────────────────────────────────

    // 1. If we have a result, show the dashboard (Happy path)
    if (result) {
        // 获取视频资源 URL
        const videoAsset = result.assetRefs?.find((ref) => ref.kind === "video");
        const videoSrc = videoAsset ? endpoints.assetContent(videoAsset.assetId) : undefined;

        return (
            <ResultLayout>

                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 min-h-screen pb-20">
                    {/* Left Pane: Tabs (Mindmap | Chat | Exercises) */}
                    <div className="lg:sticky lg:top-6 lg:h-[calc(100vh-3rem)] bg-white rounded-xl border border-stone-200 overflow-hidden flex flex-col shadow-sm">

                        {/* Tab Header */}
                        <div className="flex border-b border-stone-200 bg-stone-50/50">
                            <button
                                onClick={() => handleTabChange("mindmap")}
                                className={`flex-1 py-3 xl:py-4 text-sm xl:text-lg font-medium flex items-center justify-center gap-2 xl:gap-3 border-b-2 transition-colors ${activeTab === "mindmap"
                                    ? "border-orange-500 text-orange-700 bg-white"
                                    : "border-transparent text-stone-600 hover:text-stone-900 hover:bg-stone-100"
                                    }`}
                            >
                                <BrainCircuit className="w-4 h-4 xl:w-5 xl:h-5" />
                                {t("tabs.mindmap")}
                            </button>
                            <button
                                onClick={() => handleTabChange("chat")}
                                className={`flex-1 py-3 xl:py-4 text-sm xl:text-lg font-medium flex items-center justify-center gap-2 xl:gap-3 border-b-2 transition-colors ${activeTab === "chat"
                                    ? "border-orange-500 text-orange-700 bg-white"
                                    : "border-transparent text-stone-600 hover:text-stone-900 hover:bg-stone-100"
                                    }`}
                            >
                                <MessageSquare className="w-4 h-4 xl:w-5 xl:h-5" />
                                {t("tabs.chat")}
                            </button>
                            <button
                                onClick={() => handleTabChange("exercises")}
                                className={`flex-1 py-3 xl:py-4 text-sm xl:text-lg font-medium flex items-center justify-center gap-2 xl:gap-3 border-b-2 transition-colors ${activeTab === "exercises"
                                    ? "border-orange-500 text-orange-700 bg-white"
                                    : "border-transparent text-stone-600 hover:text-stone-900 hover:bg-stone-100"
                                    }`}
                            >
                                <Layout className="w-4 h-4 xl:w-5 xl:h-5" />
                                {t("tabs.exercises")}
                            </button>
                        </div>

                        {/* Tab Content */}
                        <div className="flex-1 relative overflow-hidden">
                            {activeTab === "mindmap" && (
                                <MindmapEditor
                                    projectId={projectId}
                                    resultId={result.resultId}
                                    initialMindmap={result.mindmap}
                                    onNodeNavigation={handleMindmapNavigation}
                                    onSaveSuccess={() => console.log("Mindmap saved successfully")}
                                    onSaveError={(error) => console.error("Failed to save mindmap:", error instanceof Error ? error.message : error)}
                                />
                            )}
                            {activeTab === "chat" && <AIChat />}
                            {activeTab === "exercises" && <ExercisesCanvas projectId={projectId} />}
                        </div>
                    </div>

                    {/* Right Pane: Video + Note - Independent Scroll */}
                    <div className="flex flex-col space-y-6 lg:sticky lg:top-6 lg:h-[calc(100vh-3rem)] overflow-y-auto pb-10 [&::-webkit-scrollbar]:hidden [-ms-overflow-style:none] [scrollbar-width:none]">
                        {/* Video Player Container */}
                        <div
                            ref={playerContainerCallbackRef}
                            className={`shrink-0 bg-black rounded-xl overflow-hidden shadow-lg border border-stone-800 transition-opacity duration-300 ${isFloatingVisible ? 'opacity-20 pointer-events-none grayscale' : 'opacity-100'}`}
                        >
                            <VideoPlayer
                                ref={videoPlayerCallbackRef}
                                src={videoSrc}
                            />
                        </div>

                        {/* Note Editor */}
                        <div className="bg-white rounded-xl border border-stone-200 shadow-sm flex-none flex flex-col">
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

    // 2. If we came from ingest with an explicit jobId, show progress immediately
    //    (result is disabled, so we never fetched it)
    if (jobId) {
        return <JobProgress jobId={jobId} projectId={projectId} />;
    }

    // 3. Loading the result (no jobId, result fetch in-flight)
    if (resultLoading) {
        return (
            <ResultLayout>
                <div className="flex items-center justify-center min-h-[60vh]">
                    <div className="text-center">
                        <div className="inline-block w-12 h-12 border-4 border-stone-300 border-t-orange-600 rounded-full animate-spin mb-4" />
                        <p className="text-stone-600">{t("loading")}</p>
                    </div>
                </div>
            </ResultLayout>
        );
    }

    // 4. Result is 404 — try to discover the latest job for this project
    if (resultIs404) {
        // Still fetching the project detail to find the job
        if (projectDetailLoading) {
            return (
                <ResultLayout>
                    <div className="flex items-center justify-center min-h-[60vh]">
                        <div className="text-center">
                            <div className="inline-block w-12 h-12 border-4 border-stone-300 border-t-orange-600 rounded-full animate-spin mb-4" />
                            <p className="text-stone-600">{t("loading")}</p>
                        </div>
                    </div>
                </ResultLayout>
            );
        }

        // Found a job — show progress view (JobProgress handles its own SSE/polling
        // and will invalidate the result query when it detects success)
        if (discoveredJobId) {
            return <JobProgress jobId={discoveredJobId} projectId={projectId} />;
        }

        // No job found at all — project exists but no analysis has ever been created
        return (
            <ResultLayout>
                <div className="flex items-center justify-center min-h-[60vh]">
                    <p className="text-stone-600">{t("noResult")}</p>
                </div>
            </ResultLayout>
        );
    }

    // 5. Other errors (network failure, 5xx, etc.)
    if (resultError) {
        const messageCandidate = (resultError as { message?: unknown } | null)?.message;
        const resultErrorMessage =
            typeof messageCandidate === "string" && messageCandidate.trim().length > 0
                ? messageCandidate
                : t("notFound");

        return (
            <ResultLayout>
                <div className="flex items-center justify-center min-h-[60vh]">
                    <div className="text-center max-w-md">
                        <h2 className="text-xl font-semibold text-stone-900 mb-2">{t("loadFailed")}</h2>
                        <p className="text-stone-600 mb-4">
                            {resultErrorMessage}
                        </p>
                    </div>
                </div>
            </ResultLayout>
        );
    }

    // 6. Fallback: no result, no error, no jobId (should rarely happen)
    return (
        <ResultLayout>
            <div className="flex items-center justify-center min-h-[60vh]">
                <p className="text-stone-600">{t("noResult")}</p>
            </div>
        </ResultLayout>
    );
}

