import { useQuery, useQueryClient, useMutation } from "@tanstack/react-query";
import { queryKeys } from "./queryKeys";
import { fetchJob, fetchJobLogs, cancelJob, retryJob } from "./jobApi";
import type { Job, LogsResponse } from "../contracts/types";

/**
 * Query hook for fetching job status
 * - Enabled polling when job is running
 * - Stops polling when job reaches terminal state
 */
export function useJobQuery(jobId: string) {
    return useQuery({
        queryKey: queryKeys.job(jobId),
        queryFn: () => fetchJob(jobId),
        refetchInterval: (query) => {
            const data = query.state.data as Job | undefined;
            if (!data) return false;

            // Poll every 2s if running, stop if terminal state
            const isRunning = data.status === "running" || data.status === "queued";
            return isRunning ? 2000 : false;
        },
        staleTime: 1000, // Consider stale after 1s
    });
}

/**
 * Query hook for fetching job logs with cursor-based pagination
 */
export function useJobLogsQuery(jobId: string, cursor?: string) {
    return useQuery({
        queryKey: cursor ? [...queryKeys.logs(jobId), cursor] : queryKeys.logs(jobId),
        queryFn: () => fetchJobLogs(jobId, cursor),
        // Tail view: poll for new logs; history view (cursor set) stays static.
        refetchInterval: cursor ? false : 2000,
        staleTime: 5000, // Logs don't change frequently
    });
}

/**
 * Mutation hook for canceling a job
 */
export function useCancelJobMutation(jobId: string) {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: () => cancelJob(jobId),
        onSuccess: () => {
            // Invalidate job query to refetch new status
            queryClient.invalidateQueries({ queryKey: queryKeys.job(jobId) });
        },
    });
}

/**
 * Mutation hook for retrying a job
 */
export function useRetryJobMutation(jobId: string) {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: () => retryJob(jobId),
        onSuccess: () => {
            // Invalidate job query to refetch new status
            queryClient.invalidateQueries({ queryKey: queryKeys.job(jobId) });
        },
    });
}
