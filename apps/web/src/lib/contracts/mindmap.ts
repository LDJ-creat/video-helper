/**
 * Mindmap API Contracts
 * Based on Story 9-3-be-core-mindmap-save
 */

/**
 * Mindmap node definition
 */
export interface MindmapNode {
    id: string;
    type: "root" | "topic" | "detail";
    label: string;
    level: number;
    data?: {
        targetBlockId?: string;
        targetHighlightId?: string;
    };
}

/**
 * Mindmap edge definition
 */
export interface MindmapEdge {
    id: string;
    source: string;
    target: string;
    label?: string | null;
}

/**
 * Mindmap graph structure
 */
export interface Mindmap {
    nodes: MindmapNode[];
    edges: MindmapEdge[];
}

/**
 * Request body for saving/updating mindmap
 */
export interface SaveMindmapRequest {
    /** Mindmap graph data */
    mindmap: Mindmap;
}

/**
 * Response for save mindmap operation
 */
export interface SaveMindmapResponse {
    /** Result ID */
    resultId: string;
    /** Project ID */
    projectId: string;
    /** Timestamp when saved (Unix ms) */
    savedAtMs: number;
}
