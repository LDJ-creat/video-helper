import { useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { SseClient } from "./sseClient";
import { endpoints } from "../api/endpoints";
import { queryKeys } from "../api/queryKeys";
import type { JobEvent } from "./jobEvents";
import type { Job, LogEntry } from "../contracts/types";

export interface UseJobSseOptions {
  jobId: string;
  enabled?: boolean;
  onEvent?: (event: JobEvent) => void;
}

export interface UseJobSseReturn {
  isConnected: boolean;
  connectionMode: "sse" | "polling" | "disconnected";
  lastEvent: JobEvent | null;
}

/**
 * Hook for consuming SSE job events with automatic polling fallback
 * - Establishes SSE connection to /api/v1/jobs/{jobId}/events
 * - Updates React Query cache on progress/state/log events
 * - Falls back to polling on SSE failure
 */
export function useJobSse(options: UseJobSseOptions): UseJobSseReturn {
  const { jobId, enabled = true, onEvent } = options;
  const queryClient = useQueryClient();
  const sseClientRef = useRef<SseClient | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [connectionMode, setConnectionMode] = useState<"sse" | "polling" | "disconnected">("disconnected");
  const [lastEvent, setLastEvent] = useState<JobEvent | null>(null);

  useEffect(() => {
    if (!enabled) return;

    const url = endpoints.jobEvents(jobId);

    const client = new SseClient({
      url,
      onEvent: (event) => {
        setLastEvent(event);
        onEvent?.(event);

        // Update React Query cache based on event type
        if (event.type === "progress" || event.type === "state") {
          queryClient.setQueryData<Job>(queryKeys.job(jobId), (old) => {
            if (!old) return old;
            return {
              ...old,
              stage: event.stage as any,
              progress: event.progress,
              updatedAtMs: event.tsMs,
            };
          });
        }

        if (event.type === "log" && event.message) {
          // Append log entry to cache (optional implementation)
          queryClient.setQueryData<{ items: LogEntry[] }>(
            queryKeys.logs(jobId),
            (old) => {
              const newLog: LogEntry = {
                tsMs: event.tsMs,
                level: "INFO",
                message: event.message!,
                stage: event.stage as any,
              };
              return old
                ? { items: [...old.items, newLog] }
                : { items: [newLog] };
            }
          );
        }
      },
      onError: (error) => {
        console.error("[useJobSse] SSE error, falling back to polling:", error);
        setIsConnected(false);
        setConnectionMode("polling");
        // React Query's polling will take over via refetchInterval
      },
      onClose: () => {
        console.log("[useJobSse] SSE connection closed");
        setIsConnected(false);
        setConnectionMode("disconnected");
      },
    });

    client.connect();
    setIsConnected(true);
    setConnectionMode("sse");
    sseClientRef.current = client;

    return () => {
      client.close();
      sseClientRef.current = null;
    };
  }, [jobId, enabled, queryClient, onEvent]);

  return {
    isConnected,
    connectionMode,
    lastEvent,
  };
}
