// Result/Assets 类型定义（对齐 api.md 契约）

// Mindmap 相关类型
export type MindmapNode = {
    id: string;
    label: string;
    [key: string]: unknown; // 允许扩展字段
};

export type MindmapEdge = {
    id: string;
    source: string;
    target: string;
    [key: string]: unknown;
};

export type Mindmap = {
    nodes: MindmapNode[];
    edges: MindmapEdge[];
};

// TipTap 文档类型
export type TiptapDoc = {
    type: "doc";
    content: unknown[];
};

// 关键帧类型
export type Keyframe = {
    assetId: string;
    idx: number;
    timeMs: number;
    caption?: string;
};

// 章节类型
export type Chapter = {
    chapterId: string;
    idx: number;
    title: string;
    summary?: string;
    startMs: number;
    endMs: number;
    keyframes: Keyframe[];
};

// 重点类型
export type Highlight = {
    highlightId: string;
    chapterId: string;
    idx: number;
    text: string;
    timeMs?: number;
};

// Asset 引用类型
export type AssetRef = {
    assetId: string;
    kind: "screenshot" | "upload" | "user_image" | "cover";
};

// Result 核心类型
export type Result = {
    resultId: string;
    projectId: string;
    schemaVersion: string;
    createdAtMs: number;
    chapters: Chapter[];
    highlights: Highlight[];
    mindmap: Mindmap;
    note: TiptapDoc;
    assetRefs: AssetRef[];
};

// Asset 完整信息类型
export type Asset = {
    assetId: string;
    projectId: string;
    kind: "screenshot" | "upload" | "user_image" | "cover";
    origin: "generated" | "uploaded" | "remote";
    mime?: string;
    width?: number;
    height?: number;
    createdAtMs: number;
    contentUrl: string;
};
