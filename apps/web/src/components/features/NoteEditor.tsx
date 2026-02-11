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
import { Extension, Editor } from '@tiptap/react';
import { useEffect, useRef, useState, useCallback, useImperativeHandle, forwardRef } from "react";
import { useRouter } from "next/navigation";
import { useSaveContentBlocks } from "@/lib/api/resultQueries";
import { ContentBlock, Highlight } from "@/lib/contracts/resultTypes";

const AUTOSAVE_DELAY_MS = 1200;

// Custom extension to add attributes to nodes
const BlockAttributes = Extension.create({
    name: 'blockAttributes',
    addGlobalAttributes() {
        return [
            {
                types: ['heading'],
                attributes: {
                    blockId: {
                        default: null,
                        keepOnSplit: false,
                        renderHTML: attributes => ({
                            'data-block-id': attributes.blockId,
                        }),
                    },
                    startMs: {
                        default: null,
                        renderHTML: attributes => ({
                            'data-start-ms': attributes.startMs,
                        }),
                    },
                    endMs: {
                        default: null,
                        renderHTML: attributes => ({
                            'data-end-ms': attributes.endMs,
                        }),
                    },
                },
            },
            {
                types: ['paragraph'],
                attributes: {
                    highlightId: {
                        default: null,
                        keepOnSplit: false,
                        renderHTML: attributes => ({
                            'data-highlight-id': attributes.highlightId,
                        }),
                    },
                    keyframeUrl: {
                        default: null,
                        renderHTML: attributes => {
                            if (!attributes.keyframeUrl) return {};
                            return {
                                'data-keyframe-url': attributes.keyframeUrl,
                            };
                        }
                    },
                    timeMs: {
                        default: null,
                        renderHTML: attributes => ({
                            'data-time-ms': attributes.timeMs,
                        }),
                    },
                },
            },
        ];
    },
});

export interface NoteEditorProps {
    projectId: string;
    resultId: string;
    contentBlocks: ContentBlock[];
    onSaveSuccess?: () => void;
    onSaveError?: (error: Error) => void;
    onBlockNavigation?: (timeMs: number) => void;
}

// Navigation Extension to bridge React callback
const NavigationExtension = Extension.create({
    name: 'navigation',
    addCommands() {
        return {
            navigateToTime: (timeMs: number) => ({ editor }: { editor: Editor }) => {
                // @ts-ignore - Valid command structure for Tiptap
                editor.storage.navigation.onNavigate?.(timeMs);
                return true;
            }
        } as any
    },
    addStorage() {
        return {
            onNavigate: null as ((ms: number) => void) | null,
        }
    }
});

