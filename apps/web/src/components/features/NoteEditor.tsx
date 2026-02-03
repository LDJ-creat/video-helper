/**
 * TipTap Note Editor Component
 * Story 9-2: TipTap editor with autosave (debounce + flush)
 * 
 * AC1: Autosave after 800-1500ms of inactivity with save status indicator
 * AC2: Flush save on beforeunload/route change
 */

"use client";

import { useEditor, EditorContent, type JSONContent } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import { useEffect, useRef, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { useSaveNote } from "@/lib/api/noteQueries";

// Debounce delay in ms (AC: 800-1500ms)
const AUTOSAVE_DELAY_MS = 1200;

export interface NoteEditorProps {
    /** Project ID */
    projectId: string;
    /** Result ID */
    resultId: string;
    /** Initial note content (TipTap JSON) */
    initialContent: JSONContent;
    /** Callback when save succeeds */
    onSaveSuccess?: () => void;
    /** Callback when save fails */
    onSaveError?: (error: Error) => void;
}

export type SaveStatus = "idle" | "saving" | "saved" | "error";

export function NoteEditor({
    projectId,
    resultId,
    initialContent,
    onSaveSuccess,
    onSaveError,
}: NoteEditorProps) {
    const [saveStatus, setSaveStatus] = useState<SaveStatus>("idle");
    const [lastSavedAt, setLastSavedAt] = useState<Date | null>(null);
    const saveTimerRef = useRef<NodeJS.Timeout | null>(null);
    const hasPendingChangesRef = useRef(false);
    const router = useRouter();

    const { mutateAsync: saveNote, isPending: isSaving } = useSaveNote();

    // Editor instance
    const editor = useEditor({
        extensions: [StarterKit],
        content: initialContent,
        onUpdate: ({ editor }) => {
            hasPendingChangesRef.current = true;
            scheduleAutosave();
        },
        editorProps: {
            attributes: {
                class: "prose prose-stone max-w-none focus:outline-none min-h-[300px] px-4 py-3",
            },
        },
    });

    /**
     * Schedule debounced autosave (AC1: 800-1500ms)
     */
    const scheduleAutosave = useCallback(() => {
        // Clear existing timer
        if (saveTimerRef.current) {
            clearTimeout(saveTimerRef.current);
        }

        // Schedule new save
        saveTimerRef.current = setTimeout(() => {
            handleSave();
        }, AUTOSAVE_DELAY_MS);
    }, []);

    /**
     * Perform save operation
     */
    const handleSave = useCallback(async () => {
        if (!editor || !hasPendingChangesRef.current) return;

        const content = editor.getJSON();
        setSaveStatus("saving");

        try {
            await saveNote({
                projectId,
                resultId,
                content: { content },
            });
            // ✅ FIX: Only clear pending after successful save (race condition fix)
            hasPendingChangesRef.current = false;
            setSaveStatus("saved");
            setLastSavedAt(new Date());
            onSaveSuccess?.();
        } catch (error) {
            // ✅ FIX: Improved error handling with error type detection
            const err = error as any;
            const status = err?.response?.status;

            if (status === 401 || status === 403) {
                console.error("Auth error - please re-login:", error);
            } else if (status === 404) {
                console.error("Project/Result not found:", error);
            } else if (status >= 400 && status < 500) {
                console.error("Validation error:", error);
            } else {
                console.error("Network/Server error:", error);
            }

            setSaveStatus("error");
            onSaveError?.(error as Error);
        }
    }, [editor, projectId, resultId, saveNote, onSaveSuccess, onSaveError]);

    /**
     * Flush save (best-effort) - AC2: beforeunload/route change
     * ✅ FIX: Use fetch with keepalive instead of sendBeacon (supports headers)
     */
    const flushSave = useCallback(() => {
        if (saveTimerRef.current) {
            clearTimeout(saveTimerRef.current);
        }

        if (hasPendingChangesRef.current && editor) {
            const content = editor.getJSON();
            const url = `/api/v1/projects/${projectId}/results/${resultId}/note`;

            // Use fetch with keepalive for reliable flush (supports Content-Type header)
            fetch(url, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ content }),
                keepalive: true, // ✅ Critical: keeps request alive even after page unloads
            }).catch(() => {
                // Silently fail in flush - best effort
            });
        }
    }, [editor, projectId, resultId]);

    /**
     * Setup beforeunload handler (AC2)
     */
    useEffect(() => {
        const handleBeforeUnload = (e: BeforeUnloadEvent) => {
            if (hasPendingChangesRef.current) {
                // Modern browsers ignore custom messages
                e.preventDefault();
                flushSave();
            }
        };

        window.addEventListener("beforeunload", handleBeforeUnload);
        return () => {
            window.removeEventListener("beforeunload", handleBeforeUnload);
        };
    }, [flushSave]);

    /**
     * ✅ FIX: Route change handler (AC2 - Next.js app router)
     */
    useEffect(() => {
        const handleRouteChange = () => {
            if (hasPendingChangesRef.current) {
                flushSave();
            }
        };

        // Listen to beforePopState for Next.js routing
        const originalPush = router.push;
        const originalReplace = router.replace;
        const originalBack = router.back;

        router.push = ((href: string, options?: any) => {
            handleRouteChange();
            return originalPush(href, options);
        }) as typeof router.push;

        router.replace = ((href: string, options?: any) => {
            handleRouteChange();
            return originalReplace(href, options);
        }) as typeof router.replace;

        router.back = (() => {
            handleRouteChange();
            return originalBack();
        }) as typeof router.back;

        return () => {
            router.push = originalPush;
            router.replace = originalReplace;
            router.back = originalBack;
        };
    }, [router, flushSave]);

    /**
     * Cleanup on unmount - flush save
     */
    useEffect(() => {
        return () => {
            flushSave();
        };
    }, [flushSave]);

    /**
     * Reset "saved" status after 3 seconds
     */
    useEffect(() => {
        if (saveStatus === "saved") {
            const timer = setTimeout(() => {
                setSaveStatus("idle");
            }, 3000);
            return () => clearTimeout(timer);
        }
    }, [saveStatus]);

    if (!editor) {
        return (
            <div className="flex items-center justify-center p-8">
                <div className="text-sm text-stone-500">加载编辑器...</div>
            </div>
        );
    }

    return (
        <div className="flex flex-col h-full">
            {/* Editor Toolbar */}
            <div className="flex items-center justify-between border-b border-stone-200 px-4 py-2">
                <div className="flex items-center gap-2">
                    {/* Bold */}
                    <button
                        onClick={() => editor.chain().focus().toggleBold().run()}
                        className={`p-2 rounded hover:bg-stone-100 ${editor.isActive("bold") ? "bg-stone-200" : ""
                            }`}
                        title="粗体"
                    >
                        <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                            <path d="M6 4v12h4.5a3.5 3.5 0 001.852-6.478A3.5 3.5 0 0010.5 4H6zm2 2h2.5a1.5 1.5 0 010 3H8V6zm0 5h2.5a1.5 1.5 0 010 3H8v-3z" />
                        </svg>
                    </button>

                    {/* Italic */}
                    <button
                        onClick={() => editor.chain().focus().toggleItalic().run()}
                        className={`p-2 rounded hover:bg-stone-100 ${editor.isActive("italic") ? "bg-stone-200" : ""
                            }`}
                        title="斜体"
                    >
                        <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                            <path d="M10 4v1.5L8.5 6v1h3l-1.5.5V12l1.5.5v1h-5v-1l1.5-.5V7.5L6.5 7V6h5V4h-1.5z" />
                        </svg>
                    </button>

                    {/* Bullet List */}
                    <button
                        onClick={() => editor.chain().focus().toggleBulletList().run()}
                        className={`p-2 rounded hover:bg-stone-100 ${editor.isActive("bulletList") ? "bg-stone-200" : ""
                            }`}
                        title="无序列表"
                    >
                        <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                            <path d="M3 6a1 1 0 100-2 1 1 0 000 2zm0 5a1 1 0 100-2 1 1 0 000 2zm0 5a1 1 0 100-2 1 1 0 000 2zm4-9h10v1H7V7zm0 5h10v1H7v-1zm0 5h10v1H7v-1z" />
                        </svg>
                    </button>

                    {/* Ordered List */}
                    <button
                        onClick={() => editor.chain().focus().toggleOrderedList().run()}
                        className={`p-2 rounded hover:bg-stone-100 ${editor.isActive("orderedList") ? "bg-stone-200" : ""
                            }`}
                        title="有序列表"
                    >
                        <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                            <path d="M3 4h1v3H3V4zm0 5h1v3H3V9zm0 5h1v3H3v-3zm4-7h10v1H7V7zm0 5h10v1H7v-1zm0 5h10v1H7v-1z" />
                        </svg>
                    </button>
                </div>

                {/* Save Status Indicator (AC1) */}
                <div className="flex items-center gap-2 text-sm">
                    {saveStatus === "saving" && (
                        <>
                            <div className="w-3 h-3 border-2 border-orange-600 border-t-transparent rounded-full animate-spin" />
                            <span className="text-stone-600">保存中...</span>
                        </>
                    )}
                    {saveStatus === "saved" && (
                        <>
                            <svg className="w-4 h-4 text-green-600" fill="currentColor" viewBox="0 0 20 20">
                                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                            </svg>
                            <span className="text-green-600">已保存</span>
                            {lastSavedAt && (
                                <span className="text-stone-400">
                                    {lastSavedAt.toLocaleTimeString("zh-CN", {
                                        hour: "2-digit",
                                        minute: "2-digit",
                                    })}
                                </span>
                            )}
                        </>
                    )}
                    {saveStatus === "error" && (
                        <>
                            <svg className="w-4 h-4 text-rose-600" fill="currentColor" viewBox="0 0 20 20">
                                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
                            </svg>
                            <span className="text-rose-600">保存失败</span>
                            <button
                                onClick={handleSave}
                                className="text-orange-600 hover:text-orange-700 underline"
                            >
                                重试
                            </button>
                        </>
                    )}
                </div>
            </div>

            {/* Editor Content */}
            <div className="flex-1 overflow-y-auto">
                <EditorContent editor={editor} />
            </div>
        </div>
    );
}
