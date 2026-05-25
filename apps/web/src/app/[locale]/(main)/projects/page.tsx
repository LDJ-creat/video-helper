"use client";

import {
    useProjects,
    useDeleteProject,
    usePatchProjectCategory,
    useBatchUpdateProjectCategory,
} from "@/lib/api/projectQueries";
import { useCategories } from "@/lib/api/categoryQueries";
import { CategoryManageDialog } from "@/components/features/categories/CategoryManageDialog";
import { CategoryPicker } from "@/components/features/categories/CategoryPicker";
import { ProjectCard } from "@/components/features/projects/ProjectCard";
import { ProjectGridSkeleton } from "@/components/features/projects/ProjectGridSkeleton";
import { ProjectsGridSpinner } from "@/components/features/projects/ProjectsGridSpinner";
import { ProjectsEmptyState } from "@/components/features/projects/ProjectsEmptyState";
import { getCategoryDisplayName } from "@/lib/categories/displayName";
import { useCreateCategory } from "@/lib/api/categoryQueries";
import Link from "next/link";
import { useState } from "react";
import { Plus } from "lucide-react";
import { SearchInput } from "@/components/features/search/SearchInput";
import { SearchResults } from "@/components/features/search/SearchResults";
import { useSearch } from "@/lib/api/searchQueries";
import { useTranslations } from "next-intl";
import { toast } from "sonner";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";

