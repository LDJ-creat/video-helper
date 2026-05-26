import { apiFetch } from "./apiClient";
import { endpoints } from "./endpoints";
import type {
    BatchUpdateCategoryRequest,
    BatchUpdateCategoryResponse,
    PatchProjectCategoryRequest,
    ProjectsListResponse,
    ProjectDetailResponse,
} from "../contracts/projectTypes";
import { config } from "../config";

export async function fetchProjects(
    cursor?: string,
    categoryId?: string | null
): Promise<ProjectsListResponse> {
    const baseUrl = config.apiBaseUrl || window.location.origin;
    const url = new URL(endpoints.projects(), baseUrl);
    if (cursor) {
        url.searchParams.set("cursor", cursor);
    }
    if (categoryId) {
        url.searchParams.set("categoryId", categoryId);
    }
    return apiFetch<ProjectsListResponse>(url);
}

export async function patchProjectCategory(
    projectId: string,
    data: PatchProjectCategoryRequest
): Promise<ProjectDetailResponse> {
    const url = `${config.apiBaseUrl}${endpoints.patchProject(projectId)}`;
    return apiFetch<ProjectDetailResponse>(url, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
    });
}

export async function batchUpdateProjectCategory(
    data: BatchUpdateCategoryRequest
): Promise<BatchUpdateCategoryResponse> {
    const url = `${config.apiBaseUrl}${endpoints.batchProjectCategory()}`;
    return apiFetch<BatchUpdateCategoryResponse>(url, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
    });
}

export async function fetchProjectDetail(projectId: string): Promise<ProjectDetailResponse> {
    const url = `${config.apiBaseUrl}${endpoints.project(projectId)}`;
    return apiFetch<ProjectDetailResponse>(url);
}

export async function deleteProject(projectId: string): Promise<void> {
    const url = `${config.apiBaseUrl}${endpoints.deleteProject(projectId)}`;
    await apiFetch<void>(url, {
        method: "DELETE",
    });
}
