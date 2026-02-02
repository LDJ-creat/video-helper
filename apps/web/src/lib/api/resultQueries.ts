import { useQuery } from "@tanstack/react-query";
import { queryKeys } from "./queryKeys";
import { fetchLatestResult, fetchAsset } from "./resultApi";

/**
 * Hook: 获取项目的最新分析结果
 * @param projectId - 项目 ID
 * @param enabled - 是否启用查询（默认：projectId 存在时启用）
 */
export function useLatestResult(projectId: string, enabled = true) {
    return useQuery({
        queryKey: queryKeys.result(projectId),
        queryFn: () => fetchLatestResult(projectId),
        enabled: !!projectId && enabled,
    });
}

/**
 * Hook: 获取 Asset 元信息
 * @param assetId - Asset ID
 * @param enabled - 是否启用查询（默认：assetId 存在时启用）
 */
export function useAsset(assetId: string, enabled = true) {
    return useQuery({
        queryKey: queryKeys.asset(assetId),
        queryFn: () => fetchAsset(assetId),
        enabled: !!assetId && enabled,
    });
}
