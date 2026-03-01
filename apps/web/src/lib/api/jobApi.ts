import { apiFetch } from "./apiClient";
import { endpoints } from "./endpoints";
import type { Job, LogsResponse } from "../contracts/types";
import { config } from "../config";

/**
 * Fetch job status (for polling fallback)
 */
export async function fetchJob(jobId: string): Promise<Job> {
    const url = `${config.apiBaseUrl}${endpoints.job(jobId)}`;
    return apiFetch<Job>(url);
}

/**
 * Fetch job logs with cursor-based pagination
 */
export async function fetchJobLogs(
    jobId: string,
    cursor?: string,
    limit = 200
): Promise<LogsResponse> {
    const baseUrl = config.apiBaseUrl || window.location.origin;
    const url = new URL(endpoints.jobLogs(jobId), baseUrl);
    if (cursor) url.searchParams.set("cursor", cursor);
    url.searchParams.set("limit", String(limit));

    return apiFetch<LogsResponse>(url.toString());
}

/**
 * Cancel a job
 */
export async function cancelJob(jobId: string): Promise<{ ok: boolean }> {
    const url = `${config.apiBaseUrl}${endpoints.jobCancel(jobId)}`;
    return apiFetch<{ ok: boolean }>(url, {
        method: "POST",
    });
}

/**
 * Retry a job
 */
export async function retryJob(jobId: string): Promise<{ ok: boolean }> {
    const url = `${config.apiBaseUrl}${endpoints.jobRetry(jobId)}`;
    return apiFetch<{ ok: boolean }>(url, {
        method: "POST",
    });
}
