"use client";

/**
 * @deprecated Use AnalysisProgressPanel for job progress UI.
 * Kept for imports that pass a static Job snapshot without SSE/logs.
 */
import type { Job } from "@/lib/contracts/types";
import { AnalysisProgressPanel } from "@/components/features/analysis/AnalysisProgressPanel";

interface JobProgressProps {
    job: Job;
}

export function JobProgress({ job }: JobProgressProps) {
    return (
        <AnalysisProgressPanel
            job={job}
            connectionMode="polling"
            projectId={job.projectId}
            jobId={job.jobId}
            variant="compact"
            onResume={() => {}}
            onCancel={() => {}}
        />
    );
}
