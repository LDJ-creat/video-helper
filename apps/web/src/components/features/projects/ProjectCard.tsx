"use client";

import Link from "next/link";
import { useEffect } from "react";
import { FolderInput, Trash2 } from "lucide-react";
import type { Project } from "@/lib/contracts/projectTypes";
import { getCategoryDisplayName, getProjectCategoryDisplayName } from "@/lib/categories/displayName";
import { CategoryOptionList } from "@/components/features/categories/CategoryOptionList";
import {
    TitleHoverTooltip,
    useTitleHoverTooltip,
} from "@/components/ui/TitleHoverTooltip";

export type ProjectCardLabels = {
    untitled: string;
    updated: string;
    viewResults: string;
    moveTo: string;
    deleteTitle: string;
};

export type ProjectCardProps = {
    project: Project;
    batchMode?: boolean;
    selected?: boolean;
    moveMenuOpen?: boolean;
    categories?: { categoryId: string; name: string; slug: string }[];
    defaultCategoryLabel: string;
    sourceTypeLabels: Record<string, string>;
    labels: ProjectCardLabels;
    onToggleSelect?: () => void;
    onDelete?: (e: React.MouseEvent) => void;
    onOpenMoveMenu?: (e: React.MouseEvent) => void;
    onMove?: (categoryId: string) => void;
    /** Hide move/delete actions (e.g. search results) */
    readOnly?: boolean;
};

export function ProjectCard({
    project,
    batchMode = false,
    selected = false,
    moveMenuOpen = false,
    categories = [],
    defaultCategoryLabel,
    sourceTypeLabels,
    labels,
    onToggleSelect,
    onDelete,
    onOpenMoveMenu,
    onMove,
    readOnly = false,
}: ProjectCardProps) {
    const displayTitle = project.title || labels.untitled;
    const { titleRef, titleHoverHandlers, dismiss, portal } =
        useTitleHoverTooltip(displayTitle);

    useEffect(() => {
        if (moveMenuOpen) dismiss();
    }, [moveMenuOpen, dismiss]);

    const categoryLabel = getProjectCategoryDisplayName(project, defaultCategoryLabel);
    const sourceLabel =
        project.sourceType === "youtube"
            ? sourceTypeLabels.youtube
            : project.sourceType === "bilibili"
              ? sourceTypeLabels.bilibili
              : project.sourceType === "url"
                ? sourceTypeLabels.url
                : sourceTypeLabels.upload;

    const cardInner = (
        <div className="space-y-4 2xl:space-y-6">
            <div className="flex items-start justify-between gap-2">
                <div className="flex flex-wrap items-center gap-2">
                    {batchMode && onToggleSelect && (
                        <input
                            type="checkbox"
                            checked={selected}
                            onChange={(e) => {
                                e.stopPropagation();
                                onToggleSelect();
                            }}
                            onClick={(e) => e.stopPropagation()}
                            className="h-4 w-4 rounded border-stone-300"
                        />
                    )}
                    <div
                        className={`rounded-full px-2.5 py-0.5 2xl:px-4 2xl:py-1 text-xs 2xl:text-sm font-medium ${
                            project.sourceType === "youtube"
                                ? "bg-red-50 text-red-700"
                                : project.sourceType === "bilibili"
                                  ? "bg-pink-50 text-pink-700"
                                  : "bg-blue-50 text-blue-700"
                        }`}
                    >
                        {sourceLabel}
                    </div>
                    {categoryLabel && (
                        <span className="rounded-full bg-stone-100 px-2.5 py-0.5 text-xs font-medium text-stone-600">
                            {categoryLabel}
                        </span>
                    )}
                </div>
                {!readOnly && onDelete && onOpenMoveMenu && onMove && (
                    <div
                        className="relative z-20 flex shrink-0 items-center gap-1.5"
                        onMouseEnter={(e) => {
                            e.stopPropagation();
                            dismiss();
                        }}
                        onPointerDown={(e) => e.stopPropagation()}
                    >
                        <button
                            type="button"
                            onClick={onOpenMoveMenu}
                            aria-label={labels.moveTo}
                            aria-expanded={moveMenuOpen}
                            title={labels.moveTo}
                            className={`inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-transparent text-stone-400 transition-all hover:border-stone-100 hover:bg-stone-50 hover:text-stone-700 group-hover:opacity-100 ${
                                moveMenuOpen
                                    ? "opacity-100 bg-stone-50 text-stone-700"
                                    : "opacity-0"
                            }`}
                        >
                            <FolderInput className="h-4 w-4" aria-hidden />
                        </button>
                        <button
                            type="button"
                            onClick={onDelete}
                            aria-label={labels.deleteTitle}
                            title={labels.deleteTitle}
                            className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-transparent text-stone-400 opacity-0 transition-all hover:border-red-100 hover:bg-red-50 hover:text-red-600 group-hover:opacity-100"
                        >
                            <Trash2 className="h-4 w-4" aria-hidden />
                        </button>
                        {moveMenuOpen && (
                            <CategoryOptionList
                                className="absolute right-0 top-full z-30 mt-1.5 min-w-[10rem]"
                                categories={categories}
                                defaultCategoryLabel={defaultCategoryLabel}
                                currentCategoryId={project.categoryId}
                                header={labels.moveTo}
                                onPick={onMove}
                            />
                        )}
                    </div>
                )}
            </div>

            <div>
                <TitleHoverTooltip
                    text={displayTitle}
                    titleRef={titleRef}
                    hoverHandlers={titleHoverHandlers}
                    className="font-semibold text-stone-900 line-clamp-2 leading-relaxed text-base 2xl:text-2xl"
                />
                {project.updatedAtMs ? (
                    <p className="mt-2 2xl:mt-4 text-xs 2xl:text-sm text-stone-500">
                        {labels.updated} {new Date(project.updatedAtMs).toLocaleDateString()}
                    </p>
                ) : null}
            </div>
        </div>
    );

    if (batchMode) {
        return (
            <div
                className={`group relative flex flex-col justify-between overflow-hidden rounded-xl 2xl:rounded-2xl border bg-white p-6 2xl:p-8 shadow-sm ${
                    selected ? "border-stone-800 ring-1 ring-stone-800" : "border-stone-200"
                }`}
            >
                {cardInner}
                {portal}
            </div>
        );
    }

    return (
        <Link
            href={`/projects/${project.projectId}/results`}
            className="group relative flex flex-col justify-between overflow-hidden rounded-xl 2xl:rounded-2xl border border-stone-200 bg-white p-6 2xl:p-8 shadow-sm transition-all hover:border-stone-300 hover:shadow-md active:scale-[0.99]"
        >
            {cardInner}
            {portal}
            <div className="mt-6 2xl:mt-10 flex items-center text-sm 2xl:text-lg font-medium text-stone-900 opacity-60 transition-opacity group-hover:opacity-100">
                {labels.viewResults}
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4 2xl:w-6 2xl:h-6 ml-1 2xl:ml-2">
                    <path
                        fillRule="evenodd"
                        d="M3 10a.75.75 0 01.75-.75h10.638L10.23 5.29a.75.75 0 111.04-1.08l5.5 5.25a.75.75 0 010 1.08l-5.5 5.25a.75.75 0 11-1.04-1.08l4.158-3.96H3.75A.75.75 0 013 10z"
                        clipRule="evenodd"
                    />
                </svg>
            </div>
        </Link>
    );
}
