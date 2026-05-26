"use client";

import { Fragment } from "react";
import type { InfiniteData } from "@tanstack/react-query";
import type { SearchResponse } from "@/lib/contracts/searchTypes";
import { searchResultToProject } from "@/lib/contracts/searchTypes";
import { useTranslations } from "next-intl";
import { ProjectCard, type ProjectCardLabels } from "@/components/features/projects/ProjectCard";
import { ProjectGridSkeleton } from "@/components/features/projects/ProjectGridSkeleton";

interface SearchResultsProps {
    data: InfiniteData<SearchResponse> | undefined;
    isLoading: boolean;
    isError: boolean;
    error: Error | null;
    hasNextPage: boolean;
    isFetchingNextPage: boolean;
    fetchNextPage: () => void;
    cardLabels: ProjectCardLabels;
    defaultCategoryLabel: string;
    sourceTypeLabels: Record<string, string>;
}

export function SearchResults({
    data,
    isLoading,
    isError,
    error,
    hasNextPage,
    isFetchingNextPage,
    fetchNextPage,
    cardLabels,
    defaultCategoryLabel,
    sourceTypeLabels,
}: SearchResultsProps) {
    const t = useTranslations("Search");

    if (isLoading) {
        return <ProjectGridSkeleton count={6} />;
    }

    if (isError) {
        return (
            <div className="rounded-xl border border-red-100 bg-red-50 px-6 py-10 text-center text-base text-red-600">
                {t("failed")}: {error?.message || t("unknownError")}
            </div>
        );
    }

    const allResults = data?.pages.flatMap((page) => page.items) ?? [];

    if (allResults.length === 0) {
        return (
            <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-stone-200 bg-stone-50 px-8 py-16 text-center">
                <p className="text-lg font-semibold text-stone-600">{t("noResults")}</p>
                <p className="mt-2 text-base text-stone-500">{t("tryOther")}</p>
            </div>
        );
    }

    return (
        <div className="w-full space-y-6">
            <div className="grid gap-6 2xl:gap-10 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                {data?.pages.map((page, pageIndex) => (
                    <Fragment key={pageIndex}>
                        {page.items.map((result) => (
                            <ProjectCard
                                key={result.projectId}
                                project={searchResultToProject(result)}
                                defaultCategoryLabel={defaultCategoryLabel}
                                sourceTypeLabels={sourceTypeLabels}
                                labels={cardLabels}
                                readOnly
                            />
                        ))}
                    </Fragment>
                ))}
            </div>

            {hasNextPage && (
                <div className="text-center">
                    <button
                        type="button"
                        onClick={fetchNextPage}
                        disabled={isFetchingNextPage}
                        className="rounded-lg border border-stone-200 bg-white px-6 py-2.5 text-sm font-medium text-stone-700 transition-colors hover:bg-stone-50 disabled:opacity-50"
                    >
                        {isFetchingNextPage ? t("loadingMore") : t("loadMore")}
                    </button>
                </div>
            )}
        </div>
    );
}
