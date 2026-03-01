import type { JobEvent, JobEventType } from "./jobEvents";

export type SseEventHandler = (event: JobEvent) => void;
export type SseErrorHandler = (error: Error) => void;
export type SseCloseHandler = () => void;
export type SseOpenHandler = () => void;

export interface SseClientOptions {
    url: string;
    lastEventId?: string;
    onEvent: SseEventHandler;
    onOpen?: SseOpenHandler;
    onError?: SseErrorHandler;
    onClose?: SseCloseHandler;
    heartbeatTimeoutMs?: number; // Default: 60000 (60s)
}

/**
 * SSE Client wrapper for job events
 * - Parses event type and payload
 * - Supports Last-Event-ID for reconnection
 * - Detects heartbeat timeout (connection stale)
 */
export class SseClient {
    private eventSource: EventSource | null = null;
    private heartbeatTimer: NodeJS.Timeout | null = null;
    private errorCount = 0;
    private lastErrorAtMs = 0;
    private readonly options: SseClientOptions & {
        heartbeatTimeoutMs: number;
        onError: SseErrorHandler;
        onClose: SseCloseHandler;
        onOpen: SseOpenHandler;
    };
    private closed = false;

    constructor(options: SseClientOptions) {
        this.options = {
            ...options,
            heartbeatTimeoutMs: options.heartbeatTimeoutMs ?? 60000,
            onOpen: options.onOpen ?? (() => { }),
            onError: options.onError ?? (() => { }),
            onClose: options.onClose ?? (() => { }),
        };
    }

    connect(): void {
        if (this.eventSource || this.closed) return;

        const url = new URL(this.options.url, window.location.origin);
        const eventSource = new EventSource(url.toString());

        // Listen to all event types
        const eventTypes: JobEventType[] = ["heartbeat", "progress", "log", "state"];
        eventTypes.forEach((type) => {
            eventSource.addEventListener(type, (e: MessageEvent) => {
                this.resetHeartbeatTimer();
                try {
                    const payload = JSON.parse(e.data) as JobEvent;
                    this.options.onEvent({ ...payload, type });
                } catch (err) {
                    console.error(`[SseClient] Failed to parse ${type} event:`, err);
                }
            });
        });

        eventSource.onerror = (e) => {
            console.error("[SseClient] Connection error:", e);
            // IMPORTANT:
            // Do NOT close on transient errors. Native EventSource will auto-reconnect.
            // Closing here causes rapid reconnect storms and /events request spam.
            const now = Date.now();
            if (now - this.lastErrorAtMs > 30_000) {
                this.errorCount = 0;
            }
            this.lastErrorAtMs = now;
            this.errorCount += 1;

            // Only surface a fatal error after repeated failures.
            if (this.errorCount >= 3 && !this.isConnected) {
                this.options.onError?.(new Error("SSE connection unstable"));
            }
        };

        eventSource.onopen = () => {
            console.log("[SseClient] Connected");
            this.errorCount = 0;
            this.resetHeartbeatTimer();
            this.options.onOpen?.();
        };

        this.eventSource = eventSource;
    }

    close(): void {
        if (this.closed) return;
        this.closed = true;

        if (this.heartbeatTimer) {
            clearTimeout(this.heartbeatTimer);
            this.heartbeatTimer = null;
        }

        if (this.eventSource) {
            this.eventSource.close();
            this.eventSource = null;
        }

        this.options.onClose?.();
    }

    private resetHeartbeatTimer(): void {
        if (this.heartbeatTimer) {
            clearTimeout(this.heartbeatTimer);
        }

        this.heartbeatTimer = setTimeout(() => {
            console.warn("[SseClient] Heartbeat timeout - closing connection");
            // Heartbeat timeout is treated as fatal: close so caller can fall back to polling.
            this.options.onError?.(new Error("Heartbeat timeout"));
            this.close();
        }, this.options.heartbeatTimeoutMs);
    }

    get isConnected(): boolean {
        return this.eventSource?.readyState === EventSource.OPEN;
    }
}
