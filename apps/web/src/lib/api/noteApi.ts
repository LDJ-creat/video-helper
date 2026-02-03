/**
 * Notes API Client
 * Story 9-2: TipTap editor with autosave
 */

import { SaveNoteRequest, SaveNoteResponse } from "@/lib/contracts/notes";
import { endpoints } from "./endpoints";
import { apiFetch } from "./apiClient";

/**
 * Save note content for a result
 */
export async function saveNote(
    projectId: string,
    resultId: string,
    request: SaveNoteRequest
): Promise<SaveNoteResponse> {
    return apiFetch<SaveNoteResponse>(endpoints.saveNote(projectId, resultId), {
        method: "PUT",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify(request),
    });
}