export default function ProjectsPage() {
    const t = useTranslations("Projects");
    const [searchQuery, setSearchQuery] = useState("");
    const [selectedCategoryId, setSelectedCategoryId] = useState<string | null>(null);
    const [batchMode, setBatchMode] = useState(false);
    const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
    const [manageOpen, setManageOpen] = useState(false);
    const [quickAddOpen, setQuickAddOpen] = useState(false);
    const [quickAddName, setQuickAddName] = useState("");
    const [moveMenuProjectId, setMoveMenuProjectId] = useState<string | null>(null);
    const [deleteTarget, setDeleteTarget] = useState<{
        projectId: string;
        title: string;
    } | null>(null);

    const searchResult = useSearch(searchQuery);
    const { data: categories } = useCategories();
    const createCategoryMutation = useCreateCategory();

    const {
        data: projectsData,
        fetchNextPage,
        hasNextPage,
        isFetchingNextPage,
        isLoading,
        isFetching,
        isPlaceholderData,
        error,
    } = useProjects(selectedCategoryId);

    const projects = projectsData?.pages.flatMap((page) => page.items) ?? [];

    const isSearchActive = searchQuery.trim().length > 0;
    const isListFetching = isFetching && !isFetchingNextPage;
    const showInitialSkeleton = !isSearchActive && isLoading && !projectsData;
    const isListRefreshing =
        !isSearchActive && isListFetching && !isLoading && projects.length > 0;
    const showTabLoadingSpinner =
        !isSearchActive &&
        isListFetching &&
        projects.length === 0 &&
        (isPlaceholderData || !projectsData);

    const deleteMutation = useDeleteProject();
    const patchCategoryMutation = usePatchProjectCategory();
    const batchMutation = useBatchUpdateProjectCategory();

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

    const requestDelete = (
        e: React.MouseEvent,
        projectId: string,
        projectTitle: string
    ) => {
        e.preventDefault();
        e.stopPropagation();
        setDeleteTarget({ projectId, title: projectTitle });
        setMoveMenuProjectId(null);
    };

    const confirmDelete = async () => {
        if (!deleteTarget) return;
        try {
            await deleteMutation.mutateAsync(deleteTarget.projectId);
            setDeleteTarget(null);
        } catch (err) {
            toast.error(getDeleteErrorMessage(err));
        }
    };

    const toggleSelect = (projectId: string) => {
        setSelectedIds((prev) => {
            const next = new Set(prev);
            if (next.has(projectId)) next.delete(projectId);
            else next.add(projectId);
            return next;
        });
    };

    const handleMoveOne = async (projectId: string, categoryId: string) => {
        try {
            await patchCategoryMutation.mutateAsync({ projectId, categoryId });
            setMoveMenuProjectId(null);
        } catch {
            // api client surfaces errors
        }
    };

    const handleBatchMove = async (categoryId: string) => {
        if (selectedIds.size === 0) return;
        try {
            await batchMutation.mutateAsync({
                projectIds: Array.from(selectedIds),
                categoryId,
            });
            setSelectedIds(new Set());
            setBatchMode(false);
        } catch {
            // api client surfaces errors
        }
    };

    const handleQuickAddCategory = async () => {
        const name = quickAddName.trim();
        if (!name) return;
        try {
            const created = await createCategoryMutation.mutateAsync({ name });
            setSelectedCategoryId(created.categoryId);
            setQuickAddName("");
            setQuickAddOpen(false);
        } catch {
            // errors via API envelope
        }
    };

    const selectedCategory = (categories ?? []).find(
        (c) => c.categoryId === selectedCategoryId
    );
    const selectedCategoryLabel = selectedCategory
        ? getCategoryDisplayName(selectedCategory, t("defaultCategory"))
        : null;

    const cardLabels = {
        untitled: t("untitled"),
        updated: t("updated"),
        viewResults: t("viewResults"),
        moveTo: t("moveToCategory"),
        deleteTitle: "",
    };
    const sourceTypeLabels = {
        youtube: t("sourceTypes.youtube"),
        bilibili: t("sourceTypes.bilibili"),
        url: t("sourceTypes.link"),
        upload: t("sourceTypes.upload"),
    };

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
                <div className="flex flex-wrap items-center gap-3">
                    <button
                        type="button"
                        onClick={() => setManageOpen(true)}
                        className="rounded-xl border border-stone-200 px-4 py-2.5 text-base font-medium text-stone-700 transition-colors hover:bg-stone-50"
                    >
                        {t("manageCategories")}
                    </button>
                    <button
                        type="button"
                        onClick={() => {
                            setBatchMode((v) => !v);
                            setSelectedIds(new Set());
                        }}
                        className="rounded-xl border border-stone-200 px-4 py-2.5 text-base font-medium text-stone-700 transition-colors hover:bg-stone-50"
                    >
                        {batchMode ? t("batch.cancel") : t("batch.select")}
                    </button>
                    <div className="w-full sm:w-80 2xl:w-[28rem]">
                        <SearchInput
                            size="lg"
                            value={searchQuery}
                            onValueChange={setSearchQuery}
                            onSearch={setSearchQuery}
                            placeholder={t("searchPlaceholder")}
                            clearLabel={t("searchClear")}
                        />
                    </div>
                </div>
            </div>

            {isSearchActive ? (
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
                        cardLabels={{
                            untitled: t("untitled"),
                            updated: t("updated"),
                            viewResults: t("viewResults"),
                            moveTo: t("moveToCategory"),
                            deleteTitle: t("deleteConfirm", { title: "" }),
                        }}
                        defaultCategoryLabel={t("defaultCategory")}
                        sourceTypeLabels={sourceTypeLabels}
                    />
                </div>
            ) : (
                <>
                    <div className="flex flex-wrap items-center gap-2.5 border-b border-stone-100 pb-5">
                        <CategoryTab
                            active={selectedCategoryId === null}
                            label={t("tabs.all")}
                            onClick={() => setSelectedCategoryId(null)}
                        />
                        {(categories ?? []).map((cat) => (
                            <CategoryTab
                                key={cat.categoryId}
                                active={selectedCategoryId === cat.categoryId}
                                label={getCategoryDisplayName(cat, t("defaultCategory"))}
                                count={cat.projectCount}
                                onClick={() => setSelectedCategoryId(cat.categoryId)}
                            />
                        ))}
                        {quickAddOpen ? (
                            <div className="flex items-center gap-1.5">
                                <input
                                    type="text"
                                    maxLength={32}
                                    value={quickAddName}
                                    onChange={(e) => setQuickAddName(e.target.value)}
                                    onKeyDown={(e) => {
                                        if (e.key === "Enter") {
                                            e.preventDefault();
                                            handleQuickAddCategory();
                                        }
                                        if (e.key === "Escape") {
                                            setQuickAddOpen(false);
                                            setQuickAddName("");
                                        }
                                    }}
                                    placeholder={t("categories.newPlaceholder")}
                                    className="w-32 rounded-full border border-stone-200 px-4 py-2 text-base sm:w-40"
                                    autoFocus
                                />
                                <button
                                    type="button"
                                    disabled={createCategoryMutation.isPending || !quickAddName.trim()}
                                    onClick={handleQuickAddCategory}
                                    className="rounded-full bg-stone-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
                                >
                                    {t("categories.add")}
                                </button>
                            </div>
                        ) : (
                            <button
                                type="button"
                                onClick={() => setQuickAddOpen(true)}
                                className="inline-flex items-center gap-1.5 rounded-full border border-dashed border-stone-300 px-4 py-2 text-base font-medium text-stone-600 hover:border-stone-400 hover:bg-stone-50"
                            >
                                <Plus className="h-4 w-4" />
                                {t("addCategoryTab")}
                            </button>
                        )}
                    </div>

                    {batchMode && selectedIds.size > 0 && (
                        <BatchMoveBar
                            count={selectedIds.size}
                            categories={categories ?? []}
                            defaultLabel={t("defaultCategory")}
                            moving={batchMutation.isPending}
                            onMove={handleBatchMove}
                            labels={{
                                selected: t("batch.selected", { count: selectedIds.size }),
                                moveTo: t("batch.moveTo"),
                                moving: t("batch.moving"),
                            }}
                        />
                    )}

                    <div className="relative min-h-[320px] sm:min-h-[400px]">
                    {error ? (
                        <div className="rounded-lg bg-red-50 p-4 text-red-600">
                            {t("loading")} {String(error)}
                        </div>
                    ) : showInitialSkeleton ? (
                        <ProjectGridSkeleton />
                    ) : showTabLoadingSpinner ? (
                        <ProjectsGridSpinner />
                    ) : projects.length === 0 ? (
                        <ProjectsEmptyState
                            title={
                                selectedCategoryId
                                    ? t("emptyInCategoryTitle")
                                    : t("emptyAllTitle")
                            }
                            description={
                                selectedCategoryId
                                    ? t("emptyInCategoryDesc")
                                    : t("emptyAllDesc")
                            }
                            categoryHint={
                                selectedCategoryLabel
                                    ? t("emptyInCategoryHint") + `：${selectedCategoryLabel}`
                                    : undefined
                            }
                            actionLabel={t("createFirst")}
                            categoryId={selectedCategoryId}
                        />
                    ) : (
                        <div
                            className={`relative transition-opacity duration-200 ease-out ${
                                isListRefreshing ? "opacity-55" : "opacity-100"
                            }`}
                        >
                        <div className="grid gap-6 2xl:gap-10 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                            {projects.map((project) => (
                                <ProjectCard
                                    key={project.projectId}
                                    project={project}
                                    batchMode={batchMode}
                                    selected={selectedIds.has(project.projectId)}
                                    moveMenuOpen={moveMenuProjectId === project.projectId}
                                    categories={categories ?? []}
                                    defaultCategoryLabel={t("defaultCategory")}
                                    sourceTypeLabels={sourceTypeLabels}
                                    labels={{
                                        ...cardLabels,
                                        deleteTitle: t("deleteDialogTitle"),
                                    }}
                                    onToggleSelect={() => toggleSelect(project.projectId)}
                                    onDelete={(e) =>
                                        requestDelete(
                                            e,
                                            project.projectId,
                                            project.title || t("untitled")
                                        )
                                    }
                                    onOpenMoveMenu={(e) => {
                                        e.preventDefault();
                                        e.stopPropagation();
                                        setMoveMenuProjectId(
                                            moveMenuProjectId === project.projectId ? null : project.projectId
                                        );
                                    }}
                                    onMove={(categoryId) => handleMoveOne(project.projectId, categoryId)}
                                />
                            ))}
                        </div>
                        {isListRefreshing && (
                            <div
                                className="pointer-events-none absolute inset-0 z-10 flex items-start justify-center pt-24"
                                aria-hidden
                            >
                                <div className="h-8 w-8 animate-spin rounded-full border-2 border-stone-200 border-t-stone-700 bg-white/80 p-0.5 shadow-sm" />
                            </div>
                        )}
                        </div>
                    )}

                    {hasNextPage && !showInitialSkeleton && !showTabLoadingSpinner && (
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
                    </div>
                </>
            )}

            <CategoryManageDialog open={manageOpen} onClose={() => setManageOpen(false)} />

            <ConfirmDialog
                open={deleteTarget !== null}
                onClose={() => {
                    if (!deleteMutation.isPending) setDeleteTarget(null);
                }}
                onConfirm={confirmDelete}
                title={t("deleteDialogTitle")}
                description={t("deleteDialogDesc")}
                highlight={deleteTarget?.title}
                confirmLabel={
                    deleteMutation.isPending ? t("deleting") : t("deleteDialogConfirm")
                }
                cancelLabel={t("deleteDialogCancel")}
                loading={deleteMutation.isPending}
                variant="danger"
            />
        </main>
    );
}

