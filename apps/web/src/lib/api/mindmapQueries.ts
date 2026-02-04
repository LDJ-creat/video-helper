/**
 * Mindmap React Query Hooks
 * Story 9-4: ReactFlow editor with autosave
 */

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { SaveMindmapRequest, SaveMindmapResponse } from "@/lib/contracts/mindmap";
import { saveMindmap } from "./mindmapApi";
import { queryKeys } from "./queryKeys";

interface SaveMindmapMutationVariables {
    projectId: string;
    resultId: string;
    data: SaveMindmapRequest;
}

/**
 * Mutation hook for saving mindmap
 */
export function useSaveMindmap() {
    const queryClient = useQueryClient();

    return useMutation<SaveMindmapResponse, Error, SaveMindmapMutationVariables>({
        mutationFn: ({ projectId, resultId, data }) =>
            saveMindmap(projectId, resultId, data),
        onSuccess: (data) => {
            // Invalidate result query to reflect updated mindmap
            queryClient.invalidateQueries({
                queryKey: queryKeys.result(data.projectId),
            });
        },
    });
}
