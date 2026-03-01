/**
 * Job creation types aligned with API contract
 * Reference: api.md POST /api/v1/jobs specification
 */

export type SourceType = "youtube" | "bilibili" | "url" | "upload";

export type CreateJobUrlRequest = {
    sourceUrl: string;
    title?: string;
    outputLanguage?: string;
};

export type CreateJobResponse = {
    jobId: string;
    projectId: string;
    status: "queued";
    createdAtMs: number;
};
