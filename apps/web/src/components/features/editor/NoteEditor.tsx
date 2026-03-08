"use client";

import { useEditor, EditorContent, JSONContent, ReactNodeViewRenderer, NodeViewWrapper, NodeViewContent } from "@tiptap/react";

import StarterKit from "@tiptap/starter-kit";
import { Heading } from '@tiptap/extension-heading';
import { Paragraph } from '@tiptap/extension-paragraph';
import { Underline } from '@tiptap/extension-underline';
import { Highlight as TiptapHighlight } from '@tiptap/extension-highlight';
import { Link } from '@tiptap/extension-link';
import { TaskList } from '@tiptap/extension-task-list';
import { TaskItem } from '@tiptap/extension-task-item';
import { Typography } from '@tiptap/extension-typography';
import { Placeholder } from '@tiptap/extension-placeholder';
import { TextAlign } from '@tiptap/extension-text-align';
import { Extension } from '@tiptap/react';
import { useEffect, useRef, useState, useCallback, useImperativeHandle, forwardRef } from "react";
import { useTranslations } from "next-intl";
import { ContentBlock, Highlight, Keyframe } from "@/lib/contracts/resultTypes";
import { useSaveContentBlocks, useUploadAsset } from "@/lib/api/resultQueries";
import { TextSelection } from "@tiptap/pm/state";

const AUTOSAVE_DELAY_MS = 2000;

// Custom extension to add attributes to nodes
const BlockAttributes = Extension.create({
    name: 'blockAttributes',
    addGlobalAttributes() {
        return [
            {
                types: ['heading'],
                attributes: {
                    blockId: { default: null, keepOnSplit: false, renderHTML: attrs => ({ 'data-block-id': attrs.blockId }) },
                    startMs: { default: null, renderHTML: attrs => ({ 'data-start-ms': attrs.startMs }) },
                    endMs: { default: null, renderHTML: attrs => ({ 'data-end-ms': attrs.endMs }) },
                },
            },
            {
                types: ['paragraph'],
                attributes: {
                    highlightId: { default: null, keepOnSplit: false, renderHTML: attrs => ({ 'data-highlight-id': attrs.highlightId }) },
                    timeMs: { default: null, renderHTML: attrs => ({ 'data-time-ms': attrs.timeMs }) },
                    keyframes: {
                        default: [],
                        parseHTML: element => {
                            const attr = element.getAttribute('data-keyframes');
                            return attr ? JSON.parse(attr) : [];
                        },
                        renderHTML: attrs => ({ 'data-keyframes': JSON.stringify(attrs.keyframes) })
                    },
                },
            },
        ];
    },
});

export interface NoteEditorProps {
    projectId: string;
    resultId?: string;
    contentBlocks: ContentBlock[];
    onSaveSuccess?: () => void;
    onSaveError?: (error: Error) => void;
    onBlockNavigation?: (timeMs: number) => void;
}

export interface NoteEditorRef {
    scrollToBlock: (blockId: string) => void;
    scrollToHighlight: (highlightId: string) => void;
}

// Enter key override: insert hardBreak inside paragraph instead of splitting
const EnterInParagraph = Extension.create({
    name: 'enterInParagraph',
    addKeyboardShortcuts() {
        return {
            Enter: ({ editor }) => {
                const { selection } = editor.state;
                const { $from } = selection;
                if ($from.parent.type.name === 'paragraph') {
                    return editor.commands.setHardBreak();
                }
                return false;
            },
        };
    },
});

// Navigation Extension
const NavigationExtension = Extension.create({
    name: 'navigation',
    addStorage() { return { onNavigate: null as ((ms: number) => void) | null }; },
    addCommands() {
        return {
            navigateToTime: (timeMs: number) => ({ editor }: { editor: unknown }) => {
                // eslint-disable-next-line @typescript-eslint/no-explicit-any
                const navStorage = (editor as any).storage?.navigation;
                if (navStorage?.onNavigate) {
                    navStorage.onNavigate(timeMs);
                    return true;
                }
                return false;
            }
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
        } as any;
    },
});