function CategoryTab({
    active,
    label,
    count,
    onClick,
}: {
    active: boolean;
    label: string;
    count?: number;
    onClick: () => void;
}) {
    return (
        <button
            type="button"
            onClick={onClick}
            className={`rounded-full px-5 py-2 text-base font-medium transition-colors ${
                active
                    ? "bg-stone-900 text-white"
                    : "bg-stone-100 text-stone-600 hover:bg-stone-200"
            }`}
        >
            {label}
            {count !== undefined ? ` (${count})` : ""}
        </button>
    );
}

function BatchMoveBar({
    count,
    categories,
    defaultLabel,
    moving,
    onMove,
    labels,
}: {
    count: number;
    categories: { categoryId: string; name: string; slug: string }[];
    defaultLabel: string;
    moving: boolean;
    onMove: (categoryId: string) => void;
    labels: { selected: string; moveTo: string; moving: string };
}) {
    return (
        <div className="sticky top-4 z-10 flex flex-wrap items-center gap-3 rounded-xl border border-stone-200 bg-white p-4 shadow-md">
            <span className="text-base font-medium text-stone-700">{labels.selected}</span>
            <CategoryPicker
                categories={categories}
                defaultCategoryLabel={defaultLabel}
                placeholder={labels.moveTo}
                onSelect={onMove}
                disabled={moving}
            />
            {moving && <span className="text-sm text-stone-500">{labels.moving}</span>}
        </div>
    );
}

