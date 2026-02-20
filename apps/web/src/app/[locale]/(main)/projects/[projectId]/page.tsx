"use client";

import { useProjectDetail } from "@/lib/api/projectQueries";
import { useLatestResult } from "@/lib/api/resultQueries";
import { use } from "react";
import { useRef, useState, useCallback } from "react";
import { MindmapEditor } from "@/components/features/editor/MindmapEditor";
import { NoteEditor, NoteEditorRef } from "@/components/features/editor/NoteEditor";
import { VideoPlayer, VideoPlayerRef } from "@/components/features/player/VideoPlayer";
import { AssetRef } from "@/lib/contracts/resultTypes";

export default function ProjectDetailPage({
    params,
}: {
    params: Promise<{ projectId: string }>;
}) {
    const { projectId } = use(params);
    const { data: project, isLoading: isProjectLoading } = useProjectDetail(projectId);
    const { data: result, isLoading: isResultLoading } = useLatestResult(projectId);

    const noteEditorRef = useRef<NoteEditorRef>(null);
    const videoPlayerRef = useRef<VideoPlayerRef>(null);

    // Interaction Handlers
    const handleMindmapNavigation = useCallback((targetBlockId: string, targetHighlightId?: string) => {
        if (targetHighlightId) {
            noteEditorRef.current?.scrollToHighlight(targetHighlightId);
        } else {
            noteEditorRef.current?.scrollToBlock(targetBlockId);
        }
    }, []);

    const handleBlockNavigation = useCallback((timeMs: number) => {
        videoPlayerRef.current?.seekTo(timeMs);
        // Optional: Auto-play
        // videoPlayerRef.current?.play(); 
    }, []);

    if (isProjectLoading || isResultLoading) {
        return (
            <div className="flex items-center justify-center h-full">
                <div className="w-8 h-8 border-4 border-orange-500 border-t-transparent rounded-full animate-spin" />
            </div>
        );
    }

    if (!project) {
        return <div className="p-8 text-center text-stone-500">项目未找到</div>;
    }

    if (!result) {
        // Fallback state if result is not ready (e.g. processing)
        return (
            <div className="p-8 flex flex-col items-center justify-center h-full space-y-4">
                <h1 className="text-2xl font-bold text-stone-800">{project.title}</h1>
                <p className="text-stone-500">分析结果尚未就绪，请稍候...</p>
                <div className="text-sm text-stone-400">最新状态: {project.latestResultId ? "已生成" : "处理中"}</div>
                {/* Can add a Link to go back or refresh */}
            </div>
        );
    }

    // Resolve Video Source
    // Priority: AssetRef (video) > Project Source URL
    const videoAsset = result.assetRefs?.find((a: AssetRef) => a.kind === 'video');
    const videoSrc = videoAsset?.contentUrl || project.sourceUrl;

    return (
        <main className="flex h-[calc(100vh-64px)] overflow-hidden bg-stone-50">
            {/* Left Panel: Mindmap (50%) - Fixed */}
            <div className="w-1/2 h-full border-r border-stone-200 relative">
                <MindmapEditor
                    projectId={projectId}
                    resultId={result.resultId}
                    initialMindmap={result.mindmap}
                    onNodeNavigation={handleMindmapNavigation}
                />
            </div>

            {/* Right Panel: Video + Content (50%) - Scrollable */}
            <div className="w-1/2 h-full flex flex-col bg-white overflow-y-auto">
                {/* Video Section */}
                <div className="sticky top-0 z-20 bg-black shadow-lg">
                    <VideoPlayer
                        ref={videoPlayerRef}
                        src={videoSrc}
                        className="w-full"
                    />
                </div>

                {/* Content/Note Section */}
                <div className="flex-1 p-4">
                    <div className="mb-4 pb-4 border-b border-stone-100">
                        <h2 className="text-xl font-bold text-stone-800 mb-2">{project.title}</h2>
                        <div className="flex gap-2 text-xs text-stone-400">
                            <span>{new Date(result.createdAtMs).toLocaleString()}</span>
                            <span>•</span>
                            <span>v{result.schemaVersion}</span>
                        </div>
                    </div>

                    <NoteEditor
                        ref={noteEditorRef}
                        projectId={projectId}
                        resultId={result.resultId}
                        contentBlocks={result.contentBlocks || []}
                        onBlockNavigation={handleBlockNavigation}
                    />
                </div>
            </div>
        </main>
    );
}

