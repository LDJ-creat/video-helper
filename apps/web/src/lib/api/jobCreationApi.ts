import { apiFetch } from "./apiClient";
import { endpoints } from "./endpoints";
import type { CreateJobUrlRequest, CreateJobResponse } from "../contracts/jobCreation";
import { config } from "../config";

/**
 * Create a job from URL (YouTube/Bilibili)
 * @param data Job creation request with source URL
 * @returns Created job information
 */
export async function createJobFromUrl(
    data: CreateJobUrlRequest
): Promise<CreateJobResponse> {
    const url = `${config.apiBaseUrl}${endpoints.jobs()}`;
    return apiFetch<CreateJobResponse>(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
    });
}

/**
 * Create a job from uploaded file
 * @param file Video file to upload
 * @param title Optional title for the project
 * @returns Created job information
 */
export async function createJobFromUpload(
    file: File,
    title?: string,
    outputLanguage?: string
): Promise<CreateJobResponse> {
    const url = `${config.apiBaseUrl}${endpoints.jobs()}`;
    const formData = new FormData();
    formData.append("sourceType", "upload");
    formData.append("file", file);
    if (title) {
        formData.append("title", title);
    }
    if (outputLanguage) {
        formData.append("outputLanguage", outputLanguage);
    }

    return apiFetch<CreateJobResponse>(url, {
        method: "POST",
        body: formData,
    });
}
