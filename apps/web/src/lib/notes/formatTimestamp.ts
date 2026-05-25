/** Format milliseconds as HH:MM:SS (or H:MM:SS when hours is 0). */
export function formatTimestamp(ms: number | null | undefined): string {
    if (ms == null || Number.isNaN(ms)) return "00:00";
    const totalSeconds = Math.max(0, Math.floor(ms / 1000));
    const hours = Math.floor(totalSeconds / 3600);
    const minutes = Math.floor((totalSeconds % 3600) / 60);
    const seconds = totalSeconds % 60;
    const pad = (n: number) => String(n).padStart(2, "0");
    if (hours > 0) {
        return `${hours}:${pad(minutes)}:${pad(seconds)}`;
    }
    return `${pad(minutes)}:${pad(seconds)}`;
}

export function formatTimeRange(startMs: number | null | undefined, endMs: number | null | undefined): string {
    const start = formatTimestamp(startMs);
    const end = formatTimestamp(endMs);
    if (endMs == null || endMs === startMs) return start;
    return `${start} - ${end}`;
}
