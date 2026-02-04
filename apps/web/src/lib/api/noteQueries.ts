/**
 * Notes React Query Hooks
 * Story 9-2: TipTap editor with autosave
 */

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { SaveNoteRequest, SaveNoteResponse } from "@/lib/contracts/notes";
import { saveNote } from "./noteApi";
import { queryKeys } from "./queryKeys";

interface SaveNoteMutationVariables {
    projectId: string;
    resultId: string;
    content: SaveNoteRequest;
}

/**
 * Mutation hook for saving note
 */
export function useSaveNote() {
    const queryClient = useQueryClient();

    return useMutation<SaveNoteResponse, Error, SaveNoteMutationVariables>({
        mutationFn: ({ projectId, resultId, content }) =>
            saveNote(projectId, resultId, content),
        onSuccess: (data) => {
            // Invalidate result query to reflect updated note
            queryClient.invalidateQueries({
                queryKey: queryKeys.result(data.projectId),
            });
        },
    });
}