/* ── React Node Views ── */

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const HeadingBlock = ({ node, editor, HTMLAttributes }: { node: any, editor: any, HTMLAttributes: any }) => {
    const t = useTranslations("Notes");
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const hasTime = (node as any).attrs.startMs !== null && (node as any).attrs.startMs !== undefined;
    const blockId = node?.attrs?.blockId as string | null | undefined;

    return (
        <NodeViewWrapper
            {...HTMLAttributes}
            data-block-id={blockId ?? undefined}
            className={`flex items-baseline gap-3 group -ml-12 pl-1 transition-colors rounded-lg hover:bg-stone-50/50 mt-8 scroll-mt-24 ${HTMLAttributes?.class ?? ''}`.trim()}
        >
            <div
                contentEditable={false}
                className={`flex-shrink-0 w-[60px] flex justify-center items-center h-7 ${hasTime ? 'cursor-pointer' : 'pointer-events-none'}`}
            >
                {hasTime && (
                    // eslint-disable-next-line @typescript-eslint/no-explicit-any
                    <div className="p-1 2xl:p-2 rounded-full text-stone-300 hover:text-blue-600 hover:bg-blue-50 transition-all opacity-0 group-hover:opacity-100" title={t("jumpToVideo")} onClick={() => (editor as any).commands.navigateToTime((node as any).attrs.startMs)}>
                        <svg className="w-5 h-5 2xl:w-7 2xl:h-7" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>
                    </div>
                )}
            </div>
            <NodeViewContent className="flex-1 font-bold text-stone-800 text-xl 2xl:text-3xl" />
        </NodeViewWrapper>
    );
};

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const ParagraphBlock = ({ node, updateAttributes, editor, getPos, HTMLAttributes }: { node: any, updateAttributes: any, editor: any, getPos: any, HTMLAttributes: any }) => {
    const t = useTranslations("Notes");
    // Calculate highlight index within current block (top-level nodes only)
    const highlightIndex = (() => {
        if (!editor || typeof getPos !== 'function') return null;
        try {
            const pos = getPos();
            const doc = editor.state.doc;
            let idx = 0;
            let found = false;
            let offset = 0;
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            doc.content.forEach((n: any) => {
                if (found) return;
                if (n.type.name === 'heading') {
                    idx = 0;
                } else if (n.type.name === 'paragraph') {
                    idx += 1;
                    if (offset === pos) found = true;
                }
                offset += n.nodeSize;
            });
            return found ? idx : null;
        } catch { return null; }
    })();
    const hasTime = node.attrs.timeMs !== null && node.attrs.timeMs !== undefined;
    const keyframes = (node.attrs.keyframes || []) as Keyframe[];
    const highlightId = node?.attrs?.highlightId as string | null | undefined;
    const fileInputRef = useRef<HTMLInputElement>(null);
    const [zoomedImage, setZoomedImage] = useState<string | null>(null);

    const handleAddKeyframeClick = () => {
        fileInputRef.current?.click();
    };

    const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
        const files = Array.from(e.target.files || []);
        if (files.length === 0) return;

        // Call editor command to upload multiple
        editor.commands.uploadKeyframes(files, (results: Array<{ url: string, assetId: string }>) => {
            const newKeyframes = results.map(r => ({
                assetId: r.assetId,
                contentUrl: r.url,
                timeMs: node.attrs.timeMs || 0
            }));
            updateAttributes({ keyframes: [...keyframes, ...newKeyframes] });
        });

        e.target.value = '';
    };

    const handleDeleteKeyframe = (assetId: string) => {
        const newKeyframes = keyframes.filter(k => k.assetId !== assetId);
        updateAttributes({ keyframes: newKeyframes });
    };

    return (
        <>
            <NodeViewWrapper
                {...HTMLAttributes}
                data-highlight-id={highlightId ?? undefined}
                className={`flex items-start gap-3 2xl:gap-5 group -ml-12 2xl:-ml-16 pl-1 transition-colors rounded-lg hover:bg-stone-50/50 mb-6 relative scroll-mt-24 ${HTMLAttributes?.class ?? ''}`.trim()}
            >
                <input
                    type="file"
                    multiple
                    ref={fileInputRef}
                    className="hidden"
                    accept="image/*"
                    onChange={handleFileChange}
                />

                <div
                    contentEditable={false}
                    className={`flex-shrink-0 mt-1 w-[60px] 2xl:w-[80px] flex flex-col items-center gap-1 2xl:gap-2`}
                >
                    <div
                        className={`flex justify-center items-center h-6 2xl:h-8 w-full ${hasTime ? 'cursor-pointer' : ''}`}
                        onClick={hasTime ? () => editor.commands.navigateToTime(node.attrs.timeMs) : undefined}
                    >
                        {hasTime && (
                            <div className="p-1 2xl:p-1.5 rounded-full text-stone-400 hover:text-blue-600 hover:bg-blue-50 transition-all opacity-0 group-hover:opacity-100" title={t("jumpToVideo")}>
                                <svg className="w-5 h-5 2xl:w-7 2xl:h-7" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>
                            </div>
                        )}
                    </div>

                    {/* Keyframe Add Button */}
                    {hasTime && (
                        <button
                            onClick={handleAddKeyframeClick}
                            className="opacity-0 group-hover:opacity-100 text-xs text-stone-400 hover:text-orange-500 transition-opacity p-1 2xl:p-1.5"
                            title={t("addImage")}
                        >
                            <svg className="w-5 h-5 2xl:w-7 2xl:h-7" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="3" width="18" height="18" rx="2" ry="2" /><circle cx="8.5" cy="8.5" r="1.5" /><polyline points="21 15 16 10 5 21" /></svg>
                        </button>
                    )}
                </div>

                <div className="flex-1 min-w-0">
                    {/* Render Keyframes List */}
                    {keyframes.length > 0 && (
                        <div contentEditable={false} className="mb-4 flex flex-col gap-4 select-none">
                            {keyframes.map((kf: Keyframe, idx: number) => (
                                <div key={kf.assetId || idx} className="relative group/image w-full">
                                    {/* eslint-disable-next-line @next/next/no-img-element */}
                                    <img
                                        src={kf.contentUrl}
                                        alt={t("keyframe")}
                                        loading="lazy"
                                        decoding="async"
                                        className="rounded-lg border border-stone-200 shadow-sm w-full h-auto object-cover bg-stone-50 cursor-zoom-in hover:opacity-95 transition-opacity"
                                        draggable={false}
                                        onClick={() => setZoomedImage(kf.contentUrl)}
                                    />
                                    <button
                                        onClick={() => handleDeleteKeyframe(kf.assetId)}
                                        className="absolute top-2 right-2 p-1.5 bg-black/60 hover:bg-red-500/80 text-white rounded-full opacity-0 group-hover/image:opacity-100 transition-all backdrop-blur-sm shadow-sm"
                                        title={t("removeImage")}
                                    >
                                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" /></svg>
                                    </button>
                                </div>
                            ))}
                        </div>
                    )}
                    <div className="flex items-baseline gap-2 2xl:gap-3">
                        {highlightIndex !== null && (
                            <span contentEditable={false} className="flex-shrink-0 text-sm 2xl:text-lg font-semibold text-stone-400 select-none leading-relaxed mt-0.5 2xl:mt-1">{highlightIndex}.</span>
                        )}
                        <NodeViewContent className="flex-1 text-stone-800 text-lg 2xl:text-2xl leading-relaxed outline-none" />
                    </div>
                </div>
            </NodeViewWrapper>

            {/* Zoom Modal */}
            {zoomedImage && (
                <div
                    className="fixed inset-0 z-50 flex items-center justify-center bg-black/90 backdrop-blur-md p-8 animate-in fade-in duration-200"
                    onClick={() => setZoomedImage(null)}
                    onKeyDown={(e) => e.key === 'Escape' && setZoomedImage(null)}
                >
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img
                        src={zoomedImage}
                        alt={t("zoomedAlt")}
                        className="max-w-full max-h-full object-contain rounded-lg shadow-2xl cursor-zoom-out"
                        onClick={(e) => { e.stopPropagation(); setZoomedImage(null); }}
                    />
                </div>
            )}
        </>
    );
};

