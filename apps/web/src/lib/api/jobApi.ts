import { apiFetch } from "./apiClient";
import { endpoints } from "./endpoints";
import type { Job, LogsResponse } from "../contracts/types";

/**
 * Fetch job status (for polling fallback)
 */
export async function fetchJob(jobId: string): Promise<Job> {
    return apiFetch<Job>(endpoints.job(jobId));
}

/**
 * Fetch job logs with cursor-based pagination
 */
export async function fetchJobLogs(
    jobId: string,
    cursor?: string,
    limit = 200
): Promise<LogsResponse> {
    const url = new URL(endpoints.jobLogs(jobId), window.location.origin);
    if (cursor) url.searchParams.set("cursor", cursor);
    url.searchParams.set("limit", String(limit));

    return apiFetch<LogsResponse>(url.toString());
}

/**
 * Cancel a job
 */
export async function cancelJob(jobId: string): Promise<{ ok: boolean }> {
    return apiFetch<{ ok: boolean }>(endpoints.jobCancel(jobId), {
        method: "POST",
    });
}

/**
 * Retry a job
 */
export async function retryJob(jobId: string): Promise<{ ok: boolean }> {
    return apiFetch<{ ok: boolean }>(endpoints.jobRetry(jobId), {
        method: "POST",
    });
}
