export function sanitizeFilename(name: string): string {
    const sanitized = name.replace(/[<>:"/\\|?*\u0000-\u001f]/g, "_").trim();
    return sanitized || "notes";
}

export function buildNoteFilename(projectTitle: string | undefined, projectId: string): string {
    const base = projectTitle ? sanitizeFilename(projectTitle) : `notes-${projectId.slice(0, 8)}`;
    return `${base}-notes.md`;
}

export function downloadMarkdown(content: string, filename: string): void {
    const blob = new Blob([content], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = filename;
    anchor.click();
    URL.revokeObjectURL(url);
}
