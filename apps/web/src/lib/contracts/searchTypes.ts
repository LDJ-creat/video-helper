// Search 相关类型定义（对齐 api.md 契约）

// 搜索结果项（严格按照 api.md 契约）
export type SearchResult = {
    projectId: string;          // 必填，用于跳转到 Project
    chapterId: string | null;   // 可选，当命中章节时返回
};

// 搜索响应（cursor 分页）
export type SearchResponse = {
    items: SearchResult[];
    nextCursor: string | null;
};
