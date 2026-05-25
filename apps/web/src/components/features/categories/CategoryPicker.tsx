"use client";

import { getCategoryDisplayName } from "@/lib/categories/displayName";
import { ChevronDown, Check } from "lucide-react";
import { useEffect, useRef, useState } from "react";

export type CategoryPickerItem = {
    categoryId: string;
    name: string;
    slug: string;
};

type CategoryPickerProps = {
    categories: CategoryPickerItem[];
    defaultCategoryLabel: string;
    placeholder: string;
    onSelect: (categoryId: string) => void;
    disabled?: boolean;
    className?: string;
};

/**
 * Custom category dropdown (same visual language as ingest CategorySelect).
 */
export function CategoryPicker({
    categories,
    defaultCategoryLabel,
    placeholder,
    onSelect,
    disabled = false,
    className,
}: CategoryPickerProps) {
    const [open, setOpen] = useState(false);
    const [selectedId, setSelectedId] = useState<string | null>(null);
    const rootRef = useRef<HTMLDivElement>(null);

    const selectedCat = categories.find((c) => c.categoryId === selectedId);
    const displayLabel = selectedCat
        ? getCategoryDisplayName(selectedCat, defaultCategoryLabel)
        : placeholder;

    useEffect(() => {
        if (!open) return;
        const onDocClick = (e: MouseEvent) => {
            if (rootRef.current && !rootRef.current.contains(e.target as Node)) {
                setOpen(false);
            }
        };
        document.addEventListener("mousedown", onDocClick);
        return () => document.removeEventListener("mousedown", onDocClick);
    }, [open]);

    const handlePick = (categoryId: string) => {
        onSelect(categoryId);
        setSelectedId(null);
        setOpen(false);
    };

    return (
        <div ref={rootRef} className={`relative min-w-[11rem] sm:min-w-[14rem] ${className ?? ""}`}>
            <button
                type="button"
                disabled={disabled}
                onClick={() => setOpen((v) => !v)}
                className={`flex w-full items-center justify-between gap-2 rounded-xl border border-stone-200 bg-white px-4 py-2.5 text-left text-sm text-stone-900 shadow-sm transition-colors hover:border-stone-300 focus:border-stone-400 focus:outline-none focus:ring-2 focus:ring-stone-200 disabled:cursor-not-allowed disabled:opacity-50 ${
                    open ? "rounded-b-none border-b-transparent" : ""
                }`}
                aria-expanded={open}
                aria-haspopup="listbox"
            >
                <span className={selectedCat ? "text-stone-900" : "text-stone-500"}>
                    {displayLabel}
                </span>
                <ChevronDown
                    className={`h-4 w-4 shrink-0 text-stone-400 transition-transform ${open ? "rotate-180" : ""}`}
                />
            </button>
            {open && (
                <ul
                    role="listbox"
                    className="absolute left-0 right-0 top-full z-40 max-h-56 overflow-auto rounded-b-xl border border-t-0 border-stone-200 bg-white py-1 shadow-lg"
                >
                    {categories.map((cat) => {
                        const isSelected = cat.categoryId === selectedId;
                        return (
                            <li key={cat.categoryId} role="option" aria-selected={isSelected}>
                                <button
                                    type="button"
                                    className={`flex w-full items-center justify-between px-4 py-2.5 text-left text-sm transition-colors hover:bg-stone-50 ${
                                        isSelected
                                            ? "bg-stone-50 font-medium text-stone-900"
                                            : "text-stone-700"
                                    }`}
                                    onClick={() => handlePick(cat.categoryId)}
                                >
                                    {getCategoryDisplayName(cat, defaultCategoryLabel)}
                                    {isSelected ? (
                                        <Check className="h-4 w-4 text-stone-600" />
                                    ) : null}
                                </button>
                            </li>
                        );
                    })}
                </ul>
            )}
        </div>
    );
}
