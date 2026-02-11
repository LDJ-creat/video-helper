// Result/Assets 类型定义（对齐 api.md 契约）

// Mindmap 相关类型
export type MindmapNode = {
    id: string;
    type: "root" | "topic" | "detail";
    label: string;
    level: number; // 0=root, 1=topic, 2=detail
    data?: {
        targetBlockId?: string;
        targetHighlightId?: string;
    };
};

export type MindmapEdge = {
    id: string;
    source: string;
    target: string;
    label?: string | null;
};

export type Mindmap = {
    nodes: MindmapNode[];
    edges: MindmapEdge[];
};

// 关键帧类型 (Embedded in Highlight)
export type Keyframe = {
    assetId: string;
    contentUrl: string;
    timeMs: number;
};

// 重点类型
export type Highlight = {
    highlightId: string;
    idx: number; // 0-based within block
    text: string;
    startMs: number;
    endMs: number;
    keyframe?: Keyframe;
};

// 内容块类型
export type ContentBlock = {
    blockId: string;
    idx: number; // 0-based
    title: string;
    startMs: number;
    endMs: number;
    highlights: Highlight[];
};

// Asset 引用类型
export type AssetRef = {
    assetId: string;
    kind: "screenshot" | "upload" | "user_image" | "cover" | "video";
    contentUrl?: string;
};

// Result 核心类型
export type Result = {
    resultId: string;
    projectId: string;
    schemaVersion: string;
    pipelineVersion: string;
    createdAtMs: number;
    contentBlocks: ContentBlock[];
    mindmap: Mindmap;
    assetRefs: AssetRef[];
};

// Asset 完整信息类型
export type Asset = {
    assetId: string;
    projectId: string;
    kind: "screenshot" | "upload" | "user_image" | "cover" | "video";
    origin: "generated" | "uploaded" | "remote";
    mime?: string;
    width?: number;
    height?: number;
    createdAtMs: number;
    contentUrl: string;
};

// Update Response
export type UpdateResultResponse = {
    updatedAtMs: number;
};

