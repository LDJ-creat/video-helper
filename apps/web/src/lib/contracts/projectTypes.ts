// Project 实体类型（对齐 api.md 契约）
export type SourceType = "youtube" | "bilibili" | "url" | "local_file" | "upload";

export type Project = {
  projectId: string;           // UUID
  title: string;
  sourceType: SourceType;
  sourceUrl?: string;          // 平台类来源
  durationMs?: number;         // 可选
  latestResultId?: string;     // UUID，指向最新结果
  latestJobId?: string;        // UUID，指向最新 Job（分析任务）
  createdAtMs: number;         // Unix epoch milliseconds
  updatedAtMs: number;
};

// 列表响应（cursor 分页）
export type ProjectsListResponse = {
  items: Project[];
  nextCursor: string | null;
};

// 详情响应
export type ProjectDetailResponse = Project;
