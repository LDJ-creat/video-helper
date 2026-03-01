import { apiFetch } from "./apiClient";
import { endpoints } from "./endpoints";
import type { Result, Mindmap, ContentBlock, UpdateResultResponse } from "../contracts/resultTypes";
import { config } from "../config";

/* ── Queries ── */

export async function fetchLatestResult(projectId: string): Promise<Result> {
    const url = `${config.apiBaseUrl}${endpoints.resultLatest(projectId)}`;
    return apiFetch<Result>(url);
}

/* ── Editing mutations (aligned with api.md Section 4) ── */

/** Overwrite the entire mindmap graph. */
export async function saveMindmap(projectId: string, mindmap: Mindmap): Promise<UpdateResultResponse> {
    const url = `${config.apiBaseUrl}${endpoints.saveMindmap(projectId)}`;
    return apiFetch<UpdateResultResponse>(url, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ nodes: mindmap.nodes, edges: mindmap.edges }),
    });
}

/** Full-array overwrite of contentBlocks (used by NoteEditor autosave). */
export async function saveContentBlocks(projectId: string, contentBlocks: ContentBlock[]): Promise<UpdateResultResponse> {
    const url = `${config.apiBaseUrl}${endpoints.saveContentBlocks(projectId)}`;
    return apiFetch<UpdateResultResponse>(url, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ contentBlocks }),
    });
}

/** Patch a single content block (title, time range when allowed). */
export async function editBlock(
    projectId: string,
    blockId: string,
    patch: { title?: string; startMs?: number; endMs?: number },
): Promise<UpdateResultResponse> {
    const url = `${config.apiBaseUrl}${endpoints.editBlock(projectId, blockId)}`;
    return apiFetch<UpdateResultResponse>(url, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(patch),
    });
}

/** Bind or unbind a keyframe to/from a highlight. Pass assetId=null to unbind. */
export async function updateHighlightKeyframe(
    projectId: string,
    highlightId: string,
    payload: { assetId: string | null; timeMs?: number },
): Promise<UpdateResultResponse> {
    const url = `${config.apiBaseUrl}${endpoints.updateHighlightKeyframe(projectId, highlightId)}`;
    return apiFetch<UpdateResultResponse>(url, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
    });
}

export interface UploadAssetResponse {
    assetId: string;
    contentUrl: string;
    kind: string;
    createdAtMs: number;
}

/** Upload an image file and create an Asset record (for keyframe replacement). */
export async function uploadAsset(
    projectId: string,
    file: File,
    kind: string = "user_image",
): Promise<UploadAssetResponse> {
    const url = `${config.apiBaseUrl}${endpoints.uploadAsset(projectId)}`;
    const form = new FormData();
    form.append("file", file);
    form.append("kind", kind);
    return apiFetch<UploadAssetResponse>(url, {
        method: "POST",
        body: form,
        // Do NOT set Content-Type — browser sets it with boundary for multipart
    });
}
