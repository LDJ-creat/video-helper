"use client";

/**
 * @deprecated Error UI is integrated into AnalysisProgressPanel (FailedAnalysisCard).
 * This export remains for backward compatibility.
 */
import type { Job } from "@/lib/contracts/types";
import { AnalysisProgressPanel } from "@/components/features/analysis/AnalysisProgressPanel";
import { useRetryJobMutation } from "@/lib/api/jobQueries";

interface JobErrorProps {
    job: Job;
}

export function JobError({ job }: JobErrorProps) {
    const retryMutation = useRetryJobMutation(job.jobId);

    if (!job.error && job.status !== "failed" && job.status !== "canceled") return null;

    return (
        <AnalysisProgressPanel
            job={job}
            connectionMode="polling"
            projectId={job.projectId}
            jobId={job.jobId}
            variant="compact"
            onResume={() => retryMutation.mutate()}
            onCancel={() => {}}
            isResuming={retryMutation.isPending}
        />
    );
}
