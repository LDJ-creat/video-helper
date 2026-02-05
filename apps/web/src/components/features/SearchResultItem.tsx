"use client";

import Link from "next/link";
import type { SearchResult } from "@/lib/contracts/searchTypes";

interface SearchResultItemProps {
    result: SearchResult;
}

export function SearchResultItem({ result }: SearchResultItemProps) {
    // 构造跳转链接（根据 api.md 契约）
    const href = result.chapterId
        ? `/projects/${result.projectId}/results?chapterId=${result.chapterId}`
        : `/projects/${result.projectId}`;

    return (
        <Link
            href={href}
            className="block p-4 border-b border-gray-200 hover:bg-gray-50 transition-colors"
        >
            <div className="flex flex-col gap-1">
                <div className="flex items-center gap-2">
                    <span className="text-xs font-medium text-gray-500 uppercase">
                        {result.chapterId ? "章节" : "项目"}
                    </span>
                    <h3 className="text-lg font-semibold text-gray-900">
                        项目 ID: {result.projectId}
                    </h3>
                </div>

                {result.chapterId && (
                    <p className="text-sm text-gray-600">
                        章节 ID: {result.chapterId}
                    </p>
                )}
            </div>
        </Link>
    );
}