// Custom Node Views Definitions
const CustomHeading = Heading.extend({
    addNodeView() { return ReactNodeViewRenderer(HeadingBlock); },
}).configure({ levels: [1, 2, 3] });

const CustomParagraph = Paragraph.extend({
    addNodeView() { return ReactNodeViewRenderer(ParagraphBlock); },
});

// Helper Functions
function blocksToTiptap(blocks: ContentBlock[]): JSONContent {
    const content: JSONContent[] = [];

    (blocks || []).forEach((block: ContentBlock) => {
        content.push({
            type: 'heading',
            attrs: { level: 2, blockId: block.blockId, startMs: block.startMs, endMs: block.endMs },
            content: [{ type: 'text', text: block.title }]
        });

        block.highlights.forEach((h: Highlight) => {
            const paragraphContent: JSONContent[] = [];
            paragraphContent.push({ type: 'text', text: h.text });

            // Migration: Convert single keyframe to list if needed
            let keyframes = h.keyframes || [];
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            if (!keyframes.length && (h as any).keyframe) {
                // eslint-disable-next-line @typescript-eslint/no-explicit-any
                keyframes = [(h as any).keyframe];
            }

            content.push({
                type: 'paragraph',
                attrs: {
                    highlightId: h.highlightId,
                    timeMs: h.startMs,
                    keyframes: keyframes
                },
                content: paragraphContent
            });
        });
    });

    return { type: 'doc', content };
}

