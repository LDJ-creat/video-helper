import { useMutation } from "@tanstack/react-query";
import { createJobFromUrl, createJobFromUpload } from "./jobCreationApi";
import { useRouter } from "next/navigation";
import type { CreateJobUrlRequest } from "../contracts/jobCreation";

/**
 * Mutation hook for creating job from URL
 * Automatically redirects to job page on success
 */
export function useCreateJobFromUrl() {
    const router = useRouter();

    return useMutation({
        mutationFn: (data: CreateJobUrlRequest) => createJobFromUrl(data),
        onSuccess: (data) => {
            // Redirect to results page with jobId to track progress
            router.push(`/projects/${data.projectId}/results?jobId=${data.jobId}`);
        },
    });
}

/**
 * Mutation hook for creating job from file upload
 * Automatically redirects to job page on success
 */
export function useCreateJobFromUpload() {
    const router = useRouter();

    return useMutation({
        mutationFn: ({ file, title }: { file: File; title?: string }) =>
            createJobFromUpload(file, title),
        onSuccess: (data) => {
            // Redirect to results page with jobId to track progress
            router.push(`/projects/${data.projectId}/results?jobId=${data.jobId}`);
        },
    });
}
