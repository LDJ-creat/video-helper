/**
 * TipTap Note Editor Component
 * Story 9-2: TipTap editor with autosave (debounce + flush)
 * 
 * AC1: Autosave after 800-1500ms of inactivity with save status indicator
 * AC2: Flush save on beforeunload/route change
 * ✅ ENHANCED: Rich text editing + Markdown shortcuts
 */

"use client";

import { useEditor, EditorContent, type JSONContent } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import { Underline } from '@tiptap/extension-underline';
import { Highlight } from '@tiptap/extension-highlight';
import { Link } from '@tiptap/extension-link';
import { TaskList } from '@tiptap/extension-task-list';
import { TaskItem } from '@tiptap/extension-task-item';
import { Typography } from '@tiptap/extension-typography';
import { Placeholder } from '@tiptap/extension-placeholder';
import { TextAlign } from '@tiptap/extension-text-align';
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

    // Editor instance with enhanced features
    const editor = useEditor({
        extensions: [
            StarterKit.configure({
                heading: {
                    levels: [1, 2, 3, 4, 5, 6],
                },
                bulletList: {
                    HTMLAttributes: {
                        class: 'list-disc list-outside ml-6 my-2',
                    },
                },
                orderedList: {
                    HTMLAttributes: {
                        class: 'list-decimal list-outside ml-6 my-2',
                    },
                },
                blockquote: {
                    HTMLAttributes: {
                        class: 'border-l-4 border-stone-300 pl-4 italic my-2',
                    },
                },
                code: {
                    HTMLAttributes: {
                        class: 'bg-stone-100 text-rose-600 px-1 py-0.5 rounded text-sm font-mono',
                    },
                },
                codeBlock: {
                    HTMLAttributes: {
                        class: 'bg-stone-900 text-stone-100 p-4 rounded-lg font-mono text-sm my-2',
                    },
                },
            }),
            // ✅ Rich text extensions
            Underline,
            Highlight.configure({
                multicolor: false,
                HTMLAttributes: {
                    class: 'bg-yellow-200',
                },
            }),
            Link.configure({
                openOnClick: false,
                HTMLAttributes: {
                    class: 'text-blue-600 underline hover:text-blue-800',
                },
            }),
            // ✅ Task list
            TaskList.configure({
                HTMLAttributes: {
                    class: 'list-none ml-2',
                },
            }),
            TaskItem.configure({
                nested: true,
                HTMLAttributes: {
                    class: 'flex items-start gap-2',
                },
            }),
            // ✅ Text alignment
            TextAlign.configure({
                types: ['heading', 'paragraph'],
            }),
            // ✅ Markdown shortcuts (# + space → Heading 1, etc.)
            Typography,
            // ✅ Placeholder text
            Placeholder.configure({
                placeholder: '输入文本...试试 Markdown 快捷方式：# 标题, - 列表, > 引用',
            }),
        ],
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
        <div className="flex flex-col h-full bg-white">
            {/* Enhanced Editor Toolbar */}
            <div className="flex items-center justify-between border-b border-stone-200 px-3 py-2 flex-wrap gap-2">
                <div className="flex items-center gap-1 flex-wrap">
                    {/* 标题选择器 */}
                    <select
                        value={
                            editor.isActive('heading', { level: 1 }) ? '1' :
                                editor.isActive('heading', { level: 2 }) ? '2' :
                                    editor.isActive('heading', { level: 3 }) ? '3' :
                                        '0'
                        }
                        onChange={(e) => {
                            const level = parseInt(e.target.value);
                            if (level > 0) {
                                editor.chain().focus().setHeading({ level: level as 1 | 2 | 3 }).run();
                            } else {
                                editor.chain().focus().setParagraph().run();
                            }
                        }}
                        className="px-2 py-1 text-sm border border-stone-300 rounded hover:bg-stone-50 focus:outline-none focus:border-orange-400"
                    >
                        <option value="0">正文</option>
                        <option value="1">标题 1</option>
                        <option value="2">标题 2</option>
                        <option value="3">标题 3</option>
                    </select>

                    <div className="w-px h-6 bg-stone-300 mx-1" />

                    {/* 文本格式 */}
                    <button
                        onClick={() => editor.chain().focus().toggleBold().run()}
                        className={`p-1.5 rounded hover:bg-stone-100 transition-colors ${editor.isActive("bold") ? "bg-stone-200" : ""
                            }`}
                        title="粗体 (Ctrl+B)"
                    >
                        <span className="font-bold text-sm">B</span>
                    </button>

                    <button
                        onClick={() => editor.chain().focus().toggleItalic().run()}
                        className={`p-1.5 rounded hover:bg-stone-100 transition-colors ${editor.isActive("italic") ? "bg-stone-200" : ""
                            }`}
                        title="斜体 (Ctrl+I)"
                    >
                        <span className="italic text-sm">I</span>
                    </button>

                    <button
                        onClick={() => editor.chain().focus().toggleUnderline().run()}
                        className={`p-1.5 rounded hover:bg-stone-100 transition-colors ${editor.isActive("underline") ? "bg-stone-200" : ""
                            }`}
                        title="下划线 (Ctrl+U)"
                    >
                        <span className="underline text-sm">U</span>
                    </button>

                    <button
                        onClick={() => editor.chain().focus().toggleStrike().run()}
                        className={`p-1.5 rounded hover:bg-stone-100 transition-colors ${editor.isActive("strike") ? "bg-stone-200" : ""
                            }`}
                        title="删除线"
                    >
                        <span className="line-through text-sm">S</span>
                    </button>

                    <button
                        onClick={() => editor.chain().focus().toggleCode().run()}
                        className={`p-1.5 rounded hover:bg-stone-100 transition-colors ${editor.isActive("code") ? "bg-stone-200" : ""
                            }`}
                        title="行内代码"
                    >
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
                        </svg>
                    </button>

                    <button
                        onClick={() => editor.chain().focus().toggleHighlight().run()}
                        className={`p-1.5 rounded hover:bg-stone-100 transition-colors ${editor.isActive("highlight") ? "bg-stone-200" : ""
                            }`}
                        title="高亮"
                    >
                        <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                            <path fillRule="evenodd" d="M5 2a1 1 0 011 1v1h1a1 1 0 010 2H6v1a1 1 0 01-2 0V6H3a1 1 0 010-2h1V3a1 1 0 011-1zm0 10a1 1 0 011 1v1h1a1 1 0 110 2H6v1a1 1 0 11-2 0v-1H3a1 1 0 110-2h1v-1a1 1 0 011-1zM12 2a1 1 0 01.967.744L14.146 7.2 17.5 9.134a1 1 0 010 1.732l-3.354 1.935-1.18 4.455a1 1 0 01-1.933 0L9.854 12.8 6.5 10.866a1 1 0 010-1.732l3.354-1.935 1.18-4.455A1 1 0 0112 2z" clipRule="evenodd" />
                        </svg>
                    </button>

                    <div className="w-px h-6 bg-stone-300 mx-1" />

                    {/* 块级元素 */}
                    <button
                        onClick={() => editor.chain().focus().toggleBlockquote().run()}
                        className={`p-1.5 rounded hover:bg-stone-100 transition-colors ${editor.isActive("blockquote") ? "bg-stone-200" : ""
                            }`}
                        title='引用 (输入 "> " 自动转换)'
                    >
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 8h10M7 12h4m1 8l-4-4H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-3l-4 4z" />
                        </svg>
                    </button>

                    <button
                        onClick={() => editor.chain().focus().toggleCodeBlock().run()}
                        className={`p-1.5 rounded hover:bg-stone-100 transition-colors ${editor.isActive("codeBlock") ? "bg-stone-200" : ""
                            }`}
                        title='代码块 (输入 "```" 自动转换)'
                    >
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 9l3 3-3 3m5 0h3M5 20h14a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                        </svg>
                    </button>

                    <button
                        onClick={() => editor.chain().focus().setHorizontalRule().run()}
                        className="p-1.5 rounded hover:bg-stone-100 transition-colors"
                        title='分隔线 (输入 "---" 自动转换)'
                    >
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20 12H4" />
                        </svg>
                    </button>

                    <div className="w-px h-6 bg-stone-300 mx-1" />

                    {/* 列表 */}
                    <button
                        onClick={() => editor.chain().focus().toggleBulletList().run()}
                        className={`p-1.5 rounded hover:bg-stone-100 transition-colors ${editor.isActive("bulletList") ? "bg-stone-200" : ""
                            }`}
                        title='无序列表 (输入 "- " 自动转换)'
                    >
                        <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                            <path d="M3 6a1 1 0 100-2 1 1 0 000 2zm0 5a1 1 0 100-2 1 1 0 000 2zm0 5a1 1 0 100-2 1 1 0 000 2zm4-9h10v1H7V7zm0 5h10v1H7v-1zm0 5h10v1H7v-1z" />
                        </svg>
                    </button>

                    <button
                        onClick={() => editor.chain().focus().toggleOrderedList().run()}
                        className={`p-1.5 rounded hover:bg-stone-100 transition-colors ${editor.isActive("orderedList") ? "bg-stone-200" : ""
                            }`}
                        title='有序列表 (输入 "1. " 自动转换)'
                    >
                        <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                            <path d="M3 4h1v3H3V4zm0 5h1v3H3V9zm0 5h1v3H3v-3zm4-7h10v1H7V7zm0 5h10v1H7v-1zm0 5h10v1H7v-1z" />
                        </svg>
                    </button>

                    <button
                        onClick={() => editor.chain().focus().toggleTaskList().run()}
                        className={`p-1.5 rounded hover:bg-stone-100 transition-colors ${editor.isActive("taskList") ? "bg-stone-200" : ""
                            }`}
                        title='任务列表 (输入 "[ ] " 自动转换)'
                    >
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" />
                        </svg>
                    </button>

                    <div className="w-px h-6 bg-stone-300 mx-1" />

                    {/* 链接 */}
                    <button
                        onClick={() => {
                            const url = window.prompt('输入链接地址:');
                            if (url) {
                                editor.chain().focus().setLink({ href: url }).run();
                            }
                        }}
                        className={`p-1.5 rounded hover:bg-stone-100 transition-colors ${editor.isActive("link") ? "bg-stone-200" : ""
                            }`}
                        title="插入链接"
                    >
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
                        </svg>
                    </button>

                    {editor.isActive("link") && (
                        <button
                            onClick={() => editor.chain().focus().unsetLink().run()}
                            className="p-1.5 rounded hover:bg-rose-100 text-rose-600 transition-colors"
                            title="移除链接"
                        >
                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                            </svg>
                        </button>
                    )}
                </div>

                {/* Save Status Indicator */}
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

            {/* Markdown Shortcuts Help */}
            <div className="px-4 py-1.5 bg-blue-50 border-b border-blue-100 text-xs text-blue-700">
                <span className="font-medium">💡 快捷提示:</span>
                <span className="ml-2"># + 空格 = 标题1</span>
                <span className="ml-3">- + 空格 = 无序列表</span>
                <span className="ml-3">1. + 空格 = 有序列表</span>
                <span className="ml-3">&gt; + 空格 = 引用</span>
                <span className="ml-3">[ ] + 空格 = 任务</span>
            </div>

            {/* Editor Content */}
            <div className="flex-1 overflow-y-auto bg-white">
                <EditorContent editor={editor} />
            </div>
        </div>
    );
}
