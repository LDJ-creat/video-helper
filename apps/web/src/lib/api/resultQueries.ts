import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { queryKeys } from "./queryKeys";
import {
    fetchLatestResult,
    saveMindmap,
    saveContentBlocks,
    editBlock,
    updateHighlightKeyframe,
    uploadAsset,
} from "./resultApi";
import type { Mindmap, ContentBlock } from "../contracts/resultTypes";

/* ── Query hook ── */

export function useLatestResult(projectId: string, options?: { enabled?: boolean }) {
    return useQuery({
        queryKey: queryKeys.result(projectId),
        queryFn: () => fetchLatestResult(projectId),
        retry: false,
        enabled: options?.enabled ?? true,
    });
}

/* ── Mutation hooks (editing) ── */

export function useSaveMindmap(projectId: string) {
    return useMutation({
        mutationFn: (mindmap: Mindmap) => saveMindmap(projectId, mindmap),
        onSuccess: () => {
            // Silently succeed — MindmapEditor manages its own state
        },
    });
}

export function useSaveContentBlocks(projectId: string) {
    return useMutation({
        mutationFn: (contentBlocks: ContentBlock[]) =>
            saveContentBlocks(projectId, contentBlocks),
    });
}

export function useEditBlock(projectId: string) {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: (data: { blockId: string; patch: { title?: string; startMs?: number; endMs?: number } }) =>
            editBlock(projectId, data.blockId, data.patch),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: queryKeys.result(projectId) });
        },
    });
}

export function useUpdateHighlightKeyframe(projectId: string) {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: (data: { highlightId: string; payload: { assetId: string | null; timeMs?: number } }) =>
            updateHighlightKeyframe(projectId, data.highlightId, data.payload),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: queryKeys.result(projectId) });
        },
    });
}

export function useUploadAsset(projectId: string) {
    return useMutation({
        mutationFn: (data: { file: File; kind?: string }) =>
            uploadAsset(projectId, data.file, data.kind),
    });
}
