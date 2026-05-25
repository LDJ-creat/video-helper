// Search 相关类型定义（对齐 api.md 契约）

import type { Project, SourceType } from "./projectTypes";

/** 搜索结果项，字段与 Project 列表项对齐以便复用 ProjectCard */
export type SearchResult = Pick<
  Project,
  "projectId" | "title" | "sourceType" | "updatedAtMs" | "categoryId" | "categoryName" | "categorySlug"
> & {
  sourceType: SourceType | string;
};

export type SearchResponse = {
  items: SearchResult[];
  nextCursor: string | null;
};

function normalizeSourceType(raw: string): Project["sourceType"] {
  const s = (raw || "").toLowerCase();
  if (s === "youtube" || s === "bilibili" || s === "upload" || s === "local_file") {
    return s as Project["sourceType"];
  }
  return "url";
}

export function searchResultToProject(item: SearchResult): Project {
  return {
    projectId: item.projectId,
    title: item.title ?? "",
    sourceType: normalizeSourceType(item.sourceType),
    updatedAtMs: item.updatedAtMs,
    categoryId: item.categoryId,
    categoryName: item.categoryName,
    categorySlug: item.categorySlug,
    createdAtMs: item.updatedAtMs,
  };
}