function tiptapToBlocks(json: JSONContent): ContentBlock[] {
    const blocks: ContentBlock[] = [];
    let currentBlock: ContentBlock | null = null;
    let blockIdx = 0;

    json.content?.forEach((node) => {
        if (node.type === 'heading' && node.attrs?.level === 2) {
            currentBlock = {
                blockId: node.attrs.blockId || `blk_${Date.now()}_${Math.random()}`,
                idx: blockIdx++,
                title: node.content?.[0]?.text || 'Untitled Block',
                startMs: node.attrs.startMs || 0,
                endMs: node.attrs.endMs || 0,
                highlights: []
            };
            blocks.push(currentBlock);
        } else if (node.type === 'paragraph' && currentBlock) {
            const keyframes = (node.attrs?.keyframes || []) as Keyframe[];

            // Support hardBreak nodes inside paragraph
            const textParts: string[] = [];
            (node.content || []).forEach((c: JSONContent) => {
                if (c.type === 'hardBreak') {
                    textParts.push('\n');
                } else {
                    textParts.push(c.text || '');
                }
            });

            const highlight: Highlight = {
                highlightId: node.attrs?.highlightId || `hl_${Date.now()}_${Math.random()}`,
                idx: currentBlock.highlights.length,
                text: textParts.join(''),
                startMs: node.attrs?.timeMs || currentBlock.startMs,
                endMs: currentBlock.endMs,
                keyframes: keyframes
            };
            currentBlock.highlights.push(highlight);
        }
    });
    return blocks;
}

