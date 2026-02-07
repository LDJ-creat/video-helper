import { apiFetch } from "./apiClient";
import { endpoints } from "./endpoints";
import type { Result, Mindmap, ContentBlock, UpdateResultResponse } from "../contracts/resultTypes";

export async function fetchLatestResult(projectId: string): Promise<Result> {
    return apiFetch<Result>(endpoints.resultLatest(projectId));
}

export async function saveMindmap(projectId: string, resultId: string, mindmap: Mindmap): Promise<UpdateResultResponse> {
    // Current API contract: latest result. resultId param might be ignored by mapping logic but kept for consistency or if endpoint changes.
    // However, endpoints.ts uses latest.
    return apiFetch<UpdateResultResponse>(endpoints.saveMindmap(projectId, resultId), {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mindmap }),
    });
}

export async function saveContentBlocks(projectId: string, resultId: string, contentBlocks: ContentBlock[]): Promise<UpdateResultResponse> {
    return apiFetch<UpdateResultResponse>(endpoints.saveContentBlocks(projectId, resultId), {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ contentBlocks }),
    });
}
