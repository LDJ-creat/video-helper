"use client";

import { useEditor, EditorContent, JSONContent, ReactNodeViewRenderer } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
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
                    },
                    startMs: { default: null },
                    endMs: { default: null },
                },
            },
            {
                types: ['paragraph'],
                attributes: {
                    highlightId: {
                        default: null,
                        keepOnSplit: false,
                    },
                    keyframeUrl: { default: null },
                    timeMs: { default: null },
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

export type NoteEditorRef = {
    scrollToBlock: (blockId: string) => void;
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
                heading: { levels: [1, 2, 3] },
            }),
            BlockAttributes,
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
                class: "prose prose-stone max-w-none focus:outline-none min-h-[300px] px-4 py-3",
            },
            handleClick: (view, pos, event) => {
                const node = view.state.doc.nodeAt(pos);
                if (node) {
                    // Check if node (or parent) has timestamp
                    const timeMs = node.attrs.timeMs || node.attrs.startMs;
                    if (timeMs !== null && timeMs !== undefined && onBlockNavigation) {
                        onBlockNavigation(timeMs);
                        return true;
                    }
                }
                return false;
            }
        },
    });

    // Handle initial content updates (if data loads later) - careful with loops
    // For now, we assume initialContentBlocks is stable or we ignore updates after mount 
    // to prevent overwriting user edits.

    useImperativeHandle(ref, () => ({
        scrollToBlock: (blockId: string) => {
            if (!editor) return;
            // Find node with blockId
            let pos = -1;
            editor.state.doc.descendants((node, position) => {
                if (node.attrs.blockId === blockId) {
                    pos = position;
                    return false; // stop
                }
            });

            if (pos >= 0) {
                const dom = editor.view.domAtPos(pos).node as HTMLElement;
                dom.scrollIntoView({ behavior: 'smooth', block: 'start' });
                editor.commands.setTextSelection(pos);
            }
        }
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
        <div className="flex flex-col h-full bg-white relative">
            {/* Toolbar (Simplified for brevity, can restore full toolbar if needed) */}
            <div className="flex items-center justify-between border-b border-stone-200 px-3 py-2 bg-white sticky top-0 z-10">
                <div className="text-sm font-medium text-stone-500">
                    笔记编辑器 ({(contentBlocks || []).length} Blocks)
                </div>
                <div className="flex items-center gap-2 text-sm">
                    {saveStatus === "saving" && <span className="text-stone-600">保存中...</span>}
                    {saveStatus === "saved" && <span className="text-green-600">已保存</span>}
                    {saveStatus === "error" && <span className="text-rose-600">保存失败</span>}
                </div>
            </div>

            <div className="flex-1 overflow-y-auto">
                <EditorContent editor={editor} />
            </div>
        </div>
    );
});

NoteEditor.displayName = "NoteEditor";
