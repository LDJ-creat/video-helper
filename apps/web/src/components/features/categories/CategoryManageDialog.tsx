"use client";

import {
  useCategories,
  useCreateCategory,
  useDeleteCategory,
  useUpdateCategory,
} from "@/lib/api/categoryQueries";
import { getCategoryDisplayName } from "@/lib/categories/displayName";
import type { ApiErrorEnvelope } from "@/lib/api/apiClient";
import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import { Plus, Trash2, Pencil, X } from "lucide-react";

type CategoryManageDialogProps = {
  open: boolean;
  onClose: () => void;
};

export function CategoryManageDialog({ open, onClose }: CategoryManageDialogProps) {
  const t = useTranslations("Projects.categories");
  const tProj = useTranslations("Projects");
  const { data: categories } = useCategories();
  const createMutation = useCreateCategory();
  const updateMutation = useUpdateCategory();
  const deleteMutation = useDeleteCategory();
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editName, setEditName] = useState("");
  const [newName, setNewName] = useState("");
  const [createError, setCreateError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  const getDeleteError = (err: unknown): string => {
    if (err && typeof err === "object" && "error" in err) {
      const envelope = err as ApiErrorEnvelope;
      if (envelope.error?.code === "CATEGORY_IN_USE") {
        return t("deleteInUse");
      }
      return envelope.error?.message || t("deleteFailed");
    }
    return t("deleteFailed");
  };

  const getCreateError = (err: unknown): string => {
    if (err && typeof err === "object" && "error" in err) {
      const envelope = err as ApiErrorEnvelope;
      if (envelope.error?.code === "CATEGORY_NAME_CONFLICT") {
        return t("nameConflict");
      }
      return envelope.error?.message || t("createFailed");
    }
    return t("createFailed");
  };

  const saveEdit = async (categoryId: string) => {
    const name = editName.trim();
    if (!name) return;
    try {
      await updateMutation.mutateAsync({ categoryId, name });
      setEditingId(null);
    } catch {
      // handled by mutation
    }
  };

  const handleCreate = async () => {
    const name = newName.trim();
    if (!name) return;
    setCreateError(null);
    try {
      await createMutation.mutateAsync({ name });
      setNewName("");
    } catch (err) {
      setCreateError(getCreateError(err));
    }
  };

  const handleDelete = async (categoryId: string, name: string) => {
    if (!window.confirm(t("deleteConfirm", { name }))) return;
    try {
      await deleteMutation.mutateAsync(categoryId);
    } catch (err) {
      alert(getDeleteError(err));
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6"
      role="presentation"
    >
      <button
        type="button"
        className="absolute inset-0 bg-stone-900/50 backdrop-blur-[2px]"
        aria-label={t("close")}
        onClick={onClose}
      />
      <div
        className="relative flex max-h-[min(88vh,720px)] w-full max-w-lg flex-col overflow-hidden rounded-2xl bg-white shadow-2xl ring-1 ring-stone-200/80"
        role="dialog"
        aria-modal="true"
        aria-labelledby="category-dialog-title"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between border-b border-stone-100 px-6 py-5 sm:px-8 sm:py-6">
          <div>
            <h2 id="category-dialog-title" className="text-xl font-semibold text-stone-900 sm:text-2xl">
              {t("title")}
            </h2>
            <p className="mt-1 text-sm text-stone-500 sm:text-base">{t("subtitle")}</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-2 text-stone-400 transition-colors hover:bg-stone-100 hover:text-stone-700"
            aria-label={t("close")}
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="border-b border-stone-100 px-6 py-5 sm:px-8">
          <p className="mb-3 text-sm font-medium text-stone-700">{t("addNew")}</p>
          <div className="flex gap-2">
            <input
              type="text"
              maxLength={32}
              value={newName}
              onChange={(e) => {
                setNewName(e.target.value);
                setCreateError(null);
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  handleCreate();
                }
              }}
              placeholder={t("newPlaceholder")}
              className="flex-1 rounded-xl border border-stone-200 px-4 py-3 text-base focus:border-stone-400 focus:outline-none focus:ring-2 focus:ring-stone-200"
            />
            <button
              type="button"
              disabled={createMutation.isPending || !newName.trim()}
              onClick={handleCreate}
              className="inline-flex items-center gap-2 rounded-xl bg-stone-900 px-5 py-3 text-base font-medium text-white disabled:opacity-50"
            >
              <Plus className="h-5 w-5" />
              {t("add")}
            </button>
          </div>
          {createError && <p className="mt-2 text-sm text-red-600">{createError}</p>}
        </div>

        <ul className="min-h-0 flex-1 overflow-y-auto divide-y divide-stone-100">
          {(categories ?? []).map((cat) => (
            <li key={cat.categoryId} className="px-6 py-4 sm:px-8 sm:py-5">
              {editingId === cat.categoryId ? (
                <div className="flex gap-2">
                  <input
                    type="text"
                    maxLength={32}
                    value={editName}
                    onChange={(e) => setEditName(e.target.value)}
                    className="flex-1 rounded-xl border border-stone-200 px-4 py-2.5 text-base"
                    autoFocus
                  />
                  <button
                    type="button"
                    onClick={() => saveEdit(cat.categoryId)}
                    className="rounded-xl bg-stone-900 px-4 py-2.5 text-sm font-medium text-white"
                  >
                    {t("save")}
                  </button>
                </div>
              ) : (
                <div className="flex items-center justify-between gap-4">
                  <div className="min-w-0">
                    <p className="text-base font-semibold text-stone-900 sm:text-lg">
                      {getCategoryDisplayName(cat, tProj("defaultCategory"))}
                    </p>
                    <p className="mt-1 text-sm text-stone-500">
                      {t("projectCount", { count: cat.projectCount })}
                    </p>
                  </div>
                  <div className="flex shrink-0 items-center gap-1">
                    <button
                      type="button"
                      onClick={() => {
                        setEditingId(cat.categoryId);
                        setEditName(cat.name);
                      }}
                      className="rounded-lg p-2.5 text-stone-500 transition-colors hover:bg-stone-100 hover:text-stone-800"
                      title={t("rename")}
                    >
                      <Pencil className="h-4 w-4" />
                    </button>
                    {!cat.isSystem && (
                      <button
                        type="button"
                        onClick={() =>
                          handleDelete(
                            cat.categoryId,
                            getCategoryDisplayName(cat, tProj("defaultCategory"))
                          )
                        }
                        className="rounded-lg p-2.5 text-stone-400 transition-colors hover:bg-red-50 hover:text-red-600"
                        title={t("delete")}
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    )}
                  </div>
                </div>
              )}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
