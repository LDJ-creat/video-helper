import { apiFetch } from "./apiClient";
import { endpoints } from "./endpoints";
import type { Result, Asset } from "../contracts/resultTypes";

/**
 * 获取项目的最新分析结果
 * @param projectId - 项目 ID
 * @returns Result 对象（包含 chapters、highlights、mindmap、note 等）
 */
export async function fetchLatestResult(projectId: string): Promise<Result> {
    return apiFetch<Result>(endpoints.resultLatest(projectId));
}

/**
 * 获取 Asset 元信息
 * @param assetId - Asset ID
 * @returns Asset 对象（包含 contentUrl）
 */
export async function fetchAsset(assetId: string): Promise<Asset> {
    return apiFetch<Asset>(endpoints.asset(assetId));
}
