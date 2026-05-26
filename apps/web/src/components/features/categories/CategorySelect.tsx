"use client";

import { useCategories, useCreateCategory } from "@/lib/api/categoryQueries";
import { getCategoryDisplayName } from "@/lib/categories/displayName";
import { logIngestCategory } from "@/lib/categories/ingestCategoryDebug";
import { useTranslations } from "next-intl";
import { useEffect, useMemo, useRef, useState } from "react";
import { ChevronDown, Check, Plus } from "lucide-react";

type CategorySelectProps = {
  value: string | null;
  onChange: (categoryId: string) => void;
  className?: string;
  /** Pre-select when navigating from projects page (?categoryId=) */
  presetCategoryId?: string | null;
};

export function CategorySelect({
  value,
  onChange,
  className,
  presetCategoryId,
}: CategorySelectProps) {
  const t = useTranslations("Ingest");
  const tProj = useTranslations("Projects");
  const { data: categories, isLoading } = useCategories();
  const createMutation = useCreateCategory();
  const [showNew, setShowNew] = useState(false);
  const [newName, setNewName] = useState("");
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const initializedRef = useRef(false);

  const defaultCategory = useMemo(
    () => categories?.find((c) => c.slug === "default"),
    [categories]
  );

  const presetTrimmed = presetCategoryId?.trim() || null;

  const selectedId = value ?? defaultCategory?.categoryId ?? "";
  const selectedCat = categories?.find((c) => c.categoryId === selectedId);

  // Single initialization: preset from URL wins over default (never overwrite existing value).
  useEffect(() => {
    if (!categories?.length || initializedRef.current) return;

    if (value) {
      initializedRef.current = true;
      logIngestCategory("skip-init-already-has-value", { value });
      return;
    }

    const presetValid =
      presetTrimmed &&
      categories.some((c) => c.categoryId === presetTrimmed);

    if (presetTrimmed && !presetValid) {
      logIngestCategory("preset-invalid", {
        presetCategoryId: presetTrimmed,
        knownIds: categories.map((c) => c.categoryId),
      });
    }

    const nextId = presetValid
      ? presetTrimmed
      : defaultCategory?.categoryId;

    if (nextId) {
      logIngestCategory("init-category", {
        nextId,
        source: presetValid ? "url-preset" : "default",
        presetCategoryId: presetTrimmed,
      });
      onChange(nextId);
      initializedRef.current = true;
    }
  }, [categories, presetTrimmed, defaultCategory, value, onChange]);

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

  const handleCreate = async () => {
    const name = newName.trim();
    if (!name) return;
    try {
      const created = await createMutation.mutateAsync({ name });
      onChange(created.categoryId);
      setNewName("");
      setShowNew(false);
      setOpen(false);
    } catch {
      // error surfaced by mutation
    }
  };

  if (isLoading) {
    return (
      <div className={`h-12 animate-pulse rounded-xl bg-stone-100 ${className ?? ""}`} />
    );
  }

  return (
    <div className={`space-y-3 ${className ?? ""}`} ref={rootRef}>
      <label className="block text-sm font-medium text-stone-700 xl:text-base">
        {t("categoryLabel")}
      </label>
      <div className="flex gap-2">
        <div className="relative min-w-0 flex-1">
          <button
            type="button"
            onClick={() => setOpen((v) => !v)}
            className={`flex w-full items-center justify-between gap-2 rounded-xl border border-stone-200 bg-white px-4 py-3 text-left text-sm text-stone-900 shadow-sm transition-colors hover:border-stone-300 focus:border-stone-400 focus:outline-none focus:ring-2 focus:ring-stone-200 xl:text-base ${
              open ? "rounded-b-none border-b-transparent" : ""
            }`}
            aria-expanded={open}
            aria-haspopup="listbox"
          >
            <span className="truncate">
              {selectedCat
                ? getCategoryDisplayName(selectedCat, tProj("defaultCategory"))
                : tProj("defaultCategory")}
            </span>
            <ChevronDown
              className={`h-4 w-4 shrink-0 text-stone-400 transition-transform ${open ? "rotate-180" : ""}`}
            />
          </button>
          {open && (
            <ul
              role="listbox"
              className="absolute left-0 right-0 top-full z-30 max-h-56 overflow-auto rounded-b-xl border border-t-0 border-stone-200 bg-white py-1 shadow-lg"
            >
              {(categories ?? []).map((cat) => {
                const isSelected = cat.categoryId === selectedId;
                return (
                  <li key={cat.categoryId} role="option" aria-selected={isSelected}>
                    <button
                      type="button"
                      className={`flex w-full items-center justify-between px-4 py-2.5 text-left text-sm transition-colors hover:bg-stone-50 xl:text-base ${
                        isSelected ? "bg-stone-50 font-medium text-stone-900" : "text-stone-700"
                      }`}
                      onClick={() => {
                        onChange(cat.categoryId);
                        setOpen(false);
                      }}
                    >
                      {getCategoryDisplayName(cat, tProj("defaultCategory"))}
                      {isSelected ? <Check className="h-4 w-4 text-stone-600" /> : null}
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
        <button
          type="button"
          onClick={() => setShowNew((v) => !v)}
          className="inline-flex shrink-0 items-center gap-1.5 rounded-xl border border-stone-200 bg-white px-4 py-3 text-sm font-medium text-stone-700 shadow-sm hover:bg-stone-50 xl:text-base"
        >
          <Plus className="h-4 w-4" />
          {t("createCategoryShort")}
        </button>
      </div>
      {showNew && (
        <div className="flex gap-2 rounded-xl border border-stone-100 bg-stone-50/80 p-3">
          <input
            type="text"
            maxLength={32}
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            placeholder={t("newCategoryPlaceholder")}
            className="flex-1 rounded-lg border border-stone-200 bg-white px-3 py-2.5 text-sm focus:border-stone-400 focus:outline-none focus:ring-1 focus:ring-stone-300"
          />
          <button
            type="button"
            disabled={createMutation.isPending || !newName.trim()}
            onClick={handleCreate}
            className="rounded-lg bg-stone-900 px-4 py-2.5 text-sm font-medium text-white disabled:opacity-50"
          >
            {t("addCategory")}
          </button>
        </div>
      )}
    </div>
  );
}
