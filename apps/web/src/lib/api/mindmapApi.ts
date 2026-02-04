/**
 * Mindmap API Client
 * Story 9-4: ReactFlow editor with autosave
 */

import { SaveMindmapRequest, SaveMindmapResponse } from "@/lib/contracts/mindmap";
import { endpoints } from "./endpoints";
import { apiFetch } from "./apiClient";

/**
 * Save mindmap content for a result
 */
export async function saveMindmap(
    projectId: string,
    resultId: string,
    request: SaveMindmapRequest
): Promise<SaveMindmapResponse> {
    return apiFetch<SaveMindmapResponse>(endpoints.saveMindmap(projectId, resultId), {
        method: "PUT",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify(request),
    });
}
