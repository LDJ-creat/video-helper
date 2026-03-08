"use client";

import { useProjects, useDeleteProject } from "@/lib/api/projectQueries";
import Link from "next/link";
import { useState } from "react";
import { SearchInput } from "@/components/features/search/SearchInput";
import { SearchResults } from "@/components/features/search/SearchResults";
import { useSearch } from "@/lib/api/searchQueries";
import { useTranslations } from "next-intl";

export default function ProjectsPage() {
    const t = useTranslations("Projects");
    const [searchQuery, setSearchQuery] = useState("");

    // Search Query
    const searchResult = useSearch(searchQuery);

    // Projects Query (for default view)
    const {
        data: projectsData,
        fetchNextPage,
        hasNextPage,
        isFetchingNextPage,
        isLoading,
        error
    } = useProjects();

    const deleteMutation = useDeleteProject();

    const getDeleteErrorMessage = (err: unknown): string => {
        if (err && typeof err === "object" && "error" in err) {
            const envelope = err as { error?: { message?: string } };
            return envelope.error?.message || t("deleteFailed");
        }
        if (err instanceof Error) {
            return err.message || t("deleteFailed");
        }
        return t("deleteFailed");
    };

    const handleDelete = async (e: React.MouseEvent, projectId: string, projectTitle: string) => {
        e.preventDefault(); // Prevent navigation
        const confirmed = window.confirm(t("deleteConfirm", { title: projectTitle }));
        if (!confirmed) return;

        try {
            await deleteMutation.mutateAsync(projectId);
        } catch (err) {
            alert(getDeleteErrorMessage(err));
        }
    };

    if (isLoading) {
        return (
            <main className="mx-auto w-full max-w-[1800px] p-6 sm:p-10">
                <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
                    {[1, 2, 3].map((i) => (
                        <div key={i} className="h-48 animate-pulse rounded-xl bg-stone-100" />
                    ))}
                </div>
            </main>
        );
    }

    if (error) {
        return (
            <main className="mx-auto w-full max-w-[1800px] p-6 sm:p-10">
                <div className="rounded-lg bg-red-50 p-4 text-red-600">
                    {t("loading")} {String(error)}
                </div>
            </main>
        );
    }

    const projects = projectsData?.pages.flatMap((page) => page.items) ?? [];

    return (
        <main className="mx-auto w-full max-w-[1800px] space-y-8 p-6 sm:p-10">
            <div className="flex flex-col gap-6 sm:flex-row sm:items-center sm:justify-between">
                <div>
                    <h1 className="text-3xl 2xl:text-5xl font-bold tracking-tight text-stone-900">
                        {t("title")}
                    </h1>
                    <p className="mt-2 text-stone-600 2xl:text-xl 2xl:mt-4">
                        {t("subtitle")}
                    </p>
                </div>
                <div className="w-full sm:w-72 2xl:w-96">
                    <SearchInput
                        onSearch={setSearchQuery}
                        placeholder={t("searchPlaceholder")}
                    />
                </div>
            </div>

            {searchQuery ? (
                // Search Mode
                <div className="animate-in fade-in slide-in-from-bottom-2">
                    <h2 className="mb-4 text-lg font-medium text-stone-700">{t("searchResults")}</h2>
                    <SearchResults
                        data={searchResult.data}
                        isLoading={searchResult.isLoading}
                        isError={searchResult.isError}
                        error={searchResult.error}
                        hasNextPage={searchResult.hasNextPage}
                        isFetchingNextPage={searchResult.isFetchingNextPage}
                        fetchNextPage={searchResult.fetchNextPage}
                    />
                </div>
            ) : (
                // List Mode
                <>
                    {projects.length === 0 ? (
                        <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-stone-200 bg-stone-50 py-20 text-center">
                            <p className="text-lg font-medium text-stone-500">{t("noProjects")}</p>
                            <Link
                                href="/ingest"
                                className="mt-4 text-sm font-medium text-stone-900 underline underline-offset-4 hover:text-stone-700"
                            >
                                {t("createFirst")}
                            </Link>
                        </div>
                    ) : (
                        <div className="grid gap-6 2xl:gap-10 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                            {projects.map((project) => (
                                <Link
                                    key={project.projectId}
                                    href={`/projects/${project.projectId}/results`}
                                    className="group relative flex flex-col justify-between overflow-hidden rounded-xl 2xl:rounded-2xl border border-stone-200 bg-white p-6 2xl:p-8 shadow-sm transition-all hover:border-stone-300 hover:shadow-md active:scale-[0.99]"
                                >
                                    <div className="space-y-4 2xl:space-y-6">
                                        <div className="flex items-start justify-between">
                                            <div className={`rounded-full px-2.5 py-0.5 2xl:px-4 2xl:py-1 text-xs 2xl:text-sm font-medium ${project.sourceType === 'youtube' ? 'bg-red-50 text-red-700' :
                                                project.sourceType === 'bilibili' ? 'bg-pink-50 text-pink-700' :
                                                    project.sourceType === 'url' ? 'bg-blue-50 text-blue-700' :
                                                        'bg-blue-50 text-blue-700'
                                                }`}>
                                                {project.sourceType === 'youtube' ? t("sourceTypes.youtube") :
                                                    project.sourceType === 'bilibili' ? t("sourceTypes.bilibili") :
                                                        project.sourceType === 'url' ? t("sourceTypes.link") : t("sourceTypes.upload")}
                                            </div>
                                            <button
                                                onClick={(e) => handleDelete(e, project.projectId, project.title)}
                                                className="opacity-0 transition-opacity group-hover:opacity-100 p-1 text-stone-400 hover:text-red-600"
                                                title={t("deleteConfirm", { title: project.title })}
                                            >
                                                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-5 h-5">
                                                    <path fillRule="evenodd" d="M8.75 1A2.75 2.75 0 006 3.75v.443c-.795.077-1.584.176-2.365.298a.75.75 0 10.23 1.482l.149-.022.841 10.518A2.75 2.75 0 007.596 19h4.807a2.75 2.75 0 002.742-2.53l.841-10.52.149.023a.75.75 0 00.23-1.482A41.03 41.03 0 0014 4.193V3.75A2.75 2.75 0 0011.25 1h-2.5zM10 4c.84 0 1.673.025 2.5.075V3.75c0-.69-.56-1.25-1.25-1.25h-2.5c-.69 0-1.25.56-1.25 1.25v.325C8.327 4.025 9.16 4 10 4zM8.58 7.72a.75.75 0 00-1.5.06l.3 7.5a.75.75 0 101.5-.06l-.3-7.5zm4.34.06a.75.75 0 10-1.5-.06l-.3 7.5a.75.75 0 101.5.06l.3-7.5z" clipRule="evenodd" />
                                                </svg>
                                            </button>
                                        </div>

                                        <div>
                                            <h3 className="font-semibold text-stone-900 line-clamp-2 leading-relaxed text-base 2xl:text-2xl">
                                                {project.title || t("untitled")}
                                            </h3>
                                            <p className="mt-2 2xl:mt-4 text-xs 2xl:text-sm text-stone-500 font-mono">
                                                {t("updated")} {new Date(project.updatedAtMs).toLocaleDateString()}
                                            </p>
                                        </div>
                                    </div>

                                    <div className="mt-6 2xl:mt-10 flex items-center text-sm 2xl:text-lg font-medium text-stone-900 opacity-60 transition-opacity group-hover:opacity-100">
                                        {t("viewResults")}
                                        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4 2xl:w-6 2xl:h-6 ml-1 2xl:ml-2">
                                            <path fillRule="evenodd" d="M3 10a.75.75 0 01.75-.75h10.638L10.23 5.29a.75.75 0 111.04-1.08l5.5 5.25a.75.75 0 010 1.08l-5.5 5.25a.75.75 0 11-1.04-1.08l4.158-3.96H3.75A.75.75 0 013 10z" clipRule="evenodd" />
                                        </svg>
                                    </div>
                                </Link>
                            ))}
                        </div>
                    )}

                    {hasNextPage && (
                        <div className="mt-8 text-center bg-stone-50 p-4 rounded-xl border border-dashed border-stone-200">
                            <button
                                onClick={() => fetchNextPage()}
                                disabled={isFetchingNextPage}
                                className="px-6 py-2 text-sm font-medium text-stone-600 hover:text-stone-900 disabled:opacity-50"
                            >
                                {isFetchingNextPage ? t("loading") : t("loadMore")}
                            </button>
                        </div>
                    )}
                </>
            )}
        </main>
    );
}
