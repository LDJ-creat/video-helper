import type { LogEntry } from "@/lib/contracts/types";

const TECHNICAL_PATTERNS: RegExp[] = [
    /^job failed\b/i,
    /\bErrorCode\./i,
    /\bcode=[A-Z_]+\b/,
    /\bmessage=.*\bdetails=/i,
    /^status=(queued|running|blocked|succeeded|failed|canceled)$/i,
    /^progress=/i,
];

export function isTechnicalLog(message: string): boolean {
    const trimmed = message.trim();
    if (!trimmed) return true;
    return TECHNICAL_PATTERNS.some((re) => re.test(trimmed));
}

export function pickUserFacingLog(items: LogEntry[] | undefined): string | null {
    if (!items?.length) return null;
    for (let i = items.length - 1; i >= 0; i--) {
        const msg = items[i]?.message?.trim();
        if (msg && !isTechnicalLog(msg)) return msg;
    }
    return null;
}
