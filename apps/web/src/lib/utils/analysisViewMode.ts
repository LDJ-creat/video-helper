import type { Job } from "@/lib/contracts/types";

export type AnalysisViewMode = "running" | "blocked" | "failed" | "succeeded" | "loading";

export function getAnalysisViewMode(job: Job | undefined): AnalysisViewMode {
    if (!job) return "loading";
    if (job.status === "succeeded") return "succeeded";
    if (job.status === "failed" && job.error) return "failed";

    const details = job.error?.details;
    const detailsObj = details && typeof details === "object" ? (details as Record<string, unknown>) : null;
    const isDuplicateBlocked = job.status === "blocked" && detailsObj?.reason === "already_analyzed";
    if (isDuplicateBlocked) return "blocked";

    if (job.status === "queued" || job.status === "running") return "running";

    // blocked (external plan), canceled with possible resume — show running-style or blocked
    if (job.status === "blocked") return "running";

    if (job.status === "canceled") return "failed";

    return "running";
}

export function isDuplicateAnalyzedBlocked(job: Job | undefined): boolean {
    if (!job || job.status !== "blocked") return false;
    const details = job.error?.details;
    const detailsObj = details && typeof details === "object" ? (details as Record<string, unknown>) : null;
    return detailsObj?.reason === "already_analyzed";
}
