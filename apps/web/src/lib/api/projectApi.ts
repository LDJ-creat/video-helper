import { apiFetch } from "./apiClient";
import { endpoints } from "./endpoints";
import type { ProjectsListResponse, ProjectDetailResponse } from "../contracts/projectTypes";
import { config } from "../config";

export async function fetchProjects(cursor?: string): Promise<ProjectsListResponse> {
    const baseUrl = config.apiBaseUrl || window.location.origin;
    const url = new URL(endpoints.projects(), baseUrl);
    if (cursor) {
        url.searchParams.set("cursor", cursor);
    }
    return apiFetch<ProjectsListResponse>(url);
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
