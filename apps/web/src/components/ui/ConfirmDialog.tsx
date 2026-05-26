"use client";

import { AlertTriangle, X } from "lucide-react";
import { useEffect } from "react";

export type ConfirmDialogProps = {
    open: boolean;
    onClose: () => void;
    onConfirm: () => void | Promise<void>;
    title: string;
    description?: string;
    /** Optional emphasized line (e.g. project title). */
    highlight?: string;
    confirmLabel: string;
    cancelLabel: string;
    loading?: boolean;
    variant?: "danger" | "default";
};

export function ConfirmDialog({
    open,
    onClose,
    onConfirm,
    title,
    description,
    highlight,
    confirmLabel,
    cancelLabel,
    loading = false,
    variant = "default",
}: ConfirmDialogProps) {
    useEffect(() => {
        if (!open) return;
        const onKey = (e: KeyboardEvent) => {
            if (e.key === "Escape" && !loading) onClose();
        };
        document.addEventListener("keydown", onKey);
        const prevOverflow = document.body.style.overflow;
        document.body.style.overflow = "hidden";
        return () => {
            document.removeEventListener("keydown", onKey);
            document.body.style.overflow = prevOverflow;
        };
    }, [open, onClose, loading]);

    if (!open) return null;

    const isDanger = variant === "danger";

    return (
        <div
            className="fixed inset-0 z-[60] flex items-center justify-center p-4 sm:p-6"
            role="presentation"
        >
            <button
                type="button"
                className="absolute inset-0 bg-stone-900/45 backdrop-blur-[3px] transition-opacity"
                aria-label={cancelLabel}
                disabled={loading}
                onClick={() => {
                    if (!loading) onClose();
                }}
            />
            <div
                className="relative w-full max-w-md overflow-hidden rounded-2xl bg-white shadow-2xl ring-1 ring-stone-200/90 animate-in fade-in duration-200"
                role="alertdialog"
                aria-modal="true"
                aria-labelledby="confirm-dialog-title"
                aria-describedby="confirm-dialog-desc"
                onClick={(e) => e.stopPropagation()}
            >
                <div className="px-6 pt-6 pb-4 sm:px-8 sm:pt-8">
                    <div className="flex gap-4">
                        <div
                            className={`flex h-12 w-12 shrink-0 items-center justify-center rounded-full ${
                                isDanger ? "bg-red-50" : "bg-stone-100"
                            }`}
                        >
                            <AlertTriangle
                                className={`h-6 w-6 ${isDanger ? "text-red-600" : "text-stone-600"}`}
                                aria-hidden
                            />
                        </div>
                        <div className="min-w-0 flex-1 pt-0.5">
                            <div className="flex items-start justify-between gap-2">
                                <h2
                                    id="confirm-dialog-title"
                                    className="text-lg font-semibold tracking-tight text-stone-900 sm:text-xl"
                                >
                                    {title}
                                </h2>
                                <button
                                    type="button"
                                    onClick={onClose}
                                    disabled={loading}
                                    className="shrink-0 rounded-lg p-1.5 text-stone-400 transition-colors hover:bg-stone-100 hover:text-stone-700 disabled:opacity-50"
                                    aria-label={cancelLabel}
                                >
                                    <X className="h-5 w-5" />
                                </button>
                            </div>
                            {description ? (
                                <p
                                    id="confirm-dialog-desc"
                                    className="mt-2 text-sm leading-relaxed text-stone-600 sm:text-base"
                                >
                                    {description}
                                </p>
                            ) : null}
                            {highlight ? (
                                <p className="mt-4 line-clamp-3 rounded-xl border border-stone-100 bg-stone-50 px-4 py-3 text-sm font-medium leading-snug text-stone-900">
                                    {highlight}
                                </p>
                            ) : null}
                        </div>
                    </div>
                </div>

                <div className="flex flex-col-reverse gap-2 border-t border-stone-100 bg-stone-50/60 px-6 py-4 sm:flex-row sm:justify-end sm:gap-3 sm:px-8">
                    <button
                        type="button"
                        onClick={onClose}
                        disabled={loading}
                        className="w-full rounded-xl border border-stone-200 bg-white px-4 py-2.5 text-sm font-medium text-stone-700 shadow-sm transition-colors hover:bg-stone-50 disabled:opacity-50 sm:w-auto"
                    >
                        {cancelLabel}
                    </button>
                    <button
                        type="button"
                        onClick={() => void onConfirm()}
                        disabled={loading}
                        className={`w-full rounded-xl px-4 py-2.5 text-sm font-medium text-white shadow-sm transition-colors disabled:opacity-60 sm:w-auto ${
                            isDanger
                                ? "bg-red-600 hover:bg-red-700 focus:ring-2 focus:ring-red-200"
                                : "bg-stone-900 hover:bg-stone-800 focus:ring-2 focus:ring-stone-200"
                        }`}
                    >
                        {confirmLabel}
                    </button>
                </div>
            </div>
        </div>
    );
}
