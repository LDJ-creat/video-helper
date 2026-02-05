"use client";

import { Fragment } from "react";
import { SearchResultItem } from "./SearchResultItem";
import type { InfiniteData } from "@tanstack/react-query";
import type { SearchResponse } from "@/lib/contracts/searchTypes";

interface SearchResultsProps {
    data: InfiniteData<SearchResponse> | undefined;
    isLoading: boolean;
    isError: boolean;
    error: Error | null;
    hasNextPage: boolean;
    isFetchingNextPage: boolean;
    fetchNextPage: () => void;
}

export function SearchResults({
    data,
    isLoading,
    isError,
    error,
    hasNextPage,
    isFetchingNextPage,
    fetchNextPage,
}: SearchResultsProps) {
    if (isLoading) {
        return (
            <div className="flex items-center justify-center py-12">
                <div className="text-gray-500">搜索中...</div>
            </div>
        );
    }

    if (isError) {
        return (
            <div className="flex items-center justify-center py-12">
                <div className="text-red-500">
                    搜索失败: {error?.message || "未知错误"}
                </div>
            </div>
        );
    }

    const allResults = data?.pages.flatMap((page) => page.items) ?? [];

    if (allResults.length === 0) {
        return (
            <div className="flex items-center justify-center py-12">
                <div className="text-gray-500">未找到相关结果</div>
            </div>
        );
    }

    return (
        <div className="w-full">
            <div className="border border-gray-200 rounded-lg overflow-hidden">
                {data?.pages.map((page, pageIndex) => (
                    <Fragment key={pageIndex}>
                        {page.items.map((result) => (
                            <SearchResultItem key={result.resultId} result={result} />
                        ))}
                    </Fragment>
                ))}
            </div>

            {hasNextPage && (
                <div className="mt-4 text-center">
                    <button
                        onClick={fetchNextPage}
                        disabled={isFetchingNextPage}
                        className="px-6 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
                    >
                        {isFetchingNextPage ? "加载中..." : "加载更多"}
                    </button>
                </div>
            )}
        </div>
    );
}
