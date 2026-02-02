import { useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { SseClient } from "./sseClient";
import { queryKeys } from "../api/queryKeys";
import type { JobEvent } from "./jobEvents";
import type { Job, JobStage, LogEntry } from "../contracts/types";

function isJobStage(stage: string): stage is JobStage {
  return (
    stage === "ingest" ||
    stage === "transcribe" ||
    stage === "segment" ||
    stage === "analyze" ||
    stage === "assemble_result" ||
    stage === "extract_keyframes"
  );
}

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
  const fallbackToPollingRef = useRef(false);
  const [isConnected, setIsConnected] = useState(false);
  const [connectionMode, setConnectionMode] = useState<"sse" | "polling" | "disconnected">("disconnected");
  const [lastEvent, setLastEvent] = useState<JobEvent | null>(null);

  useEffect(() => {
    if (!enabled) return;

    fallbackToPollingRef.current = false;

    // IMPORTANT: do not use /api/v1/* here in dev.
    // next.config.ts rewrites /api/v1/:path* to backend and may buffer SSE,
    // causing the browser to miss heartbeat/progress frames.
    const url = `/api/sse/jobs/${encodeURIComponent(jobId)}/events`;

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
              stage: isJobStage(event.stage) ? event.stage : old.stage,
              progress: typeof event.progress === "number" ? event.progress : old.progress,
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
                stage: isJobStage(event.stage) ? event.stage : undefined,
              };
              return old
                ? { items: [...old.items, newLog] }
                : { items: [newLog] };
            }
          );
        }
      },
      onOpen: () => {
        setIsConnected(true);
        setConnectionMode("sse");
      },
      onError: (error) => {
        console.error("[useJobSse] SSE error, falling back to polling:", error);
        fallbackToPollingRef.current = true;
        setIsConnected(false);
        setConnectionMode("polling");
        // React Query's polling will take over via refetchInterval
      },
      onClose: () => {
        console.log("[useJobSse] SSE connection closed");
        setIsConnected(false);
        if (!fallbackToPollingRef.current) {
          setConnectionMode("disconnected");
        }
      },
    });

    client.connect();
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
