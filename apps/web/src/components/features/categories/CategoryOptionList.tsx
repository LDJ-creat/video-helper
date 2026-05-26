"use client";

import { getCategoryDisplayName } from "@/lib/categories/displayName";
import { Check } from "lucide-react";
import type { CategoryPickerItem } from "./CategoryPicker";

type CategoryOptionListProps = {
    categories: CategoryPickerItem[];
    defaultCategoryLabel: string;
    currentCategoryId?: string | null;
    onPick: (categoryId: string) => void;
    header?: string;
    className?: string;
};

/** Shared list panel styling (ingest CategorySelect). */
export function CategoryOptionList({
    categories,
    defaultCategoryLabel,
    currentCategoryId,
    onPick,
    header,
    className,
}: CategoryOptionListProps) {
    return (
        <div
            className={`overflow-hidden rounded-xl border border-stone-200 bg-white py-1 shadow-lg ${className ?? ""}`}
            onClick={(e) => e.stopPropagation()}
        >
            {header ? (
                <p className="px-4 py-2 text-xs font-medium text-stone-500">{header}</p>
            ) : null}
            <ul role="listbox" className="max-h-56 overflow-auto">
                {categories.map((cat) => {
                    const isCurrent = cat.categoryId === currentCategoryId;
                    return (
                        <li key={cat.categoryId} role="option" aria-selected={isCurrent}>
                            <button
                                type="button"
                                className={`flex w-full items-center justify-between px-4 py-2.5 text-left text-sm transition-colors hover:bg-stone-50 ${
                                    isCurrent
                                        ? "bg-stone-50 font-medium text-stone-900"
                                        : "text-stone-700"
                                }`}
                                onClick={() => onPick(cat.categoryId)}
                            >
                                {getCategoryDisplayName(cat, defaultCategoryLabel)}
                                {isCurrent ? (
                                    <Check className="h-4 w-4 shrink-0 text-stone-600" />
                                ) : null}
                            </button>
                        </li>
                    );
                })}
            </ul>
        </div>
    );
}