export const NoteEditor = forwardRef<NoteEditorRef, NoteEditorProps>(({
    projectId,
    contentBlocks,
    onSaveSuccess,
    onSaveError,
    onBlockNavigation,
}, ref) => {
    const t = useTranslations("Notes");
    const [saveStatus, setSaveStatus] = useState<"idle" | "saving" | "saved" | "error">("idle");
    const saveTimerRef = useRef<NodeJS.Timeout | null>(null);
    const hasPendingChangesRef = useRef(false);

    const { mutateAsync: saveBlocks } = useSaveContentBlocks(projectId);
    const { mutateAsync: uploadAsset } = useUploadAsset(projectId);

    // Stable ref for uploadAsset to be used in editor paste handler
    const uploadAssetRef = useRef(uploadAsset);
    useEffect(() => { uploadAssetRef.current = uploadAsset; }, [uploadAsset]);

    const saveHandlerRef = useRef<(() => Promise<void>) | undefined>(undefined);

    const scrollAnimFrameRef = useRef<number | null>(null);

    const animateScrollTop = useCallback((container: HTMLElement, targetTop: number, durationMs = 420) => {
        // Prefer native smooth scrolling (usually smoother + less main-thread work).
        // Keep the same function signature so callers don't change.
        if (scrollAnimFrameRef.current !== null) {
            cancelAnimationFrame(scrollAnimFrameRef.current);
            scrollAnimFrameRef.current = null;
        }

        const reducedMotion = typeof window !== 'undefined'
            && window.matchMedia
            && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

        const maxTop = container.scrollHeight - container.clientHeight;
        const clampedTarget = Math.max(0, Math.min(targetTop, Math.max(0, maxTop)));

        if (reducedMotion || durationMs <= 0 || Math.abs(clampedTarget - container.scrollTop) < 2) {
            container.scrollTop = clampedTarget;
            return;
        }

        try {
            container.scrollTo({ top: clampedTarget, behavior: 'smooth' });
        } catch {
            container.scrollTop = clampedTarget;
        }
    }, []);

    const UploadExtension = Extension.create({
        name: 'uploadKeyframes',
        addCommands() {
            return {
                uploadKeyframes: (files: File[], callback: (results: Array<{ url: string, assetId: string }>) => void) => async () => {
                    try {
                        const promises = files.map((file: File) => uploadAsset({ file, kind: 'user_image' }));
                        const results = await Promise.all(promises);
                        const mapped = results.map(r => ({ url: r.contentUrl, assetId: r.assetId }));
                        callback(mapped);
                        return true;
                    } catch (e) {
                        console.error("Upload failed", e);
                        return false;
                    }
                }
                // eslint-disable-next-line @typescript-eslint/no-explicit-any
            } as any;
        }
    });

    const editor = useEditor({
        immediatelyRender: false,
        extensions: [
            StarterKit.configure({ heading: false, paragraph: false }),
            CustomHeading,
            CustomParagraph,
            BlockAttributes,
            NavigationExtension,
            UploadExtension,
            EnterInParagraph,
            Underline, TiptapHighlight, Link, TaskList, TaskItem, Typography, Placeholder, TextAlign
        ],
        content: blocksToTiptap(contentBlocks),
        onUpdate: () => {
            hasPendingChangesRef.current = true;
            scheduleAutosave();
        },
        editorProps: {
            attributes: { class: "prose prose-stone prose-lg max-w-none focus:outline-none min-h-[300px] px-4 py-3 ml-12 2xl:prose-xl 2xl:px-8 2xl:py-6 2xl:ml-16" },
            handlePaste: (view, event) => {
                const items = Array.from(event.clipboardData?.items || []);
                const imageItems = items.filter(item => item.type.startsWith('image/'));

                if (imageItems.length > 0) {
                    event.preventDefault();
                    const files: File[] = [];
                    imageItems.forEach(item => {
                        const f = item.getAsFile();
                        if (f) files.push(f);
                    });

                    if (files.length === 0) return false;

                    // Find the paragraph node context
                    const { state } = view;
                    const { selection } = state;
                    const { $from } = selection;

                    // Find the paragraph node
                    let targetPos = -1;
                    let targetNode = null;

                    // Check if current node is paragraph or find one up
                    if ($from.parent.type.name === 'paragraph') {
                        targetNode = $from.parent;
                        targetPos = $from.before();
                    } else {
                        // Fallback? Try to find first paragraph in selection?
                        // For now, only support if inside paragraph.
                    }

                    if (targetNode && targetPos !== -1) {
                        // Perform upload batch
                        const promises = files.map((file: File) => uploadAssetRef.current({ file, kind: 'user_image' }));
                        Promise.all(promises)
                            .then((results: Array<{ assetId: string; contentUrl: string }>) => {
                                // Get FRESH node from state to avoid stale attrs if user typed fast
                                const freshNode = view.state.doc.nodeAt(targetPos);
                                if (!freshNode) return;

                                const newKeyframes = results.map(res => ({
                                    assetId: res.assetId,
                                    contentUrl: res.contentUrl,
                                    timeMs: freshNode.attrs.timeMs || 0
                                }));

                                const currentKeyframes = freshNode.attrs.keyframes || [];
                                const combinedKeyframes = [...currentKeyframes, ...newKeyframes];

                                const tr = view.state.tr.setNodeMarkup(targetPos, undefined, {
                                    ...freshNode.attrs,
                                    keyframes: combinedKeyframes
                                });
                                view.dispatch(tr);
                            })
                            .catch(err => console.error("Paste upload failed", err));
                    }

                    return true;
                }
                return false;
            }
        },
    });

    const setSelectionWithoutScrolling = useCallback((pos: number) => {
        if (!editor) return;
        try {
            const tr = editor.state.tr.setSelection(TextSelection.create(editor.state.doc, pos));
            // Don't call tr.scrollIntoView() — avoids ProseMirror instant scroll.
            editor.view.dispatch(tr);
        } catch {
            // ignore
        }
    }, [editor]);

    const handleSave = useCallback(async () => {
        if (!editor || !hasPendingChangesRef.current) return;

        const json = editor.getJSON();
        const blocks = tiptapToBlocks(json);

        setSaveStatus("saving");
        try {
            await saveBlocks(blocks);
            hasPendingChangesRef.current = false;
            setSaveStatus("saved");
            onSaveSuccess?.();
            setTimeout(() => setSaveStatus("idle"), 3000);
        } catch (error) {
            console.error("Save failed", error);
            setSaveStatus("error");
            onSaveError?.(error as Error);
        }
    }, [saveBlocks, onSaveSuccess, onSaveError, editor]);

    useEffect(() => {
        saveHandlerRef.current = handleSave;
    }, [handleSave]);

    const scheduleAutosave = useCallback(() => {
        if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
        saveTimerRef.current = setTimeout(() => {
            if (saveHandlerRef.current) saveHandlerRef.current();
        }, AUTOSAVE_DELAY_MS);
    }, []);

    useEffect(() => {
        if (editor && onBlockNavigation) {
            // eslint-disable-next-line @typescript-eslint/no-explicit-any, react-hooks/immutability
            (editor.storage as any).navigation.onNavigate = onBlockNavigation;
        }
    }, [editor, onBlockNavigation]);

    useImperativeHandle(ref, () => ({
        scrollToBlock: (blockId: string) => {
            if (!editor) return;
            const element = document.querySelector(`[data-block-id="${blockId}"]`) as HTMLElement;
            const getContainer = (targetEl: HTMLElement) => (
                (targetEl.closest('.overflow-y-auto') as HTMLElement | null)
                ?? (document.scrollingElement as HTMLElement | null)
            );

            const computeDesiredTop = (targetEl: HTMLElement, container: HTMLElement, block: ScrollLogicalPosition) => {
                const topPos = targetEl.getBoundingClientRect().top - container.getBoundingClientRect().top + container.scrollTop;
                if (block === 'center') {
                    return topPos - (container.clientHeight / 2) + (targetEl.clientHeight / 2);
                }

                const scrollMarginTop = Number.parseFloat(getComputedStyle(targetEl).scrollMarginTop || '0') || 0;
                return topPos - scrollMarginTop - 12;
            };

            const scrollElementIntoView = (targetEl: HTMLElement, block: ScrollLogicalPosition, durationMs?: number) => {
                const container = getContainer(targetEl);
                if (container) {
                    const desiredTop = computeDesiredTop(targetEl, container, block);
                    if (Math.abs(container.scrollTop - desiredTop) > 8) {
                        animateScrollTop(container, desiredTop, durationMs);
                    }
                } else {
                    targetEl.scrollIntoView({ behavior: 'smooth', block });
                }
            };

            let pos = -1;
            editor.state.doc.descendants((node, position) => {
                if (node.attrs?.blockId === blockId) { pos = position; return false; }
            });

            // Resolve target element AFTER we know pos, to avoid double-scroll.
            let targetEl: HTMLElement | null = element || null;
            if (!targetEl && pos >= 0) {
                try {
                    const domAtPos = editor.view.domAtPos(pos);
                    const domNode = domAtPos.node;
                    targetEl = (domNode.nodeType === Node.TEXT_NODE ? domNode.parentElement : domNode) as HTMLElement | null;
                } catch {
                    targetEl = null;
                }
            }

            if (targetEl) {
                scrollElementIntoView(targetEl, 'start');
            }

            if (pos >= 0) {
                // Apply selection on next frame without focusing to avoid hard scroll.
                requestAnimationFrame(() => setSelectionWithoutScrolling(pos));

                // Layout-shift correction (e.g., images above load later)
                const correct = (delayMs: number) => {
                    window.setTimeout(() => {
                        const liveEl = (document.querySelector(`[data-block-id="${blockId}"]`) as HTMLElement | null) || targetEl;
                        if (!liveEl) return;
                        scrollElementIntoView(liveEl, 'start', 240);
                    }, delayMs);
                };
                correct(180);
                correct(700);
            }
        },
        scrollToHighlight: (highlightId: string) => {
            if (!editor) return;
            const element = document.querySelector(`[data-highlight-id="${highlightId}"]`) as HTMLElement;
            const getContainer = (targetEl: HTMLElement) => (
                (targetEl.closest('.overflow-y-auto') as HTMLElement | null)
                ?? (document.scrollingElement as HTMLElement | null)
            );

            const computeDesiredTop = (targetEl: HTMLElement, container: HTMLElement) => {
                const topPos = targetEl.getBoundingClientRect().top - container.getBoundingClientRect().top + container.scrollTop;
                return topPos - (container.clientHeight / 2) + (targetEl.clientHeight / 2);
            };

            const scrollElementIntoView = (targetEl: HTMLElement, durationMs?: number) => {
                const container = getContainer(targetEl);
                if (container) {
                    const desiredTop = computeDesiredTop(targetEl, container);
                    if (Math.abs(container.scrollTop - desiredTop) > 8) {
                        animateScrollTop(container, desiredTop, durationMs);
                    }
                } else {
                    targetEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
                }
            };

            let pos = -1;
            editor.state.doc.descendants((node, position) => {
                if (node.attrs?.highlightId === highlightId) { pos = position; return false; }
            });

            let targetEl: HTMLElement | null = element || null;
            if (!targetEl && pos >= 0) {
                try {
                    const domAtPos = editor.view.domAtPos(pos);
                    const domNode = domAtPos.node;
                    targetEl = (domNode.nodeType === Node.TEXT_NODE ? domNode.parentElement : domNode) as HTMLElement | null;
                } catch {
                    targetEl = null;
                }
            }

            if (targetEl) {
                scrollElementIntoView(targetEl);
            }

            if (pos >= 0) {
                requestAnimationFrame(() => setSelectionWithoutScrolling(pos));

                const correct = (delayMs: number) => {
                    window.setTimeout(() => {
                        const liveEl = (document.querySelector(`[data-highlight-id="${highlightId}"]`) as HTMLElement | null) || targetEl;
                        if (!liveEl) return;
                        scrollElementIntoView(liveEl, 240);
                    }, delayMs);
                };
                correct(180);
                correct(700);
            }
        },
    }));

    useEffect(() => {
        return () => {
            if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
            if (hasPendingChangesRef.current && saveHandlerRef.current) {
                saveHandlerRef.current();
            }
        }
    }, []);

    if (!editor) return <div>{t("loading")}</div>;

    return (
        <div className="flex flex-col bg-white relative rounded-xl">
            <div className="flex items-center justify-between border-b border-stone-100 px-4 py-3 2xl:px-8 2xl:py-6 bg-white sticky top-0 z-10 rounded-t-xl">
                <div className="text-base 2xl:text-xl font-medium text-stone-600">
                    {t("editorTitle")} ({editor.storage.characterCount?.words?.() || 0} {t("words")})
                </div>
                <div className="flex items-center gap-2 text-base 2xl:text-xl">
                    {saveStatus === "saving" && <span className="text-stone-400">{t("saving")}</span>}
                    {saveStatus === "saved" && <span className="text-green-600 flex items-center gap-1">{t("saved")}</span>}
                    {saveStatus === "error" && <span className="text-rose-600">{t("saveFailed")}</span>}
                </div>
            </div>
            <div className="flex-1">
                <EditorContent editor={editor} />
            </div>
        </div>
    );
});

NoteEditor.displayName = "NoteEditor";
