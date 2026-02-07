import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { queryKeys } from "./queryKeys";
import { fetchLatestResult, saveMindmap, saveContentBlocks } from "./resultApi";
import type { Mindmap, ContentBlock } from "../contracts/resultTypes";

export function useLatestResult(projectId: string) {
    return useQuery({
        queryKey: queryKeys.result(projectId),
        queryFn: () => fetchLatestResult(projectId),
        retry: false, // Don't retry 404s endlessly
    });
}

export function useSaveMindmap(projectId: string) {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: (data: { resultId: string; mindmap: Mindmap }) =>
            saveMindmap(projectId, data.resultId, data.mindmap),
        onSuccess: () => {
            // Optional: Invalidate or update cache?
            // queryClient.invalidateQueries({ queryKey: queryKeys.result(projectId) });
        }
    });
}

export function useSaveContentBlocks(projectId: string) {
    return useMutation({
        mutationFn: (data: { resultId: string; contentBlocks: ContentBlock[] }) =>
            saveContentBlocks(projectId, data.resultId, data.contentBlocks),
    });
}
