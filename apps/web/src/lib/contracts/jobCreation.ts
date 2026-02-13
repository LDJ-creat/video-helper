/**
 * Job creation types aligned with API contract
 * Reference: api.md POST /api/v1/jobs specification
 */

export type SourceType = "youtube" | "bilibili" | "upload";

export type CreateJobUrlRequest = {
    sourceType: Exclude<SourceType, "upload">;
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
