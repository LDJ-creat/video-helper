/**
 * Notes API Contracts
 * Based on Story 9-1-be-core-note-save
 */

import type { JSONContent } from "@tiptap/react";

/**
 * Request body for saving/updating note
 */
export interface SaveNoteRequest {
    /** TipTap JSON document */
    content: JSONContent;
}

/**
 * Response for save note operation
 */
export interface SaveNoteResponse {
    /** Result ID */
    resultId: string;
    /** Project ID */
    projectId: string;
    /** Timestamp when saved (Unix ms) */
    savedAtMs: number;
}
