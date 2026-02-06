"use client";

import Link from "next/link";
import type { SearchResult } from "@/lib/contracts/searchTypes";

interface SearchResultItemProps {
    result: SearchResult;
}

export function SearchResultItem({ result }: SearchResultItemProps) {
    // 构造跳转链接（根据 api.md 契约）
    // User Requirement: Skip detail page, go directly to results
    const href = result.chapterId
        ? `/projects/${result.projectId}/results?chapterId=${result.chapterId}`
        : `/projects/${result.projectId}/results`;

    return (
        <Link
            href={href}
            className="block border-b border-stone-100 bg-white p-4 transition-colors hover:bg-stone-50"
        >
            <div className="flex flex-col gap-1">
                <div className="flex items-center gap-2">
                    <span className="rounded-md bg-stone-100 px-2 py-0.5 text-xs font-medium text-stone-600 uppercase">
                        {result.chapterId ? "章节" : "项目"}
                    </span>
                    <h3 className="text-base font-semibold text-stone-900">
                        项目 ID: {result.projectId}
                    </h3>
                </div>

                {result.chapterId && (
                    <p className="text-sm text-stone-500">
                        章节 ID: {result.chapterId}
                    </p>
                )}
            </div>
        </Link>
    );
}
