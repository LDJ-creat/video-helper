"use client";

import { Link } from "@/i18n/navigation";
import { FolderOpen, Plus } from "lucide-react";

type ProjectsEmptyStateProps = {
    title: string;
    description: string;
    actionLabel: string;
    /** Target ingest route; categoryId is passed as query when set */
    categoryId?: string | null;
    categoryHint?: string;
};

export function ProjectsEmptyState({
    title,
    description,
    actionLabel,
    categoryId,
    categoryHint,
}: ProjectsEmptyStateProps) {
    const ingestHref =
        categoryId != null && categoryId !== ""
            ? { pathname: "/ingest" as const, query: { categoryId } }
            : "/ingest";

    return (
        <div className="flex flex-col items-center justify-center rounded-2xl border border-stone-200/80 bg-gradient-to-b from-stone-50 to-white px-8 py-16 sm:py-24 text-center shadow-sm">
            <div className="mb-6 flex h-16 w-16 items-center justify-center rounded-2xl bg-stone-100 text-stone-500 sm:h-20 sm:w-20">
                <FolderOpen className="h-8 w-8 sm:h-10 sm:w-10" strokeWidth={1.5} />
            </div>
            <h2 className="text-xl font-semibold tracking-tight text-stone-900 sm:text-2xl">
                {title}
            </h2>
            <p className="mt-3 max-w-md text-base leading-relaxed text-stone-600 sm:text-lg">
                {description}
            </p>
            {categoryHint ? (
                <p className="mt-2 text-sm text-stone-500">{categoryHint}</p>
            ) : null}
            <Link
                href={ingestHref}
                className="mt-8 inline-flex items-center gap-2 rounded-xl bg-stone-900 px-6 py-3 text-base font-medium text-white shadow-sm transition-all hover:bg-stone-800 hover:shadow-md active:scale-[0.98] sm:px-8 sm:py-3.5 sm:text-lg"
            >
                <Plus className="h-5 w-5" />
                {actionLabel}
            </Link>
        </div>
    );
}
