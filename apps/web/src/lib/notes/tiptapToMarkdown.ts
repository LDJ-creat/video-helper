import type { JSONContent } from "@tiptap/react";
import type { Keyframe } from "@/lib/contracts/resultTypes";
import { formatTimeRange } from "./formatTimestamp";

export type NoteMarkdownLabels = {
    documentTitle: string;
    exportedAt: string;
    keyframeAlt: string;
};

export type TiptapToMarkdownOptions = {
    labels: NoteMarkdownLabels;
    exportedAt?: Date;
};

function resolveAssetUrl(url: string): string {
    if (url.startsWith("http://") || url.startsWith("https://")) return url;
    if (typeof window !== "undefined") {
        return new URL(url, window.location.origin).href;
    }
    return url;
}

function applyMarks(text: string, marks?: JSONContent["marks"]): string {
    if (!marks?.length) return text;

    let result = text;
    for (const mark of marks) {
        switch (mark.type) {
            case "bold":
                result = `**${result}**`;
                break;
            case "italic":
                result = `*${result}*`;
                break;
            case "strike":
                result = `~~${result}~~`;
                break;
            case "code":
                result = `\`${result}\``;
                break;
            case "link":
                result = `[${result}](${mark.attrs?.href ?? ""})`;
                break;
            case "highlight":
                result = `==${result}==`;
                break;
            case "underline":
                result = `<u>${result}</u>`;
                break;
            default:
                break;
        }
    }
    return result;
}

function inlineNodesToMarkdown(nodes: JSONContent[] | undefined, continuationIndent: string): string {
    if (!nodes?.length) return "";

    return nodes
        .map((node) => {
            if (node.type === "hardBreak") {
                return `\n${continuationIndent}`;
            }
            if (node.type === "text") {
                return applyMarks(node.text ?? "", node.marks);
            }
            return "";
        })
        .join("");
}

function formatKeyframes(keyframes: Keyframe[], keyframeAlt: string): string[] {
    return keyframes.map((kf) => `   ![${keyframeAlt}](${resolveAssetUrl(kf.contentUrl)})`);
}

function formatExportTimestamp(date: Date, locale?: string): string {
    try {
        return new Intl.DateTimeFormat(locale, {
            year: "numeric",
            month: "2-digit",
            day: "2-digit",
            hour: "2-digit",
            minute: "2-digit",
        }).format(date);
    } catch {
        return date.toISOString();
    }
}

export function isNoteEmpty(doc: JSONContent): boolean {
    if (!doc.content?.length) return true;

    return !doc.content.some((node) => {
        if (node.type === "heading") {
            return Boolean(node.content?.some((c) => c.text?.trim()));
        }
        if (node.type === "paragraph") {
            const hasText = node.content?.some((c) => c.text?.trim());
            const keyframes = (node.attrs?.keyframes ?? []) as Keyframe[];
            return Boolean(hasText || keyframes.length > 0);
        }
        return false;
    });
}

export function tiptapToMarkdown(doc: JSONContent, options: TiptapToMarkdownOptions): string {
    const exportedAt = options.exportedAt ?? new Date();
    const lines: string[] = [
        `# ${options.labels.documentTitle}`,
        "",
        `> ${options.labels.exportedAt}: ${formatExportTimestamp(exportedAt)}`,
        "",
    ];

    let highlightCounter = 0;

    for (const node of doc.content ?? []) {
        if (node.type === "heading" && node.attrs?.level === 2) {
            highlightCounter = 0;
            const title = inlineNodesToMarkdown(node.content, "");
            lines.push(`## ${title || "Untitled"}`);

            const { startMs, endMs } = node.attrs ?? {};
            if (startMs != null) {
                lines.push(`<!-- time: ${formatTimeRange(startMs, endMs)} -->`);
            }
            lines.push("");
            continue;
        }

        if (node.type === "paragraph") {
            highlightCounter += 1;
            const keyframes = (node.attrs?.keyframes ?? []) as Keyframe[];
            lines.push(...formatKeyframes(keyframes, options.labels.keyframeAlt));

            const text = inlineNodesToMarkdown(node.content, "   ");
            lines.push(`${highlightCounter}. ${text}`);
            lines.push("");
        }
    }

    return lines.join("\n").trimEnd() + "\n";
}
