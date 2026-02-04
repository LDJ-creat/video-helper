/**
 * Mindmap API Contracts
 * Based on Story 9-3-be-core-mindmap-save
 */

/**
 * Mindmap node definition
 */
export interface MindmapNode {
    id: string;
    label: string;
    [key: string]: unknown; // Additional fields for ReactFlow
}

/**
 * Mindmap edge definition
 */
export interface MindmapEdge {
    id: string;
    source: string;
    target: string;
    [key: string]: unknown; // Additional fields for ReactFlow
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