function formatTime(ms: number): string {
    if (ms === null || ms === undefined) return "00:00";
    const totalSeconds = Math.floor(ms / 1000);
    const minutes = Math.floor(totalSeconds / 60);
    const seconds = totalSeconds % 60;
    return `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
}

// React Node Views
const HeadingBlock = ({ node, editor }: { node: any, editor: any }) => {
    const time = formatTime(node.attrs.startMs || 0);

    return (
        <NodeViewWrapper className="flex items-start gap-3 group -ml-12 pl-1 transition-colors rounded-lg hover:bg-stone-50/50">
            <div
                contentEditable={false}
                className="flex-shrink-0 mt-1.5 px-2 py-0.5 w-[60px] text-center bg-stone-100 text-stone-600 font-mono text-xs rounded-full cursor-pointer hover:bg-blue-100 hover:text-blue-700 transition-colors select-none"
                onClick={() => editor.commands.navigateToTime(node.attrs.startMs)}
                title="点击跳转视频"
            >
                {time}
            </div>
            <NodeViewContent className="flex-1 font-semibold text-stone-800 text-lg leading-snug" />
        </NodeViewWrapper>
    );
};

const ParagraphBlock = ({ node, editor }: { node: any, editor: any }) => {
    const hasTime = node.attrs.timeMs !== null && node.attrs.timeMs !== undefined;

    return (
        <NodeViewWrapper className="flex items-start gap-3 group -ml-12 pl-1 transition-colors rounded-lg hover:bg-stone-50/50">
            <div
                contentEditable={false}
                className={`flex-shrink-0 mt-1 w-[60px] flex justify-center items-center h-6 ${hasTime ? 'cursor-pointer' : 'pointer-events-none'}`}
                onClick={hasTime ? () => editor.commands.navigateToTime(node.attrs.timeMs) : undefined}
            >
                {hasTime && (
                    <div className="p-1 rounded-full text-stone-300 hover:text-blue-600 hover:bg-blue-50 transition-all opacity-0 group-hover:opacity-100" title="点击跳转视频">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                            <polygon points="5 3 19 12 5 21 5 3"></polygon>
                        </svg>
                    </div>
                )}
            </div>
            <NodeViewContent className="flex-1 text-stone-600 leading-relaxed" />
        </NodeViewWrapper>
    );
};

// Custom Extensions
const CustomHeading = Heading.extend({
    addNodeView() {
        return ReactNodeViewRenderer(HeadingBlock);
    },
}).configure({ levels: [1, 2, 3] });

const CustomParagraph = Paragraph.extend({
    addNodeView() {
        return ReactNodeViewRenderer(ParagraphBlock);
    },
});

export type NoteEditorRef = {
    scrollToBlock: (blockId: string) => void;
    scrollToHighlight: (highlightId: string) => void;
};

// Conversion Helpers
function blocksToTiptap(blocks: ContentBlock[]): JSONContent {
    const content: JSONContent[] = [];

    (blocks || []).forEach(block => {
        // Block Title as Heading 2
        content.push({
            type: 'heading',
            attrs: { level: 2, blockId: block.blockId, startMs: block.startMs, endMs: block.endMs },
            content: [{ type: 'text', text: block.title }]
        });

        // Highlights
        block.highlights.forEach(h => {
            const paragraphContent: JSONContent[] = [];

            // Keyframe (Simulated as image inside paragraph or text for now since we lack Image extension in package.json)
            // Ideally we would use an Image node, but without it installed, we might use a special styling/component.
            // For MVP, we'll try to use a simple text representation or HTML if we could.
            // Since we can't easily install new packages, let's assume we render keyframe as a separate paragraph or generic content.
            // Actually, let's just append text. 
            // Better: Use a "Keyframe" mark or just prepend text "[Keyframe]" if URL exists.
            if (h.keyframe?.contentUrl) {
                // If we implemented a custom node for Keyframe, valid. For now, let's treat it as attribute on paragraph 
                // and render it via NodeView or just rely on the data.
                // We will use the attribute 'keyframeUrl' on the paragraph to potentially render it custom later.
            }

            paragraphContent.push({ type: 'text', text: h.text });

            content.push({
                type: 'paragraph',
                attrs: { highlightId: h.highlightId, timeMs: h.startMs, keyframeUrl: h.keyframe?.contentUrl },
                content: paragraphContent
            });
        });
    });

    return {
        type: 'doc',
        content
    };
}

function tiptapToBlocks(json: JSONContent): ContentBlock[] {
    const blocks: ContentBlock[] = [];
    let currentBlock: ContentBlock | null = null;
    let blockIdx = 0;

    json.content?.forEach((node) => {
        if (node.type === 'heading' && node.attrs?.level === 2) {
            // Start new block
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
            // Add to current block
            const highlight: Highlight = {
                highlightId: node.attrs?.highlightId || `hl_${Date.now()}_${Math.random()}`,
                idx: currentBlock.highlights.length,
                text: node.content?.map(c => c.text).join('') || '',
                startMs: node.attrs?.timeMs || currentBlock.startMs, // Fallback
                endMs: currentBlock.endMs, // Fallback
                keyframe: node.attrs?.keyframeUrl ? {
                    assetId: 'unknown', // Lost in conversion if not stored, MVP compromise
                    contentUrl: node.attrs.keyframeUrl,
                    timeMs: node.attrs.timeMs || 0
                } : undefined
            };
            currentBlock.highlights.push(highlight);
        }
    });

    return blocks;
}

export const NoteEditor = forwardRef<NoteEditorRef, NoteEditorProps>(({
    projectId,
    resultId,
    contentBlocks,
    onSaveSuccess,
    onSaveError,
    onBlockNavigation,
}, ref) => {
    const [saveStatus, setSaveStatus] = useState<"idle" | "saving" | "saved" | "error">("idle");
    const [lastSavedAt, setLastSavedAt] = useState<Date | null>(null);
    const saveTimerRef = useRef<NodeJS.Timeout | null>(null);
    const hasPendingChangesRef = useRef(false);

    const { mutateAsync: saveBlocks } = useSaveContentBlocks(projectId);

    const editor = useEditor({
        immediatelyRender: false,
        extensions: [
            StarterKit.configure({
                heading: false, // Use CustomHeading
                paragraph: false, // Use CustomParagraph
            }),
            CustomHeading,
            CustomParagraph,
            BlockAttributes,
            NavigationExtension, // Add Navigation
            Underline,
            TiptapHighlight,
            Link,
            TaskList,
            TaskItem,
            Typography,
            Placeholder.configure({ placeholder: '输入内容...' }),
            TextAlign.configure({ types: ['heading', 'paragraph'] }),
        ],
        content: blocksToTiptap(contentBlocks),
        onUpdate: () => {
            hasPendingChangesRef.current = true;
            scheduleAutosave();
        },
        editorProps: {
            attributes: {
                class: "prose prose-stone max-w-none focus:outline-none min-h-[300px] px-4 py-3 ml-12", // Increased ml for the gutter
            },
            // handleClick removed - handled by NodeViews
        },
    });

    // Sync callback to editor storage
    useEffect(() => {
        if (editor && onBlockNavigation) {
            editor.storage.navigation.onNavigate = onBlockNavigation;
        }
    }, [editor, onBlockNavigation]);

    // Handle initial content updates (if data loads later) - careful with loops
    // For now, we assume initialContentBlocks is stable or we ignore updates after mount 
    // to prevent overwriting user edits.

    useImperativeHandle(ref, () => ({
        scrollToBlock: (blockId: string) => {
            if (!editor) return;
            let pos = -1;
            editor.state.doc.descendants((node, position) => {
                if (node.attrs.blockId === blockId) {
                    pos = position;
                    return false;
                }
            });

            if (pos >= 0) {
                const dom = editor.view.domAtPos(pos).node as HTMLElement;
                dom.scrollIntoView({ behavior: 'smooth', block: 'start' });
                editor.commands.setTextSelection(pos);
            }
        },
        scrollToHighlight: (highlightId: string) => {
            if (!editor) return;
            let pos = -1;
            editor.state.doc.descendants((node, position) => {
                if (node.attrs.highlightId === highlightId) {
                    pos = position;
                    return false;
                }
            });

            if (pos >= 0) {
                const dom = editor.view.domAtPos(pos).node as HTMLElement;
                dom.scrollIntoView({ behavior: 'smooth', block: 'center' });
                editor.commands.setTextSelection(pos);
            }
        },
    }));

    const scheduleAutosave = useCallback(() => {
        if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
        saveTimerRef.current = setTimeout(handleSave, AUTOSAVE_DELAY_MS);
    }, []);

    const handleSave = useCallback(async () => {
        if (!editor || !hasPendingChangesRef.current) return;

        const json = editor.getJSON();
        const blocks = tiptapToBlocks(json);

        setSaveStatus("saving");
        try {
            await saveBlocks({ resultId, contentBlocks: blocks });
            hasPendingChangesRef.current = false;
            setSaveStatus("saved");
            setLastSavedAt(new Date());
            onSaveSuccess?.();
        } catch (error) {
            console.error("Save failed", error);
            setSaveStatus("error");
            onSaveError?.(error as Error);
        }
    }, [editor, resultId, saveBlocks, onSaveSuccess, onSaveError]);

    // Cleanup and Flush
    useEffect(() => {
        return () => {
            if (hasPendingChangesRef.current) handleSave(); // Best effort flush
        };
    }, [handleSave]);

    if (!editor) return <div>Loading Editor...</div>;

    return (
        <div className="flex flex-col h-full bg-white relative rounded-xl">
            {/* Toolbar (Simplified for brevity, can restore full toolbar if needed) */}
            <div className="flex items-center justify-between border-b border-stone-100 px-4 py-3 bg-white sticky top-0 z-10 rounded-t-xl">
                <div className="text-sm font-medium text-stone-600">
                    笔记编辑器 ({(contentBlocks || []).length} Blocks)
                </div>
                <div className="flex items-center gap-2 text-sm">
                    {saveStatus === "saving" && <span className="text-stone-400">保存中...</span>}
                    {saveStatus === "saved" && <span className="text-green-600 flex items-center gap-1"><span className="w-1.5 h-1.5 rounded-full bg-green-500" /> 已保存</span>}
                    {saveStatus === "error" && <span className="text-rose-600">保存失败</span>}
                </div>
            </div>

            <div className="flex-1">
                <EditorContent editor={editor} />
            </div>
        </div>
    );
});

NoteEditor.displayName = "NoteEditor";
